"""Dashboard authentication, grants, session policy and admin MFA."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.dashboard_session import DashboardSessionStore
from app.db.admin_store import AdminSecurityStore
from app.db.repository import AccountRepository
from app.deps import (
    AuthenticatedUser,
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    get_admin_store,
    get_current_dashboard_session,
    get_current_user,
    get_dashboard_sessions,
    get_repository,
    require_admin,
)
from app.schemas.admin import MfaCodeRequest, MfaSetupResponse, MfaStatusResponse
from app.schemas.auth import DashboardUserInfo, GrantRequest, LoginRequest, MeResponse, RedeemRequest, UserPolicyRequest
from app.security.auth_config import VALID_ROLES
from app.security.passwords import hash_password, verify_password

router = APIRouter(prefix='/auth', tags=['auth'])
logger = logging.getLogger('battlenode.auth')

COOKIE_SECURE_ENV_VAR = 'DASHBOARD_COOKIE_SECURE'

_DUMMY_PASSWORD_HASH = hash_password('not-a-real-password-used-only-for-constant-time-login')


def _cookie_secure() -> bool:
    return os.environ.get(COOKIE_SECURE_ENV_VAR, 'true').strip().lower() not in ('0', 'false', 'no')


def _set_auth_cookies(response: Response, *, session_id: str, csrf_token: str, max_age: int) -> None:
    secure = _cookie_secure()
    response.set_cookie(
        SESSION_COOKIE_NAME, session_id, max_age=max_age, httponly=True,
        secure=secure, samesite='lax', path='/',
    )
    response.set_cookie(
        CSRF_COOKIE_NAME, csrf_token, max_age=max_age, httponly=False,
        secure=secure, samesite='lax', path='/',
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path='/')
    response.delete_cookie(CSRF_COOKIE_NAME, path='/')


def _audit(store: AdminSecurityStore, **kwargs) -> None:
    """Audit logging must not turn an otherwise valid auth request into a 500."""
    try:
        store.audit(**kwargs)
    except Exception:
        logger.exception('security audit write failed')


@router.post('/login', response_model=DashboardUserInfo)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    repo: AccountRepository = Depends(get_repository),
    sessions: DashboardSessionStore = Depends(get_dashboard_sessions),
    security: AdminSecurityStore = Depends(get_admin_store),
) -> DashboardUserInfo:
    email = body.email.strip().lower()
    try:
        sessions.throttle('login-peer', request.client.host if request.client else 'unknown', limit=60, seconds=60)
        sessions.throttle('login-email', email, limit=5, seconds=900)
    except HTTPException:
        _audit(
            security,
            action='auth.login',
            target_type='identity',
            target_id=email,
            actor_email=email,
            outcome='blocked',
            request=request,
            detail={'reason': 'rate_limited'},
        )
        raise

    user = repo.get_user_by_email(email)
    hash_to_check = user.password_hash if (user and user.password_hash) else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, hash_to_check)
    valid_identity = bool(
        user is not None
        and user.password_hash
        and password_ok
        and user.role in VALID_ROLES
        and user.status == 'active'
    )
    if not valid_identity:
        _audit(
            security,
            action='auth.login',
            target_type='identity',
            target_id=email,
            actor_user_id=user.id if user else None,
            actor_email=email,
            outcome='failure',
            request=request,
            detail={'reason': 'invalid_credentials_or_identity_state'},
        )
        raise HTTPException(status_code=401, detail='invalid email or password')

    mfa_required, mfa_valid = security.verify_login_mfa(user.id, body.mfa_code)
    if mfa_required and not mfa_valid:
        _audit(
            security,
            action='auth.login',
            target_type='identity',
            target_id=str(user.id),
            actor_user_id=user.id,
            actor_email=user.email,
            outcome='failure',
            request=request,
            detail={'reason': 'mfa_required_or_invalid', 'code_supplied': bool(body.mfa_code)},
        )
        detail = 'mfa required' if not body.mfa_code else 'invalid email, password, or authenticator code'
        raise HTTPException(status_code=401, detail=detail)

    session = sessions.create(
        user_id=user.id,
        email=user.email,
        role=user.role,
        expected_password_hash=user.password_hash,
    )
    _set_auth_cookies(
        response,
        session_id=session.session_id,
        csrf_token=session.csrf_token,
        max_age=sessions.ttl_seconds,
    )
    _audit(
        security,
        action='auth.login',
        target_type='identity',
        target_id=str(user.id),
        actor_user_id=user.id,
        actor_email=user.email,
        outcome='success',
        request=request,
        detail={'role': user.role, 'mfa': bool(mfa_required)},
    )
    return DashboardUserInfo(email=session.email, role=session.role, csrf_token=session.csrf_token)


@router.post('/logout', status_code=204)
def logout(
    request: Request,
    response: Response,
    session=Depends(get_current_dashboard_session),
    sessions: DashboardSessionStore = Depends(get_dashboard_sessions),
    security: AdminSecurityStore = Depends(get_admin_store),
) -> None:
    sessions.destroy(session.session_id)
    _clear_auth_cookies(response)
    _audit(
        security,
        action='auth.logout',
        target_type='session',
        target_id=session.cache_key,
        actor_user_id=session.user_id,
        actor_email=session.email,
        outcome='success',
        request=request,
    )


@router.get('/me', response_model=MeResponse)
def me(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    sessions: DashboardSessionStore = Depends(get_dashboard_sessions),
    repo: AccountRepository = Depends(get_repository),
    security: AdminSecurityStore = Depends(get_admin_store),
) -> MeResponse:
    session = sessions.get(request.cookies.get(SESSION_COOKIE_NAME, ''))
    record = repo.get_user_by_id(user.id)
    max_accounts = record.max_accounts if record is not None else 1
    max_sessions = record.max_sessions if record is not None else 1
    max_active_accounts = record.max_active_accounts if record is not None else 1
    mfa_enabled = security.mfa_status(user.id)['enabled'] if user.is_admin else False
    return MeResponse(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        session_key=session.cache_key if session else f'local:{user.id}:{user.role}',
        active_sessions=sessions.active_count() if user.is_admin else sessions.active_count(user.id),
        plan='alliance' if max_accounts > 1 else 'individual',
        max_accounts=max_accounts,
        max_sessions=max_sessions,
        max_active_accounts=max_active_accounts,
        mfa_enabled=mfa_enabled,
        player_scout_access=bool(user.is_admin or (record and record.player_scout_access)),
    )


@router.get('/sessions')
def session_inventory(session=Depends(get_current_dashboard_session), sessions=Depends(get_dashboard_sessions)):
    return sessions.inventory(session.user_id, session.cache_key)


@router.delete('/sessions/{key}', status_code=204)
def revoke_session(
    key: str,
    request: Request,
    session=Depends(get_current_dashboard_session),
    sessions=Depends(get_dashboard_sessions),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    sessions.revoke(session.user_id, key)
    _audit(
        security,
        action='session.revoke',
        target_type='session',
        target_id=key,
        actor_user_id=session.user_id,
        actor_email=session.email,
        outcome='success',
        request=request,
    )


@router.post('/revoke-all', status_code=204)
def revoke_all(
    request: Request,
    response: Response,
    session=Depends(get_current_dashboard_session),
    sessions=Depends(get_dashboard_sessions),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    sessions.revoke(session.user_id)
    _clear_auth_cookies(response)
    _audit(
        security,
        action='session.revoke_all',
        target_type='user',
        target_id=str(session.user_id),
        actor_user_id=session.user_id,
        actor_email=session.email,
        outcome='success',
        request=request,
    )


@router.get('/mfa', response_model=MfaStatusResponse)
def mfa_status(admin=Depends(require_admin), security: AdminSecurityStore = Depends(get_admin_store)):
    return security.mfa_status(admin.id)


@router.post('/mfa/setup', response_model=MfaSetupResponse)
def mfa_setup(
    request: Request,
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    result = security.begin_mfa_setup(admin.id)
    _audit(
        security,
        action='mfa.setup_started',
        target_type='user',
        target_id=str(admin.id),
        actor_user_id=admin.id,
        actor_email=admin.email,
        outcome='success',
        request=request,
    )
    return result


@router.post('/mfa/enable', status_code=204)
def mfa_enable(
    body: MfaCodeRequest,
    request: Request,
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    security.enable_mfa(admin.id, body.code)
    _audit(
        security,
        action='mfa.enabled',
        target_type='user',
        target_id=str(admin.id),
        actor_user_id=admin.id,
        actor_email=admin.email,
        outcome='success',
        request=request,
    )


@router.post('/mfa/disable', status_code=204)
def mfa_disable(
    body: MfaCodeRequest,
    request: Request,
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    security.disable_mfa(admin.id, body.code)
    _audit(
        security,
        action='mfa.disabled',
        target_type='user',
        target_id=str(admin.id),
        actor_user_id=admin.id,
        actor_email=admin.email,
        outcome='success',
        request=request,
    )


@router.post('/pilot/grants', status_code=201)
def issue_grant(
    body: GrantRequest,
    request: Request,
    response: Response,
    user=Depends(require_admin),
    sessions=Depends(get_dashboard_sessions),
    repo=Depends(get_repository),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    sessions.throttle('grant-admin', user.id, limit=20, seconds=3600)
    response.headers['Cache-Control'] = 'no-store'
    grant = sessions.issue_grant(str(body.email), body.kind)
    repo.add_event(
        account_id=None,
        actor=f'user:{user.id}',
        event_type='pilot_grant_issued',
        detail={'email': str(body.email).lower(), 'kind': body.kind},
    )
    _audit(
        security,
        action='grant.issued',
        target_type='identity',
        target_id=str(body.email).lower(),
        actor_user_id=user.id,
        actor_email=user.email,
        outcome='success',
        request=request,
        detail={'kind': body.kind, 'expires_at': grant['expires_at'].isoformat()},
    )
    return grant


@router.post('/pilot/redeem', status_code=204)
def redeem_grant(
    body: RedeemRequest,
    request: Request,
    response: Response,
    sessions=Depends(get_dashboard_sessions),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    sessions.throttle('redeem-peer', request.client.host if request.client else 'unknown', limit=30, seconds=60)
    sessions.throttle('redeem-token', body.token, limit=5, seconds=900)
    sessions.redeem(body.token, body.password)
    response.headers['Cache-Control'] = 'no-store'
    _audit(
        security,
        action='grant.redeemed',
        target_type='grant',
        outcome='success',
        request=request,
        detail={'token_present': True},
    )


@router.post('/pilot/users/{user_id}/policy', status_code=204)
def update_user_policy(
    user_id: uuid.UUID,
    body: UserPolicyRequest,
    request: Request,
    admin=Depends(require_admin),
    sessions=Depends(get_dashboard_sessions),
    repo=Depends(get_repository),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    with request.app.state.lifecycle_lock:
        sessions.update_user(user_id, **body.model_dump())
        for account in repo.list_accounts(user_id):
            request.app.state.account_manager.pilot.revoke(str(account.id))
            if request.app.state.account_manager.get_account(str(account.id)) is not None:
                request.app.state.account_manager.stop(str(account.id))
        repo.add_event(
            account_id=None,
            actor=f'user:{admin.id}',
            event_type='user_policy_changed',
            detail={'user_id': str(user_id), **body.model_dump()},
        )
    _audit(
        security,
        action='user.policy_changed',
        target_type='user',
        target_id=str(user_id),
        actor_user_id=admin.id,
        actor_email=admin.email,
        outcome='success',
        request=request,
        detail=body.model_dump(),
    )
