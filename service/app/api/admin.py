"""Administrator control center.

Every route requires the explicit admin role. These endpoints never return
Warpath app tokens, device IDs, password hashes, MFA secrets, session tokens,
or raw database credentials.
"""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.db.admin_store import AdminSecurityStore
from app.db.repository import AccountRepository
from app.deps import (
    get_account_manager,
    get_admin_store,
    get_dashboard_sessions,
    get_repository,
    require_admin,
)
from app.schemas.admin import (
    AdminAccountEventResponse,
    AdminAccountResponse,
    AdminAccountStatusPatch,
    AdminAuditResponse,
    AdminSummaryResponse,
    AdminUserPolicyPatch,
    AdminUserResponse,
)

router = APIRouter(prefix='/admin', tags=['admin'])


def _live_state(manager, account_id: uuid.UUID) -> tuple[str | None, bool]:
    session = manager.get_account(str(account_id))
    if session is None:
        return None, False
    status = session.status()
    return status.get('state'), bool(status.get('authenticated'))


def _audit(security: AdminSecurityStore, request: Request, admin, **kwargs) -> None:
    security.audit(
        actor_user_id=admin.id,
        actor_email=admin.email,
        request=request,
        **kwargs,
    )


@router.get('/summary', response_model=AdminSummaryResponse)
def summary(
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
    repo: AccountRepository = Depends(get_repository),
    sessions=Depends(get_dashboard_sessions),
    manager=Depends(get_account_manager),
):
    users = security.list_users(limit=10_000)
    accounts = repo.list_accounts()
    connected = 0
    for account in accounts:
        session = manager.get_account(str(account.id))
        if session is not None and session.is_active:
            connected += 1
    return AdminSummaryResponse(
        users_total=len(users),
        users_active=sum(row['status'] == 'active' for row in users),
        users_disabled=sum(row['status'] == 'disabled' for row in users),
        accounts_total=len(accounts),
        accounts_connected=connected,
        active_web_sessions=sessions.active_count(),
        alliance_users=sum(row['plan'] == 'alliance' for row in users),
        individual_users=sum(row['plan'] == 'individual' for row in users),
    )


