"""Operator grants never connect or resolve commands; reports never send."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.account_manager import AccountManager
from app.core.pilot_activation import PilotBlocked
from app.db.repository import AccountRecord, AccountRepository
from app.deps import (AuthenticatedUser, get_account_manager, get_current_user,
                      get_owned_account, get_repository, require_admin)

router = APIRouter(prefix='/accounts', tags=['pilot'])


class ActivationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['observe', 'automatic']
    minutes: int = Field(default=15, strict=True, ge=1, le=60)


class ActivationStatus(BaseModel):
    mode: Literal['off', 'observe']
    reason: Literal['not_activated', 'expired', 'operator_grant', 'customer_mode']
    instance_id: str
    issued_by: str | None
    issued_at: float | None
    expires_at: float | None
    automatic_actions: Literal[False] = False
    game_actions: Literal[False] = False
    upstream_evidence: Literal['unverified'] = 'unverified'
    restart_policy: Literal['off', 'auto'] = 'off'


@router.get('/{account_id}/pilot-activation', response_model=ActivationStatus)
def pilot_status(account_id: uuid.UUID, account: AccountRecord = Depends(get_owned_account),
                 manager: AccountManager = Depends(get_account_manager)):
    return manager.pilot.status(str(account_id))


@router.post('/{account_id}/pilot-activation', response_model=ActivationStatus,
             dependencies=[Depends(require_admin)])
def activate(account_id: uuid.UUID, body: ActivationRequest,
             account: AccountRecord = Depends(get_owned_account),
             user: AuthenticatedUser = Depends(get_current_user),
             repo: AccountRepository = Depends(get_repository),
             manager: AccountManager = Depends(get_account_manager)):
    if body.mode == 'automatic':
        manager.pilot.require_actions()
    session = manager.get_account(str(account_id))
    if session is not None and not session.is_quiescent:
        raise PilotBlocked('pause the current session and wait for it to stop before granting observation')
    if session is not None and any(row['kind'] in ('collect', 'search', 'gather')
                                   for row in session.connection.reply_actions.operational_status()['active']):
        raise PilotBlocked('unresolved command observations remain; activation cannot clear reservations')
    # Revoke any old grant first. Audit failure must leave the account off.
    manager.pilot.revoke(str(account_id))
    repo.add_event(account_id=account_id, actor=f'user:{user.id}',
                   event_type='pilot_observation_authorized',
                   detail={'minutes': body.minutes, 'instance_id': manager.pilot.instance_id})
    manager.pilot.activate(str(account_id), str(user.id), body.minutes)
    return manager.pilot.status(str(account_id))


@router.post('/{account_id}/pilot-pause', response_model=ActivationStatus)
def pause(account_id: uuid.UUID, account: AccountRecord = Depends(get_owned_account),
          user: AuthenticatedUser = Depends(get_current_user),
          repo: AccountRepository = Depends(get_repository),
          manager: AccountManager = Depends(get_account_manager)):
    manager.pilot.revoke(str(account_id))
    session = manager.get_account(str(account_id))
    if session is not None:
        manager.stop(str(account_id))
    # A failed audit write must never undo containment.
    repo.add_event(account_id=account_id, actor=f'user:{user.id}', event_type='pilot_paused',
                   detail={'instance_id': manager.pilot.instance_id})
    return manager.pilot.status(str(account_id))
