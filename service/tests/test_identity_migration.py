"""Stopped-worker migration/backfill using only a disposable test database."""
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from app.db.models import Base
from app.db.session import build_engine

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='requires disposable PostgreSQL')


def test_duplicate_preflight_quarantine_roles_and_downgrade(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', os.environ['TEST_DATABASE_URL'])
    engine = build_engine(os.environ['TEST_DATABASE_URL'])
    Base.metadata.drop_all(engine)
    with engine.begin() as db:
        db.execute(text('DROP TABLE IF EXISTS alembic_version'))
    config = Config('alembic.ini')
    command.upgrade(config, '0003_dashboard_auth_columns')
    owner = uuid.uuid4()
    with engine.begin() as db:
        db.execute(text("INSERT INTO users (id,email,role) VALUES (:id,'legacy@example.com',NULL)"), {'id': owner})
        for uid, status in [('000123', 'active'), ('123', 'active'), ('invalid', 'active'), ('malformed', 'restricted')]:
            db.execute(text('''INSERT INTO warpath_accounts
                (id,owner_user_id,label,app_uid,app_token_encrypted,device_id_encrypted,platform,device_metadata,status)
                VALUES (:id,:owner,'Synthetic',:uid,'synthetic-ciphertext','synthetic-ciphertext',22,'{}',:status)'''),
                {'id': uuid.uuid4(), 'owner': owner, 'uid': uid, 'status': status})
    with pytest.raises(RuntimeError, match='Duplicate canonical'):
        command.upgrade(config, 'head')
    with engine.begin() as db:
        assert db.scalar(text('SELECT version_num FROM alembic_version')) == '0003_dashboard_auth_columns'
        assert db.scalar(text('SELECT count(*) FROM warpath_accounts')) == 4
        db.execute(text("DELETE FROM warpath_accounts WHERE app_uid='123'"))  # synthetic conflict resolution only
    command.upgrade(config, 'head')
    command.check(config)
    with engine.connect() as db:
        assert db.scalar(text('SELECT role FROM users')) is None
        assert db.scalar(text("SELECT canonical_identity FROM warpath_accounts WHERE app_uid='000123'")) == 'warpath:lilith:123'
        assert db.scalar(text("SELECT status FROM warpath_accounts WHERE app_uid='invalid'")) == 'needs_reauth'
        assert db.scalar(text("SELECT status FROM warpath_accounts WHERE app_uid='malformed'")) == 'restricted'
        assert db.scalar(text('SELECT count(*) FROM website_sessions')) == 0
    command.downgrade(config, '0003_dashboard_auth_columns')
    with engine.connect() as db:
        assert db.scalar(text("SELECT status FROM warpath_accounts WHERE app_uid='invalid'")) == 'needs_reauth'
        assert db.scalar(text('SELECT role FROM users')) is None
    command.upgrade(config, 'head')
    Base.metadata.drop_all(engine)
    with engine.begin() as db:
        db.execute(text('DROP TABLE alembic_version'))
    engine.dispose()
