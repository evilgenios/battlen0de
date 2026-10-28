"""Pure validation/orchestration tests for app/core/mass_deploy.py — no
FastAPI, no sockets, no real Warpath connection anywhere. See
tests/test_mass_deploy_ops.py for the real placement/AG-join algorithm's
own tests (deploy_one_account)."""

from __future__ import annotations

import pytest

from app.core.mass_deploy import (
    DeployTarget,
    MassDeployValidationError,
    parse_army_ids,
    parse_group_type,
    parse_positive_decimal,
    run_mass_deploy,
)
from app.core.warpath.mass_deploy_ops import GROUP_ARMY_LAND, GROUP_ARMY_NAVY


def test_parse_positive_decimal_accepts_digits():
    assert parse_positive_decimal('12345', 'ag_id') == 12345


@pytest.mark.parametrize('value', ['-1', '0', 'abc', '1.5', ''])
def test_parse_positive_decimal_rejects_invalid(value):
    with pytest.raises(MassDeployValidationError):
        parse_positive_decimal(value, 'ag_id')


def test_parse_army_ids_auto_means_none():
    assert parse_army_ids('auto') is None
    assert parse_army_ids('AUTO') is None


def test_parse_army_ids_parses_comma_separated_slots():
    assert parse_army_ids('1,2,3,4,5') == [1, 2, 3, 4, 5]


@pytest.mark.parametrize('value', ['', '1,,2', '1,-2', '1,abc'])
def test_parse_army_ids_rejects_invalid(value):
    with pytest.raises(MassDeployValidationError):
        parse_army_ids(value)


def test_parse_group_type_mapping_uses_the_real_client_enum_values():
    """10001/10002 come from the latest reference client — not placeholders
    (see app/core/warpath/mass_deploy_ops.py's module docstring)."""
    assert parse_group_type('auto') == 0
    assert parse_group_type('land') == GROUP_ARMY_LAND == 10001
    assert parse_group_type('navy') == GROUP_ARMY_NAVY == 10002


def test_parse_group_type_rejects_unknown():
    with pytest.raises(MassDeployValidationError):
        parse_group_type('air')


def test_dry_run_sends_zero_requests():
    """Dry run must never touch the session or the executor at all."""

    class ExplodingExecutor:
        def deploy(self, *a, **k):
            raise AssertionError('dry run must never call the executor')

    targets = [DeployTarget(account_id='a1', label='Acc 1', session=None)]
    results = run_mass_deploy(
        targets, ag_id=1, player_uid=2, army_ids=None, group_type=0,
        execute=False, executor=ExplodingExecutor(),
    )
    assert results == [{'account_id': 'a1', 'label': 'Acc 1', 'teleport': 'skipped (dry run)', 'ag': 'skipped (dry run)', 'error': None}]


class FakeConnection:
    def __init__(self, authenticated=True):
        self.authenticated = authenticated


class FakeSession:
    def __init__(self, *, is_active=True, authenticated=True):
        self.is_active = is_active
        self.connection = FakeConnection(authenticated=authenticated)


class SuccessExecutor:
    def __init__(self):
        self.calls = []

    def deploy(self, connection, *, ag_id, player_uid, army_ids, group_type, cancel_event, position_index):
        self.calls.append((connection, ag_id, player_uid, army_ids, group_type, position_index))
        return {
            'teleport': 'success: airlifted at (1, 1) after 1 position attempt(s)',
            'ag': f'success: joined slots {army_ids}',
            'error': None,
            'position_index': position_index + 1,
        }


def test_execute_calls_executor_and_reports_per_account_success():
    session = FakeSession()
    executor = SuccessExecutor()
    targets = [DeployTarget(account_id='a1', label='Acc 1', session=session)]

    results = run_mass_deploy(
        targets, ag_id=42, player_uid=99, army_ids=[1, 2], group_type=GROUP_ARMY_LAND,
        execute=True, executor=executor,
    )

    assert len(results) == 1
    assert results[0]['teleport'].startswith('success')
    assert results[0]['ag'].startswith('success')
    assert results[0]['error'] is None
    assert executor.calls == [(session.connection, 42, 99, [1, 2], GROUP_ARMY_LAND, 0)]


def test_execute_never_touches_a_disconnected_account_but_others_still_run():
    disconnected = FakeSession(is_active=False)
    connected = FakeSession()
    executor = SuccessExecutor()
    targets = [
        DeployTarget(account_id='down', label='Down', session=disconnected),
        DeployTarget(account_id='up', label='Up', session=connected),
    ]

    results = run_mass_deploy(
        targets, ag_id=1, player_uid=2, army_ids=None, group_type=0,
        execute=True, executor=executor,
    )

    by_id = {row['account_id']: row for row in results}
    assert by_id['down']['error'] == 'account is not connected'
    assert by_id['down']['teleport'] == 'failed'
    assert by_id['up']['teleport'].startswith('success')
    assert by_id['up']['ag'].startswith('success')
    # Only the connected account's connection was ever handed to the executor.
    assert [call[0] for call in executor.calls] == [connected.connection]


def test_position_index_is_threaded_across_the_whole_batch():
    """Two accounts must not be handed the same starting placement index —
    matches the reference's shared position_index across the batch."""
    session_a = FakeSession()
    session_b = FakeSession()
    executor = SuccessExecutor()
    targets = [
        DeployTarget(account_id='a', label='A', session=session_a),
        DeployTarget(account_id='b', label='B', session=session_b),
    ]

    run_mass_deploy(
        targets, ag_id=1, player_uid=2, army_ids=None, group_type=0,
        execute=True, executor=executor,
    )

    position_indexes = [call[5] for call in executor.calls]
    assert position_indexes == [0, 1]


def test_cancelled_before_start_never_calls_the_executor():
    import threading

    cancel_event = threading.Event()
    cancel_event.set()
    session = FakeSession()
    executor = SuccessExecutor()
    targets = [DeployTarget(account_id='a1', label='Acc 1', session=session)]

    results = run_mass_deploy(
        targets, ag_id=1, player_uid=2, army_ids=None, group_type=0,
        execute=True, executor=executor, cancel_event=cancel_event,
    )

    assert results[0]['teleport'] == 'cancelled'
    assert executor.calls == []


def test_default_executor_is_the_real_implementation():
    from app.core.mass_deploy import DEFAULT_EXECUTOR, RealDeployExecutor

    assert isinstance(DEFAULT_EXECUTOR, RealDeployExecutor)
