"""POST /accounts/mass-deploy: teleport several stored accounts near a
player and join their units to an Army Group, and POST
/accounts/mass-deploy/cancel to signal an in-flight run to stop. See
app/core/mass_deploy.py's module docstring for the real vs. ported-only
history of this feature.

Inherently multi-account, unlike the single-account routes in actions.py —
callers must pass explicit account_ids they own; there is no "every stored
account" fallback (that was the legacy bot's global-state behavior, and is
exactly the footgun this route avoids).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core import mass_deploy as mass_deploy_core
from app.core.account_manager import AccountManager
from app.core.mass_deploy import (
    DeployTarget,
    MassDeployLock,
    MassDeployValidationError,
    parse_army_ids,
    parse_group_type,
    parse_positive_decimal,
)
from app.db.repository import AccountRepository
from app.deps import AuthenticatedUser, get_account_manager, get_current_user, get_mass_deploy_lock, get_repository, require_admin
from app.schemas.mass_deploy import MassDeployAccountResult, MassDeployRequest, MassDeployResponse

router = APIRouter(prefix='/accounts', tags=['mass-deploy'], dependencies=[Depends(require_admin)])


@router.post('/mass-deploy', response_model=MassDeployResponse, status_code=200)
def mass_deploy(
    body: MassDeployRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: AccountRepository = Depends(get_repository),
    manager: AccountManager = Depends(get_account_manager),
    lock: MassDeployLock = Depends(get_mass_deploy_lock),
) -> MassDeployResponse:
    try:
        parsed_ag_id = parse_positive_decimal(body.ag_id, 'ag_id')
        parsed_player_uid = parse_positive_decimal(body.player_uid, 'player_uid')
        parsed_army_ids = parse_army_ids(body.army_ids)
        parsed_group_type = parse_group_type(body.group_type)
    except MassDeployValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Explicit account IDs only — never "every stored account". Ownership
    # is enforced per account, same 404/403 semantics as get_owned_account.
    targets: list[DeployTarget] = []
    for raw_id in body.account_ids:
        try:
            account_id = uuid.UUID(raw_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f'invalid account id: {raw_id!r}') from exc
        account = repo.get_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail=f'account not found: {raw_id}')
        if account.owner_user_id != user.id and not user.is_admin:
            raise HTTPException(status_code=403, detail=f'account does not belong to the caller: {raw_id}')
        owner = repo.get_user_by_id(account.owner_user_id)
        if account.status != 'active' or owner is None or owner.status != 'active':
            raise HTTPException(409, 'account unavailable for mass deployment')
        targets.append(DeployTarget(
            account_id=str(account.id), label=account.label, session=manager.get_account(str(account.id)),
        ))

    class PolicyExecutor:
        def deploy(self, connection, **kwargs):
            # Status changes cannot interleave one account's deployment.
            # Cancel remains independent and can still signal this operation.
            with request.app.state.lifecycle_lock:
                target = next(t for t in targets if t.session and t.session.connection is connection)
                current = repo.get_account(uuid.UUID(target.account_id))
                owner = repo.get_user_by_id(current.owner_user_id) if current else None
                if current is None or current.status != 'active' or owner is None or owner.status != 'active':
                    return {'teleport': 'failed', 'ag': 'failed', 'error': 'account unavailable'}
                return mass_deploy_core.DEFAULT_EXECUTOR.deploy(connection, **kwargs)

    if body.execute:
        manager.pilot.require_actions()

    if not body.execute:
        results = mass_deploy_core.run_mass_deploy(
            targets, ag_id=parsed_ag_id, player_uid=parsed_player_uid,
            army_ids=parsed_army_ids, group_type=parsed_group_type, execute=False,
            executor=mass_deploy_core.DEFAULT_EXECUTOR,
        )
    else:
        if not lock.try_acquire():
            raise HTTPException(status_code=409, detail='another mass deployment is already running')
        try:
            results = mass_deploy_core.run_mass_deploy(
                targets, ag_id=parsed_ag_id, player_uid=parsed_player_uid,
                army_ids=parsed_army_ids, group_type=parsed_group_type, execute=True,
                executor=PolicyExecutor(), cancel_event=lock.cancel_event,
            )
        finally:
            lock.release()

        repo.add_event(
            account_id=None,
            actor=f'user:{user.id}',
            event_type='mass_deploy_executed',
            detail={'ag_id': body.ag_id, 'player_uid': body.player_uid, 'account_count': len(targets)},
        )

    # A fully completed account is reported as "success: ..." for BOTH
    # teleport and ag (see mass_deploy_ops.deploy_one_account) — a dry run's
    # "skipped (dry run)" and any "unconfirmed"/"failed"/"cancelled" text
    # deliberately do not count.
    complete_count = sum(
        1 for row in results
        if str(row['teleport']).startswith('success') and str(row['ag']).startswith('success')
    )
    army_ids_text = 'auto' if parsed_army_ids is None else ','.join(str(v) for v in parsed_army_ids)

    return MassDeployResponse(
        execute=body.execute,
        ag_id=body.ag_id,
        player_uid=body.player_uid,
        army_ids=army_ids_text,
        group_type=body.group_type,
        results=[MassDeployAccountResult(**row) for row in results],
        complete_count=complete_count,
        total_count=len(targets),
    )


@router.post('/mass-deploy/cancel', status_code=200)
def mass_cancel(
    lock: MassDeployLock = Depends(get_mass_deploy_lock),
) -> dict:
    """Signals the currently-running mass deployment (if any) to stop after
    its current in-flight request — it can never claim to have cancelled a
    request that was already accepted by the Warpath server, only that a
    stop was requested. Never starts anything itself."""
    if not lock.locked:
        return {'cancelled': False, 'detail': 'no mass deployment is currently running'}
    signalled = lock.request_cancel()
    return {
        'cancelled': signalled,
        'detail': 'cancellation requested; no further accounts will start' if signalled
        else 'no mass deployment is currently running',
    }
