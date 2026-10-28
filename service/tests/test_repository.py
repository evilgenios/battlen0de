"""SqlAlchemyAccountRepository against a REAL PostgreSQL database.

Gated on TEST_DATABASE_URL: JSONB/UUID/ON DELETE behavior is genuinely
Postgres-specific (see app/db/models.py), so these tests don't run against
SQLite — they need a real Postgres to mean anything, per the Stage 3
instructions ("if possible, use PostgreSQL-compatible testing rather than
relying exclusively on SQLite").

This sandbox has neither Docker nor a local Postgres install (verified
before writing this file), so this whole module is SKIPPED here — see the
Stage 3 report's "Test results" section. To actually run it: point
TEST_DATABASE_URL at any throwaway Postgres database (a local install, a
docker run postgres:16, or a disposable Neon branch — never your production
database, since every test drops and recreates the schema) and re-run
pytest. It will then exercise the real schema end-to-end.
"""

from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip('psycopg')

TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason=(
        'TEST_DATABASE_URL is not set (no Docker/local Postgres available in this '
        'sandbox). Set it to a throwaway Postgres database to run these tests — see '
        'this file\'s module docstring.'
    ),
)


@pytest.fixture
def repo():
    from app.db.models import Base
    from app.db.repository import SqlAlchemyAccountRepository
    from app.db.session import build_engine, build_session_factory

    engine = build_engine(TEST_DATABASE_URL, pool_size=2, max_overflow=2)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine)
    yield SqlAlchemyAccountRepository(session_factory)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    from app.security.crypto import generate_key

    monkeypatch.setenv('WARPATH_ENCRYPTION_KEY', generate_key())


def test_get_or_create_user_is_idempotent(repo):
    first = repo.get_or_create_user('owner@example.test')
    second = repo.get_or_create_user('OWNER@example.test  ')  # case/whitespace-insensitive
    assert first.id == second.id


def test_create_and_get_account(repo):
    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id,
        label='Main',
        app_uid='700003',
        app_token='token-1-SECRET',
        device_id='device-1-SECRET',
        device_metadata={'os_type': 'win', 'app_version': '1.0.0'},
    )
    fetched = repo.get_account(account.id)
    assert fetched is not None
    assert fetched.label == 'Main'
    assert fetched.owner_user_id == user.id
    # AccountRecord never carries secrets, even from the DB layer itself.
    assert not hasattr(fetched, 'app_token')
    assert not hasattr(fetched, 'device_id')


def test_secrets_are_encrypted_at_rest(repo):
    """Reads the raw row via a second, independent SQLAlchemy session and
    asserts the plaintext token never appears in the stored columns —
    proof create_account() actually encrypts rather than just claiming to."""
    from sqlalchemy import select

    from app.db.models import WarpathAccount

    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id, label='Main', app_uid='700003',
        app_token='PLAINTEXT-TOKEN-VALUE', device_id='PLAINTEXT-DEVICE-VALUE',
    )
    with repo._session_factory() as session:  # noqa: SLF001 - direct read for verification only
        row = session.execute(
            select(WarpathAccount).where(WarpathAccount.id == account.id)
        ).scalar_one()
        assert 'PLAINTEXT-TOKEN-VALUE' not in row.app_token_encrypted
        assert 'PLAINTEXT-DEVICE-VALUE' not in row.device_id_encrypted


def test_get_credentials_decrypts_correctly(repo):
    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id, label='Main', app_uid='700003',
        app_token='token-1-SECRET', device_id='device-1-SECRET',
        device_metadata={'os_type': 'win', 'server_ip': '1.2.3.4', 'server_port': 10000},
    )
    creds = repo.get_credentials(account.id)
    assert creds is not None
    assert creds.app_token == 'token-1-SECRET'
    assert creds.device_id == 'device-1-SECRET'
    assert creds.server_ip == '1.2.3.4'


def test_list_accounts_scoped_by_owner(repo):
    user_a = repo.get_or_create_user('a@example.test')
    user_b = repo.get_or_create_user('b@example.test')
    repo.create_account(owner_user_id=user_a.id, label='A1', app_uid='700001', app_token='t', device_id='d')
    repo.create_account(owner_user_id=user_b.id, label='B1', app_uid='700002', app_token='t', device_id='d')

    assert {a.label for a in repo.list_accounts(owner_user_id=user_a.id)} == {'A1'}
    assert {a.label for a in repo.list_accounts()} == {'A1', 'B1'}


def test_update_account_reencrypts_rotated_token(repo):
    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id, label='Main', app_uid='700003',
        app_token='old-token', device_id='device-1',
    )
    repo.update_account(account.id, app_token='new-token', label='Renamed')
    creds = repo.get_credentials(account.id)
    updated = repo.get_account(account.id)
    assert creds.app_token == 'new-token'
    assert updated.label == 'Renamed'


def test_delete_account_cascades_snapshot_and_discord_links(repo):
    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id, label='Main', app_uid='700003', app_token='t', device_id='d'
    )
    repo.save_snapshot(account.id, {'name': 'Player'})
    repo.link_discord_user('123456', account.id)

    assert repo.delete_account(account.id) is True
    assert repo.get_account(account.id) is None
    assert repo.get_snapshot(account.id) is None
    assert repo.list_discord_linked_account_ids('123456') == []


def test_delete_account_preserves_events_with_account_id_set_null(repo):
    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id, label='Main', app_uid='700003', app_token='t', device_id='d'
    )
    repo.add_event(account_id=account.id, actor='system', event_type='account_created', detail={})
    repo.delete_account(account.id)

    from sqlalchemy import select

    from app.db.models import AccountEvent

    with repo._session_factory() as session:  # noqa: SLF001
        rows = session.execute(select(AccountEvent)).scalars().all()
        assert len(rows) == 1
        assert rows[0].account_id is None
        # The account id survives in `detail` even after the FK is nulled.
        assert rows[0].detail.get('account_id') == str(account.id)


def test_snapshot_save_and_get_upserts(repo):
    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id, label='Main', app_uid='700003', app_token='t', device_id='d'
    )
    assert repo.get_snapshot(account.id) is None
    repo.save_snapshot(account.id, {'uid': 1})
    repo.save_snapshot(account.id, {'uid': 1, 'name': 'Player'})
    assert repo.get_snapshot(account.id) == {'uid': 1, 'name': 'Player'}


def test_discord_link_and_unlink(repo):
    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id, label='Main', app_uid='700003', app_token='t', device_id='d'
    )
    repo.link_discord_user('discord-1', account.id)
    assert repo.list_discord_linked_account_ids('discord-1') == [account.id]
    repo.unlink_discord_user('discord-1', account.id)
    assert repo.list_discord_linked_account_ids('discord-1') == []


def test_list_events_ordered_newest_first(repo):
    user = repo.get_or_create_user('owner@example.test')
    account = repo.create_account(
        owner_user_id=user.id, label='Main', app_uid='700003', app_token='t', device_id='d'
    )
    for i in range(3):
        repo.add_event(account_id=account.id, actor='system', event_type=f'event_{i}', detail={})
    events = repo.list_events(account.id)
    assert [e.event_type for e in events] == ['event_2', 'event_1', 'event_0']

