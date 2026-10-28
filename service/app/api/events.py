"""Read-only access to account audit trails."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, Query

from app.db.repository import AccountRecord, AccountRepository
from app.deps import AuthenticatedUser, get_current_user, get_owned_account, get_repository
from app.schemas.accounts import AccountEventResponse, AccountEventWithLabelResponse

router = APIRouter(prefix='/accounts', tags=['events'])
global_router = APIRouter(tags=['events'])


@global_router.get('/events', response_model=List[AccountEventWithLabelResponse])
def list_all_events(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
) -> List[AccountEventWithLabelResponse]:
    """Recent events across accounts owned by the current dashboard user.

    Deleted-account audit rows intentionally remain outside this endpoint
    because their owner relationship no longer exists after ON DELETE SET NULL.
    """
    accounts = repo.list_accounts(owner_user_id=user.id)
    label_by_id = {account.id: account.label for account in accounts}
    events = repo.list_events_for_accounts(list(label_by_id), limit=limit, offset=offset)
    return [
        AccountEventWithLabelResponse(
            event=AccountEventResponse(**vars(event)),
            account_label=label_by_id.get(event.account_id) if event.account_id is not None else None,
        )
        for event in events
    ]


@router.get('/{account_id}/events', response_model=List[AccountEventResponse])
def list_events(
    account_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    account: AccountRecord = Depends(get_owned_account),
    repo: AccountRepository = Depends(get_repository),
) -> List[AccountEventResponse]:
    events = repo.list_events(account_id, limit=limit, offset=offset)
    return [AccountEventResponse(**vars(e)) for e in events]
