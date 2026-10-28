"""scripts/migrate_json_accounts.py: validation, dry-run reporting, and the
hard secrets-never-printed guarantee. The dry-run path never touches a
database, so this runs fully in this sandbox; the actual-import path is
exercised only when TEST_DATABASE_URL is set (same gating as
test_repository.py, for the same reason)."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import migrate_json_accounts as migrate  # noqa: E402

SECRET_TOKEN = 'DO-NOT-PRINT-THIS-TOKEN-abc123'
SECRET_DEVICE_ID = 'DO-NOT-PRINT-THIS-DEVICE-ID-xyz789'


@pytest.fixture
def accounts_json(tmp_path):
    path = tmp_path / 'warpath_accounts.json'
    path.write_text(json.dumps({
        'accounts': {
            'valid@example.test': {
                'app_uid': '111', 'app_token': SECRET_TOKEN, 'device_id': SECRET_DEVICE_ID,
                'linked_at': 1700000000,
            },
            'missing-token@example.test': {
                'app_uid': '222', 'app_token': '', 'device_id': 'device-2',
            },
            'not-an-object@example.test': 'oops',
        }
    }), encoding='utf-8')
    return path


def test_dry_run_reports_correct_counts_and_writes_nothing(accounts_json, capsys):
    exit_code = migrate.main([
        '--json-path', str(accounts_json), '--owner-email', 'owner@example.test', '--dry-run',
    ])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert 'Found: 3 accounts' in out
    assert 'Valid: 1' in out
    assert 'Would import: 1' in out
    assert 'Skipped: 0' in out
    assert 'Dry run' in out


def test_dry_run_never_prints_secret_values(accounts_json, capsys):
    migrate.main(['--json-path', str(accounts_json), '--owner-email', 'owner@example.test', '--dry-run'])
    out = capsys.readouterr().out
    assert SECRET_TOKEN not in out
    assert SECRET_DEVICE_ID not in out


def test_invalid_records_are_reported_by_email_with_reason_not_value(accounts_json, capsys):
    migrate.main(['--json-path', str(accounts_json), '--owner-email', 'owner@example.test', '--dry-run'])
    out = capsys.readouterr().out
    assert 'missing-token@example.test' in out
    assert 'missing app_token' in out
    assert 'not-an-object@example.test' in out
    assert 'entry is not a JSON object' in out


def test_missing_json_file_exits_with_error(tmp_path, capsys):
    exit_code = migrate.main([
        '--json-path', str(tmp_path / 'does-not-exist.json'),
        '--owner-email', 'owner@example.test', '--dry-run',
    ])
    assert exit_code == 2
    assert 'ERROR' in capsys.readouterr().out


def test_original_json_file_is_never_modified(accounts_json):
    before = accounts_json.read_text(encoding='utf-8')
    migrate.main(['--json-path', str(accounts_json), '--owner-email', 'owner@example.test', '--dry-run'])
    after = accounts_json.read_text(encoding='utf-8')
    assert before == after


def test_validate_record_accepts_a_well_formed_entry():
    record = migrate.validate_record('user@example.test', {
        'app_uid': '1', 'app_token': 'tok', 'device_id': 'dev', 'linked_at': 123,
    })
    assert record.is_valid
    assert record.linked_at == 123


@pytest.mark.parametrize('entry,expected_fragment', [
    ({'app_uid': '', 'app_token': 't', 'device_id': 'd'}, 'missing app_uid'),
    ({'app_uid': '1', 'app_token': '', 'device_id': 'd'}, 'missing app_token'),
    ({'app_uid': '1', 'app_token': 't', 'device_id': ''}, 'missing device_id'),
    ({'app_uid': '1', 'app_token': 't', 'device_id': 'd', 'linked_at': 'not-a-number'}, 'linked_at is not a number'),
])
def test_validate_record_rejects_malformed_entries(entry, expected_fragment):
    record = migrate.validate_record('user@example.test', entry)
    assert not record.is_valid
    assert any(expected_fragment in e for e in record.errors)


# ---------------------------------------------------------------------------
# Real-import path — requires TEST_DATABASE_URL, same as test_repository.py.
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')

pytestmark_db = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason='TEST_DATABASE_URL is not set — see test_repository.py module docstring.',
)


@pytestmark_db
def test_import_creates_accounts_owned_by_the_given_user(accounts_json, monkeypatch, capsys):
    from app.db.models import Base
    from app.db.session import build_engine
    from app.security.crypto import generate_key

    monkeypatch.setenv('DATABASE_URL', TEST_DATABASE_URL)
    monkeypatch.setenv('WARPATH_ENCRYPTION_KEY', generate_key())
    engine = build_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    exit_code = migrate.main(['--json-path', str(accounts_json), '--owner-email', 'owner@example.test'])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert 'IMPORTED' in out
    assert SECRET_TOKEN not in out

    from app.db.repository import SqlAlchemyAccountRepository
    from app.db.session import build_session_factory

    repo = SqlAlchemyAccountRepository(build_session_factory(engine))
    accounts = repo.list_accounts()
    assert len(accounts) == 1
    assert accounts[0].linked_email == 'valid@example.test'
    creds = repo.get_credentials(accounts[0].id)
    assert creds.app_token == SECRET_TOKEN

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytestmark_db
def test_import_twice_skips_duplicates_without_force(accounts_json, monkeypatch, capsys):
    from app.db.models import Base
    from app.db.session import build_engine
    from app.security.crypto import generate_key

    monkeypatch.setenv('DATABASE_URL', TEST_DATABASE_URL)
    monkeypatch.setenv('WARPATH_ENCRYPTION_KEY', generate_key())
    engine = build_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    migrate.main(['--json-path', str(accounts_json), '--owner-email', 'owner@example.test'])
    exit_code = migrate.main(['--json-path', str(accounts_json), '--owner-email', 'owner@example.test'])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert 'SKIP' in out
    assert 'Skipped: 1' in out

    Base.metadata.drop_all(engine)
    engine.dispose()
