"""Marketplace persistence. Only the website user ID crosses the game-data boundary."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError

from app.db.models import Base


class MarketplaceProfile(Base):
    __tablename__ = 'marketplace_profiles'
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False, default='Commander')
    seller_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    staff_role: Mapped[str] = mapped_column(String(24), nullable=False, default='user')
    restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MarketplaceListing(Base):
    __tablename__ = 'marketplace_listings'
    __table_args__ = (
        CheckConstraint("status IN ('draft','pending_review','active','paused','removed')", name='marketplace_listing_status'),
        CheckConstraint('price_cents >= 100 AND strength >= 0 AND version > 0', name='marketplace_listing_values'),
        UniqueConstraint('server', 'commander_id', name='uq_marketplace_commander'),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    seller_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    commander_name: Mapped[str] = mapped_column(String(60), nullable=False)
    commander_id: Mapped[str] = mapped_column(String(40), nullable=False)
    server: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    strength: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    commander_level: Mapped[int] = mapped_column(Integer, nullable=False)
    collector_level: Mapped[int] = mapped_column(Integer, nullable=False)
    airspace: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    vip: Mapped[int] = mapped_column(Integer, nullable=False)
    composition: Mapped[str] = mapped_column(String(24), nullable=False)
    research: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default='USD')
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default='')
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='draft', index=True)
    review_note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    stats_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    control_demonstrated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class MarketplaceFavorite(Base):
    __tablename__ = 'marketplace_favorites'
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    listing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('marketplace_listings.id', ondelete='CASCADE'), primary_key=True)


class MarketplaceConversation(Base):
    __tablename__ = 'marketplace_conversations'
    __table_args__ = (UniqueConstraint('listing_id', 'buyer_id', name='uq_marketplace_conversation'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('marketplace_listings.id', ondelete='CASCADE'), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketplaceMessage(Base):
    __tablename__ = 'marketplace_messages'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('marketplace_conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketplaceReport(Base):
    __tablename__ = 'marketplace_reports'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('marketplace_listings.id', ondelete='CASCADE'), nullable=False)
    reporter_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketplaceAuditEvent(Base):
    __tablename__ = 'marketplace_audit_events'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('marketplace_listings.id', ondelete='SET NULL'), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketplaceNotification(Base):
    __tablename__ = 'marketplace_notifications'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


MARKETPLACE_TABLES = [table for table in Base.metadata.sorted_tables if table.name.startswith('marketplace_')]


class MarketplaceStore:
    def __init__(self, session_factory):
        self.sessions = session_factory

    @staticmethod
    def profile(session, user_id):
        profile = session.get(MarketplaceProfile, user_id)
        if profile is None:
            try:
                with session.begin_nested():
                    profile = MarketplaceProfile(user_id=user_id)
                    session.add(profile)
                    session.flush()
            except IntegrityError:
                profile = session.get(MarketplaceProfile, user_id)
        return profile

    @staticmethod
    def audit(session, actor_id, listing_id, action, **detail):
        session.add(MarketplaceAuditEvent(actor_id=actor_id, listing_id=listing_id, action=action, detail=detail))

    @staticmethod
    def notify(session, user_id, text):
        session.add(MarketplaceNotification(user_id=user_id, text=text[:300]))

    @staticmethod
    def listing(row, profile=None, *, private=False):
        data = {key: getattr(row, key) for key in (
            'id', 'title', 'description', 'commander_name', 'server', 'strength', 'commander_level',
            'collector_level', 'airspace', 'vip', 'composition', 'research', 'price_cents', 'currency',
            'status', 'stats_reviewed', 'control_demonstrated', 'version', 'created_at', 'updated_at',
        )}
        data.update(seller_name=profile.display_name if profile else 'Commander', is_demo=False)
        if private:
            data.update(commander_id=row.commander_id, evidence=row.evidence, review_note=row.review_note, seller_id=row.seller_id)
        return data
