"""FastAPI app: the ONE process-wide AccountManager lives here, built once
at startup and handed to every request via app.state (see deps.py).

    FastAPI  ->  AccountManager  ->  AccountSession  ->  WarpathConnection

No second AccountManager, no second DB engine, anywhere in this codebase.

This module is meant to run as a long-lived worker process (uvicorn with a
persistent host, not a serverless function) — see the "Important
architecture rule" in the Stage 3 report and the module docstring of
app/core/account_manager.py. Long-lived Warpath TCP connections live in
AccountSession's background threads for the lifetime of this process.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
import threading
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.security.auth_config import local_auth_enabled
from sqlalchemy import text
from app.security.identity import IdentityConflict, AccountLimitReached, AccountUnavailable

from app.api import accounts, actions, admin, auth, conquest_guard, diagnostics, events, intel, link, marketplace, mass_deploy, pilot, sessions
from app.core.pilot_activation import PilotBlocked, validate_pilot_configuration
from app.core.account_manager import AccountManager
from app.core.account_session import SessionEvent
from app.db.identity_store import PostgresIdentityStore
from app.db.admin_store import AdminSecurityStore
from app.db.marketplace import MarketplaceStore
from app.core.link_challenge_store import LinkChallengeStore
from app.core.mass_deploy import MassDeployLock
from app.db.repository import SqlAlchemyAccountRepository
from app.db.session import _load_local_dotenv, build_engine, build_session_factory
from app.deps import enforce_product_rate_limit, require_dashboard_auth

logger = logging.getLogger('warpath.service')

MAX_CONCURRENT_SESSIONS_ENV_VAR = 'MAX_CONCURRENT_SESSIONS'
SNAPSHOT_INTERVAL_ENV_VAR = 'SNAPSHOT_PERSIST_INTERVAL_SECONDS'


def _validate_internal_proxy_configuration() -> None:
    production = os.environ.get('APP_ENV', 'production').strip().lower() == 'production'
    token = os.environ.get('INTERNAL_PROXY_TOKEN', '').strip()
    if production and len(token) < 32:
        raise RuntimeError('Production requires INTERNAL_PROXY_TOKEN with at least 32 characters')

_SESSION_EVENT_TYPE = {
    'connected': 'account_connected',
    'disconnected': 'account_disconnected',
    'auth_failed': 'account_auth_failed',
    'restricted': 'account_restricted',
    'reconnecting': 'account_reconnect_started',
    'stopped': 'account_stopped',
}


def _make_event_sink(repo: SqlAlchemyAccountRepository):
    """Bridges AccountSession/AccountManager's on_event callback (Stage 1/2,
    unchanged) to the account_events table. Runs on whatever background
    thread the session's supervisor loop is on — AccountSession already
    swallows exceptions from this callback, but we don't want a slow/failing
    DB write to be the norm, either, so this stays a single small insert."""

    def _sink(event: SessionEvent) -> None:
        try:
            account_uuid = uuid.UUID(event.account_id)
        except ValueError:
            account_uuid = None
        event_type = _SESSION_EVENT_TYPE.get(event.kind, f'account_{event.kind}')
        try:
            repo.add_event(
                account_id=account_uuid,
                actor='system',
                event_type=event_type,
                detail={'detail': event.detail},
            )
            if event.kind in ('auth_failed', 'restricted') and account_uuid is not None:
                repo.mark_account_auth_failure(account_uuid, restricted=event.kind == 'restricted')
            if event.kind == 'connected' and account_uuid is not None:
                repo.update_account(account_uuid, last_connected_at=datetime.now(timezone.utc))
        except Exception:
            logger.exception('failed to persist account_event for %s', event.account_id)

    return _sink


async def _persist_snapshots_periodically(
    manager: AccountManager,
    repo: SqlAlchemyAccountRepository,
    interval_seconds: float,
    identity=None,
    admin_store=None,
) -> None:
    """Keeps high-frequency protocol state in memory (account_snapshot on
    each WarpathConnection) and only periodically writes a summary to
    Postgres — never persists raw inbound packets."""
    while True:
        await asyncio.sleep(interval_seconds)
        if identity is not None:
            try:
                await asyncio.to_thread(identity.cleanup)
            except Exception:
                logger.warning('identity retention cleanup unavailable')
        if admin_store is not None:
            try:
                await asyncio.to_thread(admin_store.cleanup)
            except Exception:
                logger.warning('admin audit retention cleanup unavailable')
        for status in manager.list_accounts():
            account_id = status['account_id']
            session = manager.get_account(account_id)
            if session is None or not session.connection.authenticated:
                continue
            try:
                account_uuid = uuid.UUID(account_id)
                snapshot = dict(session.connection.account_snapshot)
                await asyncio.to_thread(repo.save_snapshot, account_uuid, snapshot)
            except Exception:
                logger.exception('failed to persist snapshot for %s', account_id)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _load_local_dotenv()
    _validate_internal_proxy_configuration()
    local_auth_enabled()  # Also validate .env configuration before any DB/game I/O.
    validate_pilot_configuration()
    engine = build_engine()
    session_factory = build_session_factory(engine)
    repo = SqlAlchemyAccountRepository(session_factory)

    max_sessions = int(os.environ.get(MAX_CONCURRENT_SESSIONS_ENV_VAR, '5'))
    manager = AccountManager(max_concurrent_sessions=max_sessions, on_event=_make_event_sink(repo))

    app.state.engine = engine
    app.state.repository = repo
    app.state.account_manager = manager
    # In-memory only, by design — see link_challenge_store.py's module
    # docstring for why this never touches Postgres.
    app.state.link_challenges = LinkChallengeStore()
    app.state.mass_deploy_lock = MassDeployLock()
    app.state.dashboard_sessions = PostgresIdentityStore(session_factory)
    app.state.admin_store = AdminSecurityStore(session_factory)
    app.state.marketplace_store = MarketplaceStore(session_factory)

    # Registration loads credentials but never grants permission or connects.
    for record in repo.list_accounts():
        owner = repo.get_user_by_id(record.owner_user_id)
        if record.status != 'active' or owner is None or owner.status != 'active':
            continue
        credentials = repo.get_credentials(record.id)
        if credentials is None:
            continue
        manager.add_account(credentials)

    snapshot_interval = float(os.environ.get(SNAPSHOT_INTERVAL_ENV_VAR, '60'))
    snapshot_task = asyncio.create_task(
        _persist_snapshots_periodically(
            manager,
            repo,
            snapshot_interval,
            app.state.dashboard_sessions,
            app.state.admin_store,
        )
    )

    try:
        yield
    finally:
        snapshot_task.cancel()
        manager.stop_all()
        engine.dispose()


def create_app(*, lifespan_context=None) -> FastAPI:
    """Builds the FastAPI app: routers + exception handler + /health.
    Deliberately takes NO position on app.state.repository/account_manager/
    engine — those are set either by `lifespan` (production, below) or
    directly by a test fixture (tests/fake_repository.py's
    build_test_app()), which passes lifespan_context=None and assigns
    app.state.* itself so FastAPI-layer tests never need a real database.
    Either way, there is exactly one code path that defines the routes."""
    local_auth_enabled()  # Reject unsafe configuration before connecting to the database.
    validate_pilot_configuration()
    production = os.environ.get('APP_ENV', 'production').strip().lower() == 'production'
    application = FastAPI(
        title='BattleN0de Account Service',
        lifespan=lifespan_context,
        docs_url=None if production else '/docs',
        redoc_url=None if production else '/redoc',
        openapi_url=None if production else '/openapi.json',
    )
    application.state.lifecycle_lock = threading.Lock()

    @application.middleware('http')
    async def internal_proxy_boundary(request: Request, call_next):
        expected = os.environ.get('INTERNAL_PROXY_TOKEN', '').strip()
        if expected and request.url.path != '/health':
            supplied = request.headers.get('x-battlenode-internal-token', '')
            if not supplied or not secrets.compare_digest(supplied, expected):
                return JSONResponse(status_code=403, content={'detail': 'internal proxy authentication required'})
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    # Login establishes a session; every product router authenticates independently.
    application.include_router(auth.router)
    application.include_router(marketplace.router)
    protected = Depends(require_dashboard_auth)
    product_limit = Depends(enforce_product_rate_limit)
    application.include_router(admin.router, dependencies=[protected, product_limit])
    application.include_router(events.global_router, dependencies=[protected, product_limit])
    application.include_router(accounts.router, dependencies=[protected, product_limit])
    application.include_router(link.router, dependencies=[protected, product_limit])
    application.include_router(sessions.router, dependencies=[protected, product_limit])
    application.include_router(pilot.router, dependencies=[protected, product_limit])
    application.include_router(actions.router, dependencies=[protected, product_limit])
    application.include_router(mass_deploy.router, dependencies=[protected, product_limit])
    application.include_router(events.router, dependencies=[protected, product_limit])
    application.include_router(intel.router, dependencies=[protected, product_limit])
    application.include_router(conquest_guard.router, dependencies=[protected, product_limit])
    application.include_router(diagnostics.router, dependencies=[protected, product_limit])

    @application.exception_handler(PilotBlocked)
    async def _pilot_blocked(request, exc):
        return JSONResponse(status_code=409, content={'detail': str(exc)})

    @application.exception_handler(IdentityConflict)
    async def _identity_conflict(request, exc):
        return JSONResponse(status_code=409, content={'detail': 'game identity is already linked or does not match the relink target'})

    @application.exception_handler(AccountLimitReached)
    async def _account_limit(request, exc):
        return JSONResponse(status_code=409, content={'detail': 'linked account limit reached'})

    @application.exception_handler(AccountUnavailable)
    async def _account_unavailable(request, exc):
        return JSONResponse(status_code=409, content={'detail': 'account identity or status is unavailable'})

    @application.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic includes rejected input by default (including passwords/codes).
        errors = [{'loc': e['loc'], 'msg': e['msg'], 'type': e['type']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'detail': errors})

    @application.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Defense in depth: whatever this exception is, its raw text never
        # reaches the client — only route handlers that deliberately
        # construct a redacted message do. See
        # app.core.warpath.credentials.redact_secrets for how every route
        # that touches WarpathConnection sanitizes errors.
        logger.exception('unhandled exception')
        return JSONResponse(status_code=500, content={'detail': 'internal server error'})

    @application.get('/health')
    def health(request: Request) -> dict:
        engine = request.app.state.engine
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
        except Exception:
            raise HTTPException(status_code=503, detail='database unreachable')

        auth_required = not local_auth_enabled()
        return {'status': 'ok', 'database': 'ok', 'auth_required': auth_required}

    return application


app = create_app(lifespan_context=lifespan)
