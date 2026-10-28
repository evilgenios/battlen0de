"""Engine/session-factory construction from DATABASE_URL.

No default connection string is baked in anywhere in this module —
DATABASE_URL must be set explicitly (locally, in CI, or in the worker's
deployment config), so a misconfigured environment fails loudly instead of
silently reaching for a developer's local database.

Local-dev .env loading: get_database_url() (used by everything below, and
by migrations/env.py) transparently loads service/.env into os.environ
before reading DATABASE_URL — see _load_local_dotenv()'s docstring for why
that lives here rather than in each entry point (main.py, alembic's
env.py, scripts/migrate_json_accounts.py) separately. This does NOT change
what the "production configuration model" is: DATABASE_URL still comes
from the process environment either way, .env is only ever used to
populate that same os.environ when a real value isn't already there, and
in a real deployment there is normally no service/.env file for it to find
at all — this is a no-op there.

Pooling: this service is the long-lived worker (see the architecture note
in account_manager.py and the top-level README) — it is not a Vercel
serverless function reconnecting on every cold start, so a normal
persistent connection pool is appropriate. Neon specifics:

* Neon's *pooled* connection string (the one with `-pooler` in the
  hostname, routed through PgBouncer in transaction mode) is what
  DATABASE_URL should point at for this service. Neon can also suspend an
  idle compute endpoint and silently close connections, so:
  - `pool_pre_ping=True` — check a connection is alive before handing it out,
    so a resumed/replaced backend doesn't surface as a confusing query error.
  - `pool_recycle` — recycle connections periodically so none outlive a
    Neon-side idle/suspend cycle.
  - a modest `pool_size`/`max_overflow` — this worker is one process, not a
    fleet, and Neon's pooler has its own connection ceiling to respect.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL_ENV_VAR = 'DATABASE_URL'

# service/app/db/session.py -> parents[2] is service/. Computed from this
# file's own location (not the current working directory or sys.argv[0]),
# so it resolves the same way whether this runs as `alembic upgrade head`
# from service/, from the repo root, from migrations/, as `uvicorn
# app.main:app`, or as one of the scripts/ entry points.
_SERVICE_ROOT = Path(__file__).resolve().parents[2]


class DatabaseNotConfiguredError(RuntimeError):
    pass


def _load_local_dotenv() -> None:
    """Best-effort, local-dev-only convenience: populate os.environ from
    service/.env (if the file exists) before anything reads DATABASE_URL.

    This is what was missing: db/session.py itself never loaded .env, so
    anything that imports it directly — alembic's migrations/env.py in
    particular, which never goes through app.main's own startup — saw a
    bare, unpopulated os.environ even when service/.env had DATABASE_URL in
    it, even though a plain `load_dotenv()` in a one-off script worked
    fine (dotenv's default search walks up from the CWD and happened to
    find it there).

    Two things keep this from becoming a second source of truth:
    * `override=False` (python-dotenv's default) — a real environment
      variable that's already set always wins over .env; this only ever
      *fills gaps* in os.environ, never replaces something already there.
    * The path is fixed to service/.env specifically (via _SERVICE_ROOT
      above), not a CWD-relative search — so it's also deterministic
      rather than depending on where the process happened to be launched
      from.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_SERVICE_ROOT / '.env', override=False)


def _normalize_database_url(raw: str) -> str:
    """Accept a plain `postgresql://` URL (what Neon's dashboard gives you)
    and route it through the psycopg3 driver explicitly, since that's the
    driver this service is built against."""
    if raw.startswith('postgresql://'):
        return 'postgresql+psycopg://' + raw[len('postgresql://'):]
    return raw


def get_database_url(env: Optional[dict] = None) -> str:
    if env is None:
        # Only touch the filesystem/real environment when reading the real
        # process environment. Callers that pass an explicit `env` mapping
        # (tests) get fully hermetic behavior — no .env involved.
        _load_local_dotenv()
        env = os.environ
    raw = env.get(DATABASE_URL_ENV_VAR)
    if not raw:
        raise DatabaseNotConfiguredError(
            f'{DATABASE_URL_ENV_VAR} is not set. Point it at your Neon pooled '
            "connection string, e.g. postgresql://user:pass@ep-xxx-pooler."
            "region.aws.neon.tech/dbname?sslmode=require"
        )
    return _normalize_database_url(raw)


def build_engine(
    database_url: Optional[str] = None,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_recycle_seconds: int = 300,
    echo: bool = False,
) -> Engine:
    url = database_url or get_database_url()
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=pool_recycle_seconds,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
        hide_parameters=True,
        future=True,
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """One transaction per call: commit on success, roll back on any
    exception, always close. Repository methods use this so each operation
    is its own short-lived transaction — safe to call from any thread
    (AccountManager/AccountSession run in background threads, not just the
    FastAPI event loop)."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

