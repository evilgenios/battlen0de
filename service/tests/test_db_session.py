"""Regression test for the bug reported against Stage 3: `alembic upgrade
head` failed with DatabaseNotConfiguredError even though `service/.env` had
DATABASE_URL in it, because app.db.session (imported directly by
migrations/env.py) never loaded .env itself — only ad-hoc scripts that
happened to call load_dotenv() did.

These tests always point _SERVICE_ROOT at a temporary directory rather than
the real service/.env, both so they're hermetic and so they never read (or
risk printing) this machine's real Neon credentials.
"""

from __future__ import annotations

import pytest

from app.db import session as session_module
from app.db.session import DatabaseNotConfiguredError, get_database_url


@pytest.fixture(autouse=True)
def isolated_service_root(tmp_path, monkeypatch):
    """Point _SERVICE_ROOT at an empty temp directory so these tests never
    touch (or depend on the contents of) the real service/.env, and always
    delete any real DATABASE_URL from the environment first so tests start
    from a clean slate."""
    monkeypatch.setattr(session_module, '_SERVICE_ROOT', tmp_path)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    return tmp_path


def test_raises_clear_error_when_nothing_is_configured_anywhere():
    with pytest.raises(DatabaseNotConfiguredError):
        get_database_url()


def test_resolving_a_real_looking_url_prints_nothing(isolated_service_root, capsys):
    (isolated_service_root / '.env').write_text(
        'DATABASE_URL=postgresql://realuser:realsecretpassword@ep-abc123-pooler.region.aws.neon.tech/proddb\n',
        encoding='utf-8',
    )
    url = get_database_url()
    assert 'realsecretpassword' in url  # it did resolve the value...
    captured = capsys.readouterr()
    assert captured.out == ''  # ...but never printed it anywhere
    assert captured.err == ''


def test_loads_database_url_from_dotenv_at_the_service_root(isolated_service_root):
    (isolated_service_root / '.env').write_text(
        'DATABASE_URL=postgresql://testuser:testpass@localhost:5432/testdb\n',
        encoding='utf-8',
    )
    url = get_database_url()
    assert url == 'postgresql+psycopg://testuser:testpass@localhost:5432/testdb'


def test_real_environment_variable_takes_precedence_over_dotenv(isolated_service_root, monkeypatch):
    """override=False: a real env var beats .env — .env only fills gaps,
    never becomes a second source of truth."""
    (isolated_service_root / '.env').write_text(
        'DATABASE_URL=postgresql://from-dotenv/should-not-win\n', encoding='utf-8',
    )
    monkeypatch.setenv('DATABASE_URL', 'postgresql://from-real-env/should-win')
    url = get_database_url()
    assert 'from-real-env' in url
    assert 'from-dotenv' not in url


def test_dotenv_lookup_is_independent_of_current_working_directory(isolated_service_root, monkeypatch, tmp_path_factory):
    """The bug report's core complaint: this must work regardless of which
    directory alembic (or anything else) was launched from."""
    (isolated_service_root / '.env').write_text(
        'DATABASE_URL=postgresql://cwd-independent/works\n', encoding='utf-8',
    )
    unrelated_dir = tmp_path_factory.mktemp('somewhere-else-entirely')
    monkeypatch.chdir(unrelated_dir)

    url = get_database_url()
    assert 'cwd-independent' in url


def test_missing_dotenv_file_is_not_an_error(isolated_service_root):
    # No .env written at all in this temp root.
    with pytest.raises(DatabaseNotConfiguredError):
        get_database_url()


def test_explicit_env_mapping_bypasses_dotenv_entirely(isolated_service_root):
    """Passing an explicit `env=` (as the rest of the test suite's
    credentials/config tests do) must stay fully hermetic — no filesystem
    access, .env in isolated_service_root ignored even though it exists."""
    (isolated_service_root / '.env').write_text(
        'DATABASE_URL=postgresql://should-be-ignored/because-env-was-explicit\n', encoding='utf-8',
    )
    with pytest.raises(DatabaseNotConfiguredError):
        get_database_url(env={})


def test_migrations_env_module_does_not_duplicate_dotenv_loading():
    """Requirement: don't duplicate database configuration. The fix lives
    once, in app.db.session; migrations/env.py must keep calling
    get_database_url() rather than re-implementing .env loading itself."""
    import ast
    from pathlib import Path

    env_py = Path(__file__).resolve().parents[1] / 'migrations' / 'env.py'
    tree = ast.parse(env_py.read_text(encoding='utf-8'))
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', None)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert 'load_dotenv' not in calls
