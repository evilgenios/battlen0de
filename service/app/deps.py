"""FastAPI dependency wiring.

Two rules this module exists to enforce everywhere:

1. There is exactly one AccountManager and one AccountRepository per
   process, both built once at startup (see main.py's lifespan) and stored
   on `app.state`. Every request gets the SAME instances — nothing here
   constructs a second AccountManager or a second DB engine.
2. Every account-scoped route depends on get_owned_account, which is the
   ONE place that turns "does this account exist" / "does the caller own
   it" into 404 / 403. No route hand-rolls that check itself, so the
   ownership boundary can't be forgotten on a new endpoint.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Path, Request

from app.security.auth_config import VALID_ROLES, local_auth_enabled
from app.core.account_manager import AccountManager
from app.core.dashboard_session import DashboardSessionStore
from app.core.link_challenge_store import LinkChallengeStore
from app.core.mass_deploy import MassDeployLock
from app.db.repository import AccountRecord, AccountRepository
from app.db.admin_store import AdminSecurityStore

DEV_USER_EMAIL_ENV_VAR = 'DEV_USER_EMAIL'
SESSION_COOKIE_NAME = 'dashboard_session'
CSRF_COOKIE_NAME = 'dashboard_csrf'
CSRF_HEADER_NAME = 'x-csrf-token'


def get_repository(request: Request) -> AccountRepository:
    return request.app.state.repository


def get_account_manager(request: Request) -> AccountManager:
    return request.app.state.account_manager


def get_link_challenge_store(request: Request) -> LinkChallengeStore:
    return request.app.state.link_challenges


def get_mass_deploy_lock(request: Request) -> MassDeployLock:
    return request.app.state.mass_deploy_lock


def get_dashboard_sessions(request: Request) -> DashboardSessionStore:
    return request.app.state.dashboard_sessions


def get_admin_store(request: Request) -> AdminSecurityStore:
    return request.app.state.admin_store


def account_lifecycle(request: Request):
    # Plain Lock (not RLock): FastAPI may enter/exit a yield dependency on
    # different threads. Serialize commands with status/deletion/relink.
    with request.app.state.lifecycle_lock:
        yield


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    email: str
    role: Optional[str] = None

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'


def _session_from_cookie(request: Request, sessions: DashboardSessionStore):
    session_id = request.cookies.get(SESSION_COOKIE_NAME, '')
    return sessions.get(session_id) if session_id else None


def _valid_session(request: Request, sessions: DashboardSessionStore):
    session = _session_from_cookie(request, sessions)
    if session is None:
        raise HTTPException(status_code=401, detail='authentication required')
    if session.role not in VALID_ROLES:
        sessions.destroy(session.session_id)
        raise HTTPException(status_code=403, detail='valid member or admin role required')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        cookie = request.cookies.get(CSRF_COOKIE_NAME, '')
        header = request.headers.get(CSRF_HEADER_NAME, '')
        if not cookie or cookie != header or cookie != session.csrf_token:
            raise HTTPException(status_code=403, detail='CSRF token missing or invalid')
    return session


def get_current_user(
    request: Request,
    repo: AccountRepository = Depends(get_repository),
    sessions: DashboardSessionStore = Depends(get_dashboard_sessions),
) -> AuthenticatedUser:
    local = local_auth_enabled()
    # A supplied stale/invalid cookie never falls back to the local identity.
    if request.cookies.get(SESSION_COOKIE_NAME) or not local:
        session = _valid_session(request, sessions)
        return AuthenticatedUser(id=session.user_id, email=session.email, role=session.role)
    user = repo.get_or_create_user(os.environ[DEV_USER_EMAIL_ENV_VAR].strip().lower())
    return AuthenticatedUser(id=user.id, email=user.email, role=os.environ.get('DEV_USER_ROLE', 'member'))


def require_dashboard_auth(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Always authenticate, including before the first password user exists."""
    return user


def enforce_product_rate_limit(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    sessions: DashboardSessionStore = Depends(get_dashboard_sessions),
) -> None:
    """Durable per-user API abuse guard for authenticated product routes.

    Login/link/grant endpoints keep their tighter dedicated throttles. This
    guard limits the remaining authenticated surface so a valid session cannot
    hammer polling, admin or action endpoints without bound.
    """
    safe_method = request.method in ('GET', 'HEAD', 'OPTIONS')
    scope = 'api-read-minute' if safe_method else 'api-write-minute'
    limit = 600 if safe_method else 120
    sessions.throttle(scope, user.id, limit=limit, seconds=60)


def get_current_dashboard_session(
    request: Request,
    sessions: DashboardSessionStore = Depends(get_dashboard_sessions),
):
    local_auth_enabled()  # Validate configuration even on the auth router.
    return _valid_session(request, sessions)


def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='administrator role required')
    return user


def require_player_scout_access(
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
) -> AuthenticatedUser:
    """Player Scout is a privileged intelligence feature.

    Administrators always retain operator access. Customer/member identities
    must be explicitly granted the entitlement by a site administrator.
    """
    if user.is_admin:
        return user
    record = repo.get_user_by_id(user.id)
    if record is None or not record.player_scout_access:
        raise HTTPException(status_code=403, detail='player scout access required')
    return user


def get_owned_account(
    request: Request,
    lifecycle=Depends(account_lifecycle),
    account_id: uuid.UUID = Path(...),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
) -> AccountRecord:
    account = repo.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail='account not found')
    # Explicit admins retain operator access; members must own the account.
    if account.owner_user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail='account does not belong to the caller')
    if request.method not in ('GET', 'HEAD', 'OPTIONS', 'DELETE') and not request.url.path.endswith(('/disconnect', '/status', '/pilot-pause', '/conquest-guard/disable', '/debug-capture/stop')):
        owner = repo.get_user_by_id(account.owner_user_id)
        if account.status != 'active' or owner is None or owner.status != 'active':
            raise HTTPException(409, 'account is unavailable for game actions')
    if request.method not in ('GET', 'HEAD', 'OPTIONS', 'DELETE'):
        action = request.url.path.partition(f'/accounts/{account_id}/')[2]
        if action not in ('disconnect', 'status', 'pilot-activation', 'pilot-pause',
                          'conquest-guard/disable', 'debug-capture/start', 'debug-capture/stop'):
            request.app.state.account_manager.pilot.check_http(str(account_id), action)
    return account