@router.get('/users', response_model=List[AdminUserResponse])
def users(
    q: str = Query(default='', max_length=320),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    return security.list_users(query=q, limit=limit, offset=offset)


@router.patch('/users/{user_id}', response_model=AdminUserResponse)
def update_user(
    user_id: uuid.UUID,
    body: AdminUserPolicyPatch,
    request: Request,
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
    sessions=Depends(get_dashboard_sessions),
    repo: AccountRepository = Depends(get_repository),
):
    if user_id == admin.id and body.status != 'active':
        raise HTTPException(409, 'an administrator cannot disable their own active identity')

    with request.app.state.lifecycle_lock:
        sessions.update_user(user_id, **body.model_dump())
        for account in repo.list_accounts(user_id):
            request.app.state.account_manager.pilot.revoke(str(account.id))
            if request.app.state.account_manager.get_account(str(account.id)) is not None:
                request.app.state.account_manager.stop(str(account.id))

    _audit(
        security,
        request,
        admin,
        action='admin.user_policy_updated',
        target_type='user',
        target_id=str(user_id),
        outcome='success',
        detail=body.model_dump(),
    )

    rows = [row for row in security.list_users(limit=500) if row['id'] == str(user_id)]
    if not rows:
        raise HTTPException(404, 'user not found')
    return rows[0]


@router.post('/users/{user_id}/revoke-sessions', status_code=204)
def revoke_user_sessions(
    user_id: uuid.UUID,
    request: Request,
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
    sessions=Depends(get_dashboard_sessions),
):
    if user_id == admin.id:
        raise HTTPException(409, 'use your own session controls to revoke the current administrator')
    sessions.revoke(user_id)
    _audit(
        security,
        request,
        admin,
        action='admin.user_sessions_revoked',
        target_type='user',
        target_id=str(user_id),
        outcome='success',
    )


@router.get('/accounts', response_model=List[AdminAccountResponse])
def accounts(
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
    repo: AccountRepository = Depends(get_repository),
    manager=Depends(get_account_manager),
):
    user_map = {row['id']: row['email'] for row in security.list_users(limit=10_000)}
    result = []
    for account in repo.list_accounts():
        state, authenticated = _live_state(manager, account.id)
        result.append(
            AdminAccountResponse(
                id=str(account.id),
                owner_user_id=str(account.owner_user_id),
                owner_email=user_map.get(str(account.owner_user_id), 'unknown'),
                label=account.label,
                app_uid=account.app_uid,
                linked_email=account.linked_email,
                status=account.status,
                live_state=state,
                authenticated=authenticated,
                last_connected_at=account.last_connected_at,
            )
        )
    return result


@router.patch('/accounts/{account_id}', response_model=AdminAccountResponse)
def update_account(
    account_id: uuid.UUID,
    body: AdminAccountStatusPatch,
    request: Request,
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
    repo: AccountRepository = Depends(get_repository),
    manager=Depends(get_account_manager),
):
    account = repo.get_account(account_id)
    if account is None:
        raise HTTPException(404, 'account not found')

    with request.app.state.lifecycle_lock:
        if body.status != 'active':
            manager.pilot.revoke(str(account_id))
            if manager.get_account(str(account_id)) is not None:
                manager.stop(str(account_id))
        updated = repo.update_account(account_id, status=body.status)

    owner = repo.get_user_by_id(account.owner_user_id)
    state, authenticated = _live_state(manager, account_id)
    _audit(
        security,
        request,
        admin,
        action='admin.account_status_updated',
        target_type='account',
        target_id=str(account_id),
        outcome='success',
        detail={'status': body.status, 'owner_user_id': str(account.owner_user_id)},
    )
    return AdminAccountResponse(
        id=str(updated.id),
        owner_user_id=str(updated.owner_user_id),
        owner_email=owner.email if owner else 'unknown',
        label=updated.label,
        app_uid=updated.app_uid,
        linked_email=updated.linked_email,
        status=updated.status,
        live_state=state,
        authenticated=authenticated,
        last_connected_at=updated.last_connected_at,
    )


@router.post('/accounts/{account_id}/disconnect', status_code=204)
def disconnect_account(
    account_id: uuid.UUID,
    request: Request,
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
    repo: AccountRepository = Depends(get_repository),
    manager=Depends(get_account_manager),
):
    account = repo.get_account(account_id)
    if account is None:
        raise HTTPException(404, 'account not found')
    with request.app.state.lifecycle_lock:
        manager.pilot.revoke(str(account_id))
        session = manager.get_account(str(account_id))
        if session is not None and session.is_active:
            manager.stop(str(account_id))
    _audit(
        security,
        request,
        admin,
        action='admin.account_disconnected',
        target_type='account',
        target_id=str(account_id),
        outcome='success',
        detail={'owner_user_id': str(account.owner_user_id)},
    )


@router.get('/audit', response_model=List[AdminAuditResponse])
def audit(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, max_length=96),
    outcome: str | None = Query(default=None, max_length=16),
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
):
    return security.list_audit(limit=limit, offset=offset, action=action, outcome=outcome)


@router.get('/account-events', response_model=List[AdminAccountEventResponse])
def account_events(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    admin=Depends(require_admin),
    security: AdminSecurityStore = Depends(get_admin_store),
    repo: AccountRepository = Depends(get_repository),
):
    accounts = repo.list_accounts()
    owner_map = {row['id']: row['email'] for row in security.list_users(limit=10_000)}
    account_map = {account.id: account for account in accounts}
    rows = repo.list_events_for_accounts([account.id for account in accounts], limit=limit, offset=offset)
    return [
        AdminAccountEventResponse(
            id=row.id,
            account_id=str(row.account_id) if row.account_id else None,
            account_label=account_map[row.account_id].label if row.account_id in account_map else None,
            owner_email=owner_map.get(str(account_map[row.account_id].owner_user_id)) if row.account_id in account_map else None,
            actor=row.actor,
            event_type=row.event_type,
            detail=row.detail,
            created_at=row.created_at,
        )
        for row in rows
    ]
