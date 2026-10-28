"""SQLAlchemy 2.x ORM models for the account store.

Design notes:

* Every table uses a UUID primary key generated in Python (uuid4), never an
  email or other user-supplied value — per the stage-3 instructions, email
  is metadata, not an identifier.
* app_token and device_id are stored ONLY as Fernet ciphertext
  (*_encrypted columns, produced by app.security.crypto.encrypt_secret).
  Nothing in this module ever holds a decrypted value — decryption happens
  in the repository layer (db/repository.py), and only there.
* account_events.account_id is nullable with ON DELETE SET NULL rather than
  CASCADE: deleting an account should not delete its own audit trail. The
  human-readable account id is also duplicated into `detail` JSON at write
  time (by the repository) so the event stays meaningful even after the
  column is nulled out.
* A shared naming_convention is set on the metadata so Alembic autogenerate
  produces stable, predictable constraint/index names instead of the
  driver-default random ones.
* Every timestamp column declares DateTime(timezone=True) explicitly.
  `Mapped[datetime]` alone infers a naive DateTime(), which `alembic check`
  flagged as drift against 0001_initial_schema's TIMESTAMP(timezone=True)
  columns the first time this was run against a real database (see the
  Stage 3 follow-up report) — timezone-aware storage was always the
  intent, this just makes the model say so instead of relying on inference.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.security.identity import CANONICAL_SQL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class User(Base):
    __table_args__ = (CheckConstraint('max_accounts > 0 AND max_sessions > 0 AND max_active_accounts > 0', name='positive_limits'),)
    __tablename__ = 'users'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    # Nullable legacy roles are retained; authentication requires an explicit
    # valid role, active status, password and matching credential version.
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), server_default='active', nullable=False)
    auth_version: Mapped[int] = mapped_column(Integer, server_default='0', nullable=False)
    max_accounts: Mapped[int] = mapped_column(Integer, server_default='5', nullable=False)
    max_sessions: Mapped[int] = mapped_column(Integer, server_default='5', nullable=False)
    max_active_accounts: Mapped[int] = mapped_column(Integer, server_default='2', nullable=False)
    mfa_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, server_default='false', nullable=False)
    player_scout_access: Mapped[bool] = mapped_column(Boolean, server_default='false', nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    accounts: Mapped[list['WarpathAccount']] = relationship(back_populates='owner', cascade='all, delete-orphan')


class WarpathAccount(Base):
    __tablename__ = 'warpath_accounts'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    linked_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)

    app_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_identity: Mapped[Optional[str]] = mapped_column(
        String(80), Computed(CANONICAL_SQL, persisted=True), unique=True, nullable=True
    )
    # Ciphertext only (Fernet tokens, ascii-safe base64) — see module docstring.
    app_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    device_id_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    profile_uid: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    platform: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    # Everything from WarpathCredentials that isn't identity/secret/owner:
    # app_id, pack_name, channel_id, device_model, os_type, os_version,
    # os_language, pack_language, timezone, app_version, package_version,
    # env_id, net_route_type, net_route_info, client_ip, game_id, server_ip,
    # server_port, login_timeout.
    device_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    linked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 'active' | 'disabled' | 'needs_reauth' | 'restricted'
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active')

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped['User'] = relationship(back_populates='accounts')
    snapshot: Mapped[Optional['AccountSnapshot']] = relationship(
        back_populates='account', cascade='all, delete-orphan', uselist=False
    )
    discord_links: Mapped[list['DiscordLink']] = relationship(
        back_populates='account', cascade='all, delete-orphan'
    )


class AccountSnapshot(Base):
    __tablename__ = 'account_snapshots'

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('warpath_accounts.id', ondelete='CASCADE'),
        primary_key=True,
    )
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    account: Mapped['WarpathAccount'] = relationship(back_populates='snapshot')


class DiscordLink(Base):
    __tablename__ = 'discord_links'

    discord_user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    warpath_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('warpath_accounts.id', ondelete='CASCADE'),
        primary_key=True,
    )

    account: Mapped['WarpathAccount'] = relationship(back_populates='discord_links')


class AccountEvent(Base):
    __tablename__ = 'account_events'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Nullable + SET NULL: deleting an account must not delete its own audit
    # trail. The repository also writes the id into `detail` for redundancy.
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('warpath_accounts.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )



class AdminAuditEvent(Base):
    __tablename__ = 'admin_audit_events'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    actor_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    action: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    peer_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class WebsiteSession(Base):
    __tablename__ = 'website_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), index=True)
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PilotGrant(Base):
    __tablename__ = 'pilot_grants'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthThrottle(Base):
    __tablename__ = 'auth_throttles'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
