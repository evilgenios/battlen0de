"""Mass-deploy: teleport several accounts near a player and join their
units to an Army Group. Ported from the legacy Discord bot's
`/mass_deploy` command.

IMPORTANT — history of what could be ported and when:
An earlier pass had only the Discord command wrapper as reference, whose
body called an undocumented `_run_mass_deploy()` helper not present
anywhere on this machine at the time — so that pass shipped only the fully
specified parts (validation, dry-run, locking, per-account results) and
left the actual game operation (teleport + AG-join) behind a
DeployExecutor that raised "not implemented" in execute mode, rather than
fabricate protobuf packets with no reference.

This pass received a newer, more complete reference bot (message (1).py)
that DOES include the real `_run_mass_deploy` body, the real
GROUP_ARMY_LAND=10001 / GROUP_ARMY_NAVY=10002 enum values, and the real
teleport/AG-join WarpathConnection methods (send_teleport_mainbase,
send_build_mainbase, send_join_group_army — now ported onto
app/core/warpath/connection.py and verified against the vendored protobuf
schema, field by field, before use). Execute mode is therefore now
genuinely implemented — see app/core/warpath/mass_deploy_ops.py for the
ported placement/AG-join algorithm — not merely un-blocked without cause.

Deliberately NOT copied from the reference: it spawns its own unmanaged
WarpathConnection per account and waits for it to log in — the
global/legacy pattern this project has consistently rejected. Here, execute
mode only ever operates on a session AccountManager already owns and has
already authenticated; a disconnected target simply fails for itself
(same rule every other account action already follows), never triggering a
new connection on this module's own initiative.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import List, Optional, Protocol

from .warpath.mass_deploy_ops import GROUP_ARMY_LAND, GROUP_ARMY_NAVY, deploy_one_account

GROUP_TYPE_VALUES = {'auto': 0, 'land': GROUP_ARMY_LAND, 'navy': GROUP_ARMY_NAVY}


class MassDeployValidationError(ValueError):
    pass


def parse_positive_decimal(value: str, field_name: str) -> int:
    text = str(value).strip()
    if not re.fullmatch(r'[0-9]+', text) or int(text) <= 0:
        raise MassDeployValidationError(f'{field_name} must be a positive whole number.')
    return int(text)


def parse_army_ids(value: str) -> Optional[List[int]]:
    """None means "auto" — all equipped slots for the detected AG type."""
    text = str(value).strip().lower()
    if text == 'auto':
        return None
    slots = [part.strip() for part in text.split(',')]
    if not slots or any(not slot for slot in slots):
        raise MassDeployValidationError('army_ids must be "auto" or a comma-separated list of slot numbers.')
    parsed: List[int] = []
    for slot in slots:
        if not re.fullmatch(r'[0-9]+', slot) or int(slot) <= 0:
            raise MassDeployValidationError(f'invalid army slot: {slot!r}')
        parsed.append(int(slot))
    return parsed


def parse_group_type(value: str) -> int:
    key = str(value).strip().lower()
    if key not in GROUP_TYPE_VALUES:
        raise MassDeployValidationError('group_type must be auto, land, or navy.')
    return GROUP_TYPE_VALUES[key]


class DeployExecutor(Protocol):
    """One method, covering the whole per-account operation (position
    lookup, AG validation, placement, AG join) — see mass_deploy_ops.py.
    Tests inject a fake implementing just this one method."""

    def deploy(
        self, connection, *, ag_id: int, player_uid: int, army_ids: Optional[List[int]], group_type: int,
        cancel_event, position_index: int,
    ) -> dict: ...


class RealDeployExecutor:
    """Production executor: calls the real, ported placement/AG-join
    algorithm against an already-connected WarpathConnection."""

    def deploy(self, connection, *, ag_id, player_uid, army_ids, group_type, cancel_event, position_index) -> dict:
        return deploy_one_account(
            connection, ag_id=ag_id, player_uid=player_uid, army_ids=army_ids, group_type=group_type,
            cancel_event=cancel_event, position_index=position_index,
        )


DEFAULT_EXECUTOR: DeployExecutor = RealDeployExecutor()


class MassDeployLock:
    """One process-wide lock so two mass deployments can never run
    concurrently — mirrors the legacy bot's asyncio.Lock, ported to a
    plain threading.Lock since this service is synchronous/threaded.

    Also owns the cancellation signal for the run currently holding the
    lock (see api/mass_deploy.py's /mass-cancel): a fresh threading.Event
    is created on every successful acquire, so a stale cancellation from a
    PREVIOUS run can never leak into the next one."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancel_event: Optional[threading.Event] = None

    def try_acquire(self) -> bool:
        acquired = self._lock.acquire(blocking=False)
        if acquired:
            self._cancel_event = threading.Event()
        return acquired

    def release(self) -> None:
        self._cancel_event = None
        try:
            self._lock.release()
        except RuntimeError:
            pass

    def request_cancel(self) -> bool:
        """Returns True iff a run was actually in progress and got signalled
        — never claims a cancellation happened for a run that was never
        running (see /mass-cancel's "does not pretend" requirement)."""
        event = self._cancel_event
        if event is None:
            return False
        event.set()
        return True

    @property
    def cancel_event(self) -> Optional[threading.Event]:
        return self._cancel_event

    @property
    def locked(self) -> bool:
        return self._lock.locked()


@dataclass
class DeployTarget:
    account_id: str
    label: str
    session: object  # AccountSession-like: .is_active, .connection.authenticated, .connection


def run_mass_deploy(
    targets: List[DeployTarget],
    *,
    ag_id: int,
    player_uid: int,
    army_ids: Optional[List[int]],
    group_type: int,
    execute: bool,
    executor: DeployExecutor = DEFAULT_EXECUTOR,
    cancel_event=None,
) -> List[dict]:
    """Dry run (execute=False) sends NO game requests at all — it never
    touches a session or the executor. Execute mode requires each target's
    session to already be connected/authenticated (same rule as the other
    account actions); a disconnected account fails only for itself, never
    aborting the rest of the batch. position_index is threaded across the
    whole batch (matching the reference) so accounts land on distinct
    nearby footprints instead of colliding on the same one."""
    results: List[dict] = []
    position_index = 0
    for target in targets:
        if not execute:
            results.append({
                'account_id': target.account_id, 'label': target.label,
                'teleport': 'skipped (dry run)', 'ag': 'skipped (dry run)', 'error': None,
            })
            continue

        if cancel_event is not None and cancel_event.is_set():
            results.append({
                'account_id': target.account_id, 'label': target.label,
                'teleport': 'cancelled', 'ag': 'cancelled', 'error': 'cancelled before this account started',
            })
            continue

        session = target.session
        if session is None or not session.is_active or not session.connection.authenticated:
            results.append({
                'account_id': target.account_id, 'label': target.label,
                'teleport': 'failed', 'ag': 'failed', 'error': 'account is not connected',
            })
            continue

        row = {'account_id': target.account_id, 'label': target.label, 'error': None}
        try:
            outcome = executor.deploy(
                session.connection, ag_id=ag_id, player_uid=player_uid, army_ids=army_ids,
                group_type=group_type, cancel_event=cancel_event, position_index=position_index,
            )
            row['teleport'] = outcome.get('teleport', 'failed')
            row['ag'] = outcome.get('ag', 'failed')
            if outcome.get('error'):
                row['error'] = outcome['error']
            position_index = outcome.get('position_index', position_index)
        except Exception as exc:  # noqa: BLE001 - one account's failure must never affect the rest
            row.setdefault('teleport', 'failed')
            row.setdefault('ag', 'failed')
            row['error'] = str(exc)
        results.append(row)
    return results
