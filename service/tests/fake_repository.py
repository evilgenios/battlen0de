"""An in-memory AccountRepository (same structural interface as
SqlAlchemyAccountRepository — see app/db/repository.py's AccountRepository
Protocol) used ONLY to test the FastAPI layer: routing, ownership
enforcement, HTTP status-code mapping, and secret-leakage checks.

Why: this sandbox has no Docker and no local Postgres install, so
SqlAlchemyAccountRepository itself can only be tested against a real
Postgres (see test_repository.py, which is skipped here and documented as
such in the Stage 3 report). The repository *protocol* is exactly what lets
the API layer be fully tested anyway — everything in app/api/*.py talks to
AccountRepository as an interface, never to SQLAlchemy directly, so swapping
in this fake proves the API layer's own logic (ownership checks, status
codes, event writes, what does/doesn't appear in responses) independently of
whether the Postgres-specific storage code is also correct.

This is a test double for one dependency, not a second architecture: the
real AccountManager/AccountSession/WarpathConnection stack from Stage 1/2 is
used unmodified in every test that imports this file (only the socket layer
is faked, exactly as in Stage 1/2's own tests/fakes.py).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.warpath.credentials import WarpathCredentials
from app.db.repository import AccountEventRecord, AccountRecord, UserRecord

_DEVICE_METADATA_FIELDS = (
    'app_id', 'pack_name', 'channel_id', 'device_model', 'os_type', 'os_version',
    'os_language', 'pack_language', 'timezone', 'app_version', 'package_version',
    'env_id', 'net_route_type', 'net_route_info', 'client_ip', 'game_id',
    'server_ip', 'server_port', 'login_timeout',
)


class InMemoryAccountRepository:
    def __init__(self) -> None:
        self._users: Dict[uuid.UUID, UserRecord] = {}
        self._accounts: Dict[uuid.UUID, AccountRecord] = {}
        self._secrets: Dict[uuid.UUID, Dict[str, str]] = {}  # account_id -> {app_token, device_id}
        self._snapshots: Dict[uuid.UUID, Dict[str, Any]] = {}
        self._events: List[AccountEventRecord] = []
        self._discord_links: set[tuple[str, uuid.UUID]] = set()
        self._next_event_id = 1

    def get_user_by_id(self, user_id):
        return self._users.get(user_id)

    # -- users --------------------------------------------------------------
    def get_or_create_user(self, email: str) -> UserRecord:
        email = email.strip().lower()
        for user in self._users.values():
            if user.email == email:
                return user
        user = UserRecord(id=uuid.uuid4(), email=email)
        self._users[user.id] = user
        return user

    # -- accounts -------------------------------------------------------------
    def create_account(
        self,
        *,
        owner_user_id: uuid.UUID,
        label: str,
        app_uid: str,
        app_token: str,
        device_id: str,
        linked_email: Optional[str] = None,
        profile_uid: Optional[int] = None,
        platform: int = 22,
        device_metadata: Optional[Dict[str, Any]] = None,
        status: str = 'active',
    ) -> AccountRecord:
        now = datetime.now(timezone.utc)
        account = AccountRecord(
            id=uuid.uuid4(),
            owner_user_id=owner_user_id,
            label=label,
            linked_email=linked_email,
            app_uid=app_uid,
            profile_uid=profile_uid,
            platform=platform,
            device_metadata=dict(device_metadata or {}),
            linked_at=now,
            last_connected_at=None,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self._accounts[account.id] = account
        self._secrets[account.id] = {'app_token': app_token, 'device_id': device_id}
        return account

    def get_account(self, account_id: uuid.UUID) -> Optional[AccountRecord]:
        return self._accounts.get(account_id)

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        email = email.strip().lower()
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    def set_user_password(self, email: str, *, password_hash: str, role: str) -> UserRecord:
        email = email.strip().lower()
        existing = self.get_user_by_email(email)
        user_id = existing.id if existing else uuid.uuid4()
        record = UserRecord(id=user_id, email=email, password_hash=password_hash, role=role)
        self._users[user_id] = record
        return record

    def list_dashboard_users(self) -> List[UserRecord]:
        return [u for u in self._users.values() if u.password_hash]

    def list_accounts(self, owner_user_id: Optional[uuid.UUID] = None) -> List[AccountRecord]:
        rows = list(self._accounts.values())
        if owner_user_id is not None:
            rows = [r for r in rows if r.owner_user_id == owner_user_id]
        return sorted(rows, key=lambda r: r.created_at)

    def update_account(self, account_id: uuid.UUID, **fields: Any) -> Optional[AccountRecord]:
        account = self._accounts.get(account_id)
        if account is None:
            return None
        if 'app_token' in fields:
            self._secrets[account_id]['app_token'] = fields.pop('app_token')
        if 'device_id' in fields:
            self._secrets[account_id]['device_id'] = fields.pop('device_id')
        for key in fields:
            if not hasattr(account, key):
                raise ValueError(f'unknown account field: {key!r}')
        updated = replace(account, **fields, updated_at=datetime.now(timezone.utc))
        self._accounts[account_id] = updated
        return updated

    def delete_account(self, account_id: uuid.UUID) -> bool:
        if account_id not in self._accounts:
            return False
        del self._accounts[account_id]
        self._secrets.pop(account_id, None)
        self._snapshots.pop(account_id, None)
        self._discord_links = {link for link in self._discord_links if link[1] != account_id}
        return True

    def get_credentials(self, account_id: uuid.UUID) -> Optional[WarpathCredentials]:
        account = self._accounts.get(account_id)
        secrets = self._secrets.get(account_id)
        if account is None or secrets is None:
            return None
        metadata = account.device_metadata
        kwargs = {k: metadata[k] for k in _DEVICE_METADATA_FIELDS if k in metadata}
        return WarpathCredentials(
            account_id=str(account.id),
            label=account.label,
            app_uid=account.app_uid,
            app_token=secrets['app_token'],
            device_id=secrets['device_id'],
            profile_uid=account.profile_uid or 0,
            platform=account.platform,
            **kwargs,
        )

    def mark_account_auth_failure(self, account_id, *, restricted):
        account = self.get_account(account_id)
        if account and account.status == 'active':
            self.update_account(account_id, status='restricted' if restricted else 'needs_reauth')

    # -- snapshots ------------------------------------------------------------
    def save_snapshot(self, account_id: uuid.UUID, snapshot: Dict[str, Any]) -> None:
        self._snapshots[account_id] = dict(snapshot)

    def get_snapshot(self, account_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        snapshot = self._snapshots.get(account_id)
        return dict(snapshot) if snapshot is not None else None

    # -- events -----------------------------------------------------------------
    def add_event(
        self,
        *,
        account_id: Optional[uuid.UUID],
        actor: str,
        event_type: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        detail = dict(detail or {})
        if account_id is not None:
            detail.setdefault('account_id', str(account_id))
        self._events.append(AccountEventRecord(
            id=self._next_event_id,
            account_id=account_id,
            actor=actor,
            event_type=event_type,
            detail=detail,
            created_at=datetime.now(timezone.utc),
        ))
        self._next_event_id += 1

    def list_events(self, account_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> List[AccountEventRecord]:
        rows = [e for e in self._events if e.account_id == account_id]
        rows.sort(key=lambda e: e.created_at, reverse=True)
        return rows[offset: offset + limit]

    def list_events_for_accounts(
        self, account_ids: List[uuid.UUID], *, limit: int = 100, offset: int = 0
    ) -> List[AccountEventRecord]:
        allowed = set(account_ids)
        rows = [e for e in self._events if e.account_id in allowed]
        rows.sort(key=lambda e: e.created_at, reverse=True)
        return rows[offset: offset + limit]

    # -- discord links ------------------------------------------------------------
    def link_discord_user(self, discord_user_id: str, account_id: uuid.UUID) -> None:
        self._discord_links.add((discord_user_id, account_id))

    def unlink_discord_user(self, discord_user_id: str, account_id: uuid.UUID) -> None:
        self._discord_links.discard((discord_user_id, account_id))

    def list_discord_linked_account_ids(self, discord_user_id: str) -> List[uuid.UUID]:
        return [acct_id for (disc_id, acct_id) in self._discord_links if disc_id == discord_user_id]


class FakeEngine:
    """Minimal stand-in for a SQLAlchemy Engine, just enough for the
    /health route's `with engine.connect() as c: c.execute(...)` pattern."""

    def __init__(self, *, healthy: bool = True):
        self.healthy = healthy

    def connect(self):
        return self

    def __enter__(self):
        if not self.healthy:
            raise RuntimeError('database unreachable (fake)')
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        return None

