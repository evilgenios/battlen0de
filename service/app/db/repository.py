"""Data-access layer: the only place in this codebase that issues SQLAlchemy
queries for accounts. AccountManager (app/core/account_manager.py) never
imports SQLAlchemy and never will — it manages live sessions only; this
module manages persistence only.

AccountRepository is a typing.Protocol (structural interface) with one real
implementation, SqlAlchemyAccountRepository, backed by Postgres. Tests for
the FastAPI layer use a separate in-memory implementation of the same
protocol (tests/fake_repository.py) so API/auth/ownership/error-handling
behavior is verifiable without a live database — see that file's docstring
and the Stage 3 test report for why.

Secrets discipline: AccountRecord (the DTO returned by get_account/
list_accounts/create_account/update_account) deliberately has NO app_token
or device_id field — those never leave this module in plaintext except
through get_credentials(), which is the one method that decrypts them, and
which only the session-connect code path (api/sessions.py) calls.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from sqlalchemy import select, func, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError
from app.security.identity import canonical_identity, IdentityConflict, AccountLimitReached, AccountUnavailable

from app.core.warpath.credentials import WarpathCredentials
from app.security.crypto import decrypt_secret, encrypt_secret
from app.db.models import AccountEvent, AccountSnapshot, DiscordLink, User, WarpathAccount

# WarpathCredentials fields that live inside the device_metadata JSONB blob
# rather than as their own columns (everything except identity/secrets/owner).
# Public (no leading underscore) because app/api/link.py reuses this exact
# list rather than duplicating it when building a new linked account's
# device_metadata from the same WarpathCredentials shape.
DEVICE_METADATA_FIELDS = (
    'app_id', 'pack_name', 'channel_id', 'device_model', 'os_type', 'os_version',
    'os_language', 'pack_language', 'timezone', 'app_version', 'package_version',
    'env_id', 'net_route_type', 'net_route_info', 'client_ip', 'game_id',
    'server_ip', 'server_port', 'login_timeout',
)


@dataclass(frozen=True)
class AccountRecord:
    """Everything about a linked account EXCEPT its secrets. Safe to hand to
    an API response schema as-is."""

    id: uuid.UUID
    owner_user_id: uuid.UUID
    label: str
    linked_email: Optional[str]
    app_uid: str
    profile_uid: Optional[int]
    platform: int
    device_metadata: Dict[str, Any]
    linked_at: Optional[datetime]
    last_connected_at: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class UserRecord:
    id: uuid.UUID
    email: str
    # Both None for a plain Warpath-account-owner User (created via the
    # account-linking flow or DEV_USER_EMAIL). Only set once a dashboard
    # login exists for this user — see app/db/models.py's User docstring.
    password_hash: Optional[str] = None
    role: Optional[str] = None
    status: str = "active"
    auth_version: int = 0
    max_accounts: int = 5
    max_sessions: int = 5
    max_active_accounts: int = 2
    player_scout_access: bool = False


@dataclass(frozen=True)
class AccountEventRecord:
    id: int
    account_id: Optional[uuid.UUID]
    actor: str
    event_type: str
    detail: Dict[str, Any]
    created_at: datetime


class AccountRepository(Protocol):
    """Structural interface — see SqlAlchemyAccountRepository for the real
    implementation and tests/fake_repository.py for the in-memory test
    double. Anything satisfying this shape works with the API layer."""

    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[UserRecord]: ...

    def get_or_create_user(self, email: str) -> UserRecord: ...

    def get_user_by_email(self, email: str) -> Optional[UserRecord]: ...

    def set_user_password(self, email: str, *, password_hash: str, role: str) -> UserRecord: ...

    def list_dashboard_users(self) -> List[UserRecord]: ...

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
    ) -> AccountRecord: ...

    def relink_account(self, account_id: uuid.UUID, *, owner_user_id: uuid.UUID, **fields: Any) -> AccountRecord: ...

    def get_account(self, account_id: uuid.UUID) -> Optional[AccountRecord]: ...

    def list_accounts(self, owner_user_id: Optional[uuid.UUID] = None) -> List[AccountRecord]: ...

    def update_account(self, account_id: uuid.UUID, **fields: Any) -> Optional[AccountRecord]: ...

    def delete_account(self, account_id: uuid.UUID) -> bool: ...

    def get_credentials(self, account_id: uuid.UUID) -> Optional[WarpathCredentials]: ...

    def mark_account_auth_failure(self, account_id: uuid.UUID, *, restricted: bool) -> None: ...

    def save_snapshot(self, account_id: uuid.UUID, snapshot: Dict[str, Any]) -> None: ...

    def get_snapshot(self, account_id: uuid.UUID) -> Optional[Dict[str, Any]]: ...

    def add_event(
        self,
        *,
        account_id: Optional[uuid.UUID],
        actor: str,
        event_type: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None: ...

    def list_events(self, account_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> List[AccountEventRecord]: ...

    def list_events_for_accounts(self, account_ids: List[uuid.UUID], *, limit: int = 100, offset: int = 0) -> List[AccountEventRecord]: ...

    def link_discord_user(self, discord_user_id: str, account_id: uuid.UUID) -> None: ...

    def unlink_discord_user(self, discord_user_id: str, account_id: uuid.UUID) -> None: ...

    def list_discord_linked_account_ids(self, discord_user_id: str) -> List[uuid.UUID]: ...


def _to_user_record(row: User) -> UserRecord:
    return UserRecord(**{field: getattr(row, field) for field in UserRecord.__dataclass_fields__})


def _to_account_record(row: WarpathAccount) -> AccountRecord:
    return AccountRecord(
        id=row.id,
        owner_user_id=row.owner_user_id,
        label=row.label,
        linked_email=row.linked_email,
        app_uid=row.app_uid,
        profile_uid=row.profile_uid,
        platform=row.platform,
        device_metadata=dict(row.device_metadata or {}),
        linked_at=row.linked_at,
        last_connected_at=row.last_connected_at,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyAccountRepository:
    """Postgres-backed AccountRepository. Each method opens and closes its
    own short-lived session/transaction (see db.session.session_scope), so
    this object is safe to share across threads — including the background
    threads AccountSession/AccountManager use."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def _session(self) -> Session:
        return self._session_factory()

    # -- users --------------------------------------------------------------
    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[UserRecord]:
        with self._session() as session:
            row = session.get(User, user_id)
            return _to_user_record(row) if row else None

    def get_or_create_user(self, email: str) -> UserRecord:
        email = email.strip().lower()
        with self._session() as session:
            row = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if row is None:
                row = User(email=email)
                session.add(row)
                session.flush()
            session.commit()
            return _to_user_record(row)

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        email = email.strip().lower()
        with self._session() as session:
            row = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if row is None:
                return None
            return _to_user_record(row)

    def set_user_password(self, email: str, *, password_hash: str, role: str) -> UserRecord:
        """Used only by scripts/bootstrap_dashboard_admins.py — never by any
        API route. Creates the User row if it doesn't exist yet (an admin
        need not have a Warpath account linked first)."""
        if role not in ('member', 'admin'):
            raise ValueError('explicit member/admin role required')
        email = email.strip().lower()
        with self._session() as session:
            row = session.execute(select(User).where(User.email == email).with_for_update()).scalar_one_or_none()
            if row is None:
                row = User(email=email, auth_version=0)
                session.add(row)
            row.auth_version += 1
            row.status = 'active'
            row.password_hash = password_hash
            row.role = role
            session.commit()
            session.refresh(row)
            return _to_user_record(row)

    def list_dashboard_users(self) -> List[UserRecord]:
        with self._session() as session:
            rows = session.execute(select(User).where(User.password_hash.is_not(None))).scalars().all()
            return [_to_user_record(r) for r in rows]

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
        if canonical_identity(app_uid) is None:
            raise AccountUnavailable('invalid game identity')
        with self._session() as session:
            owner = session.get(User, owner_user_id, with_for_update=True)
            if owner is None or owner.status != 'active':
                raise AccountUnavailable('owner unavailable')
            count = session.scalar(select(func.count()).select_from(WarpathAccount).where(WarpathAccount.owner_user_id == owner_user_id))
            if count >= owner.max_accounts:
                raise AccountLimitReached()
            row = WarpathAccount(
                owner_user_id=owner_user_id,
                label=label,
                linked_email=linked_email,
                app_uid=app_uid,
                app_token_encrypted=encrypt_secret(app_token),
                device_id_encrypted=encrypt_secret(device_id),
                profile_uid=profile_uid,
                platform=platform,
                device_metadata=device_metadata or {},
                linked_at=datetime.now(timezone.utc),
                status=status,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise IdentityConflict() from None
            session.refresh(row)
            return _to_account_record(row)

    def relink_account(self, account_id: uuid.UUID, *, owner_user_id: uuid.UUID, **fields: Any) -> AccountRecord:
        identity = canonical_identity(fields['app_uid'])
        if identity is None:
            raise AccountUnavailable('invalid game identity')
        with self._session() as session:
            owner = session.get(User, owner_user_id, with_for_update=True)
            row = session.get(WarpathAccount, account_id, with_for_update=True)
            if (owner is None or owner.status != 'active' or row is None or row.owner_user_id != owner_user_id
                    or row.status not in ('active', 'needs_reauth')):
                raise AccountUnavailable('account unavailable for relink')
            existing = canonical_identity(row.app_uid)
            if existing is not None and existing != identity:
                raise IdentityConflict()
            row.app_uid = fields['app_uid']
            row.app_token_encrypted = encrypt_secret(fields['app_token'])
            row.device_id_encrypted = encrypt_secret(fields['device_id'])
            for key in ('linked_email', 'profile_uid', 'platform', 'device_metadata'):
                setattr(row, key, fields[key])
            row.linked_at = datetime.now(timezone.utc)
            row.status = 'active'
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise IdentityConflict() from None
            session.refresh(row)
            return _to_account_record(row)

    def get_account(self, account_id: uuid.UUID) -> Optional[AccountRecord]:
        with self._session() as session:
            row = session.get(WarpathAccount, account_id)
            return _to_account_record(row) if row is not None else None

    def list_accounts(self, owner_user_id: Optional[uuid.UUID] = None) -> List[AccountRecord]:
        with self._session() as session:
            stmt = select(WarpathAccount)
            if owner_user_id is not None:
                stmt = stmt.where(WarpathAccount.owner_user_id == owner_user_id)
            stmt = stmt.order_by(WarpathAccount.created_at)
            rows = session.execute(stmt).scalars().all()
            return [_to_account_record(row) for row in rows]

    def update_account(self, account_id: uuid.UUID, **fields: Any) -> Optional[AccountRecord]:
        """Partial update. `app_token`/`device_id` (plaintext, if given) are
        re-encrypted; every other key must match a real column name."""
        with self._session() as session:
            row = session.get(WarpathAccount, account_id)
            if row is None:
                return None
            if 'app_token' in fields:
                row.app_token_encrypted = encrypt_secret(fields.pop('app_token'))
            if 'device_id' in fields:
                row.device_id_encrypted = encrypt_secret(fields.pop('device_id'))
            for key, value in fields.items():
                if not hasattr(row, key):
                    raise ValueError(f'unknown account field: {key!r}')
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return _to_account_record(row)

    def delete_account(self, account_id: uuid.UUID) -> bool:
        with self._session() as session:
            row = session.get(WarpathAccount, account_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def get_credentials(self, account_id: uuid.UUID) -> Optional[WarpathCredentials]:
        """Decrypts app_token/device_id. Only ever call this from the
        session-connect code path — never to satisfy an API response."""
        with self._session() as session:
            row = session.get(WarpathAccount, account_id)
            if row is None:
                return None
            metadata = dict(row.device_metadata or {})
            kwargs = {k: metadata[k] for k in DEVICE_METADATA_FIELDS if k in metadata}
            return WarpathCredentials(
                account_id=str(row.id),
                label=row.label,
                app_uid=row.app_uid,
                app_token=decrypt_secret(row.app_token_encrypted),
                device_id=decrypt_secret(row.device_id_encrypted),
                profile_uid=row.profile_uid or 0,
                platform=row.platform,
                **kwargs,
            )

    def mark_account_auth_failure(self, account_id: uuid.UUID, *, restricted: bool) -> None:
        # Late game events must never replace an operator's disabled/restricted
        # policy with a relinkable state. This is one conditional SQL update.
        with self._session_factory.begin() as session:
            session.execute(update(WarpathAccount).where(WarpathAccount.id == account_id,
                WarpathAccount.status == 'active').values(status='restricted' if restricted else 'needs_reauth'))

    # -- snapshots ------------------------------------------------------------
    def save_snapshot(self, account_id: uuid.UUID, snapshot: Dict[str, Any]) -> None:
        with self._session() as session:
            row = session.get(AccountSnapshot, account_id)
            if row is None:
                row = AccountSnapshot(account_id=account_id, snapshot=snapshot)
                session.add(row)
            else:
                row.snapshot = snapshot
            session.commit()

    def get_snapshot(self, account_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        with self._session() as session:
            row = session.get(AccountSnapshot, account_id)
            return dict(row.snapshot) if row is not None else None

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
            # Redundant with the FK so the event stays meaningful even after
            # ON DELETE SET NULL fires (see models.py's AccountEvent docstring).
            detail.setdefault('account_id', str(account_id))
        with self._session() as session:
            session.add(AccountEvent(
                account_id=account_id,
                actor=actor,
                event_type=event_type,
                detail=detail,
            ))
            session.commit()

    def list_events(self, account_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> List[AccountEventRecord]:
        with self._session() as session:
            stmt = (
                select(AccountEvent)
                .where(AccountEvent.account_id == account_id)
                .order_by(AccountEvent.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                AccountEventRecord(
                    id=row.id,
                    account_id=row.account_id,
                    actor=row.actor,
                    event_type=row.event_type,
                    detail=dict(row.detail or {}),
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def list_events_for_accounts(
        self, account_ids: List[uuid.UUID], *, limit: int = 100, offset: int = 0
    ) -> List[AccountEventRecord]:
        if not account_ids:
            return []
        with self._session() as session:
            stmt = (
                select(AccountEvent)
                .where(AccountEvent.account_id.in_(account_ids))
                .order_by(AccountEvent.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                AccountEventRecord(
                    id=row.id,
                    account_id=row.account_id,
                    actor=row.actor,
                    event_type=row.event_type,
                    detail=dict(row.detail or {}),
                    created_at=row.created_at,
                )
                for row in rows
            ]

    # -- discord links ------------------------------------------------------------
    def link_discord_user(self, discord_user_id: str, account_id: uuid.UUID) -> None:
        with self._session() as session:
            existing = session.get(DiscordLink, (discord_user_id, account_id))
            if existing is None:
                session.add(DiscordLink(discord_user_id=discord_user_id, warpath_account_id=account_id))
                session.commit()

    def unlink_discord_user(self, discord_user_id: str, account_id: uuid.UUID) -> None:
        with self._session() as session:
            existing = session.get(DiscordLink, (discord_user_id, account_id))
            if existing is not None:
                session.delete(existing)
                session.commit()

    def list_discord_linked_account_ids(self, discord_user_id: str) -> List[uuid.UUID]:
        with self._session() as session:
            stmt = select(DiscordLink.warpath_account_id).where(DiscordLink.discord_user_id == discord_user_id)
            return list(session.execute(stmt).scalars().all())

