"""Account CRUD. Registering/removing a *persisted* account — connecting to
it lives in sessions.py, since that's a live-session operation against
AccountManager, not a database operation."""

from __future__ import annotations

import uuid
from typing import List, Literal
from pydantic import BaseModel

from fastapi import APIRouter, Depends

from app.core.account_manager import AccountManager
from app.db.repository import AccountRecord, AccountRepository
from app.deps import AuthenticatedUser, get_account_manager, get_current_user, get_owned_account, get_repository, require_admin
from app.schemas.accounts import AccountCreateRequest, AccountResponse
from app.schemas.sessions import AccountOverviewResponse, LiveSessionStatus, SessionStatusResponse

router = APIRouter(prefix='/accounts', tags=['accounts'])


def _to_response(account: AccountRecord) -> AccountResponse:
    return AccountResponse.model_validate(account, from_attributes=True)


@router.get('', response_model=List[AccountResponse])
def list_accounts(
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
) -> List[AccountResponse]:
    return [_to_response(a) for a in repo.list_accounts(owner_user_id=user.id)]


@router.post('', response_model=AccountResponse, status_code=201)
def create_account(
    body: AccountCreateRequest,
    user: AuthenticatedUser = Depends(require_admin),
    repo: AccountRepository = Depends(get_repository),
) -> AccountResponse:
    account = repo.create_account(
        owner_user_id=user.id,
        label=body.label,
        linked_email=body.linked_email,
        app_uid=body.app_uid,
        app_token=body.app_token,
        device_id=body.device_id,
        profile_uid=body.profile_uid,
        platform=body.platform,
        device_metadata=body.device_metadata.model_dump(),
        status=body.status,
    )
    repo.add_event(
        account_id=account.id,
        actor=f'user:{user.id}',
        event_type='account_created',
        detail={'label': account.label},
    )
    return _to_response(account)




@router.get('/overview', response_model=List[AccountOverviewResponse])
def accounts_overview(
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> List[AccountOverviewResponse]:
    """One owner-scoped request for account rows + live connection state.

    The Alliance dashboard previously issued GET /accounts and then one
    /status request per account every refresh cycle. Keep authorization and
    ownership semantics identical while making that view O(1) HTTP requests.
    """
    result: List[AccountOverviewResponse] = []
    for account in repo.list_accounts(owner_user_id=user.id):
        session = manager.get_account(str(account.id))
        live = LiveSessionStatus(**session.status()) if session is not None else None
        result.append(
            AccountOverviewResponse(
                account=_to_response(account),
                status=SessionStatusResponse(
                    account_id=account.id,
                    db_status=account.status,
                    live=live,
                ),
            )
        )
    return result


@router.get('/{account_id}', response_model=AccountResponse)
def get_account(account: AccountRecord = Depends(get_owned_account)) -> AccountResponse:
    return _to_response(account)


@router.delete('/{account_id}', status_code=204)
def delete_account(
    account_id: uuid.UUID,
    account: AccountRecord = Depends(get_owned_account),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
) -> None:
    # Stop and drop the live session first (no-op if none is registered),
    # then delete the persisted record. Order matters: we never want a
    # dangling AccountSession outliving its account row.
    if manager.get_account(str(account_id)) is not None:
        manager.remove_account(str(account_id))
    repo.add_event(
        account_id=account.id,
        actor=f'user:{user.id}',
        event_type='account_deleted',
        detail={'label': account.label},
    )
    repo.delete_account(account_id)


class AccountStatusRequest(BaseModel):
    status: Literal['active', 'disabled', 'restricted', 'needs_reauth']


@router.post('/{account_id}/status', response_model=AccountResponse)
def change_status(body: AccountStatusRequest, account: AccountRecord = Depends(get_owned_account),
                  user: AuthenticatedUser = Depends(require_admin), repo=Depends(get_repository),
                  manager=Depends(get_account_manager)):
    from app.security.identity import canonical_identity, AccountUnavailable
    if body.status == 'active' and canonical_identity(account.app_uid) is None:
        raise AccountUnavailable()
    # Commit the block before stopping runtime; failed persistence leaves the
    # previous policy intact. get_owned_account serializes all game commands.
    updated = repo.update_account(account.id, status=body.status)
    manager.pilot.revoke(str(account.id))
    if manager.get_account(str(account.id)) is not None:
        manager.stop(str(account.id))
    repo.add_event(account_id=account.id, actor=f'user:{user.id}', event_type='account_status_changed',
                   detail={'status': body.status})
    return _to_response(updated)
