"""Durable website identity. Tokens are opaque; only SHA-256 digests persist.

All credential/session/grant mutations lock the user first. There is no
in-memory authentication fallback when PostgreSQL is unavailable.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.dashboard_session import DashboardSession
from app.db.models import AuthThrottle, PilotGrant, User, WebsiteSession
from app.security.auth_config import VALID_ROLES
from app.security.passwords import hash_password


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def now():
    return datetime.now(timezone.utc)


class PostgresIdentityStore:
    ttl_seconds = 86400
    idle_timeout_seconds = 7200

    def __init__(self, session_factory):
        self.factory = session_factory

    def _live(self, at):
        return and_(WebsiteSession.revoked_at.is_(None), WebsiteSession.expires_at > at,
                    WebsiteSession.last_used_at > at - timedelta(seconds=self.idle_timeout_seconds),
                    WebsiteSession.auth_version == User.auth_version,
                    User.status == 'active', User.role.in_(VALID_ROLES), User.password_hash.is_not(None))

    def create(self, *, user_id, email, role, expected_password_hash=None):
        token = secrets.token_urlsafe(32)
        at = now()
        with self.factory.begin() as db:
            user = db.get(User, user_id, with_for_update=True)
            if (not user or user.status != 'active' or user.role not in VALID_ROLES
                    or not user.password_hash or user.password_hash != expected_password_hash):
                raise HTTPException(401, 'credentials changed; sign in again')
            count = db.scalar(select(func.count()).select_from(WebsiteSession).join(User).where(
                WebsiteSession.user_id == user_id, self._live(at)))
            # Evict oldest sessions under the same user lock, allowing recovery
            # from a lost browser without requiring another authenticated session.
            if count >= user.max_sessions:
                victims = db.scalars(select(WebsiteSession).join(User).where(
                    WebsiteSession.user_id == user_id, self._live(at)).order_by(WebsiteSession.created_at)
                    .limit(count - user.max_sessions + 1)).all()
                for victim in victims:
                    victim.revoked_at = at
            row = WebsiteSession(token_hash=digest(token), user_id=user.id, auth_version=user.auth_version,
                                 csrf_token=secrets.token_urlsafe(32), cache_key=secrets.token_urlsafe(24),
                                 created_at=at, last_used_at=at, expires_at=at + timedelta(seconds=self.ttl_seconds))
            db.add(row)
            return self._dto(row, user, token)

    @staticmethod
    def _dto(row, user, token):
        return DashboardSession(session_id=token, user_id=user.id, email=user.email, role=user.role,
                                csrf_token=row.csrf_token, cache_key=row.cache_key,
                                created_at=row.created_at.timestamp(), last_used_at=row.last_used_at.timestamp())

    def get(self, token):
        if not token or len(token) > 256:
            return None
        at = now()
        with self.factory.begin() as db:
            pair = db.execute(select(WebsiteSession, User).join(User).where(
                WebsiteSession.token_hash == digest(token), self._live(at))).first()
            if pair is None:
                return None
            row, user = pair
            row.last_used_at = at
            return self._dto(row, user, token)

    def destroy(self, token):
        with self.factory.begin() as db:
            db.execute(update(WebsiteSession).where(WebsiteSession.token_hash == digest(token))
                       .values(revoked_at=now()))

    def active_count(self, user_id=None):
        with self.factory() as db:
            query = select(func.count()).select_from(WebsiteSession).join(User).where(self._live(now()))
            if user_id is not None:
                query = query.where(User.id == user_id)
            return db.scalar(query)

    def inventory(self, user_id, current_key):
        with self.factory() as db:
            rows = db.scalars(select(WebsiteSession).join(User).where(User.id == user_id, self._live(now()))
                              .order_by(WebsiteSession.created_at.desc())).all()
            return [dict(id=r.cache_key, current=r.cache_key == current_key, created_at=r.created_at,
                         last_used_at=r.last_used_at, expires_at=r.expires_at) for r in rows]

    def revoke(self, user_id, key=None):
        with self.factory.begin() as db:
            user = db.get(User, user_id, with_for_update=True)
            if key is None:
                user.auth_version += 1
                db.execute(update(WebsiteSession).where(WebsiteSession.user_id == user_id).values(revoked_at=now()))
            else:
                row = db.scalar(select(WebsiteSession).where(WebsiteSession.user_id == user_id,
                                                            WebsiteSession.cache_key == key).with_for_update())
                if row is None:
                    raise HTTPException(404, 'session not found')
                row.revoked_at = now()

    def throttle(self, scope, subject, *, limit, seconds):
        at = now()
        key = scope + ':' + digest(str(subject))
        expired = AuthThrottle.started_at <= at - timedelta(seconds=seconds)
        stmt = insert(AuthThrottle).values(key=key, started_at=at, count=1)
        stmt = stmt.on_conflict_do_update(index_elements=[AuthThrottle.key], set_={
            'count': case((expired, 1), else_=AuthThrottle.count + 1),
            'started_at': case((expired, at), else_=AuthThrottle.started_at),
        }, where=or_(expired, AuthThrottle.count < limit)).returning(AuthThrottle.key)
        with self.factory.begin() as db:
            accepted = db.scalar(stmt)
        if accepted is None:
            raise HTTPException(429, 'too many attempts; try again later', headers={'Retry-After': str(seconds)})

    def issue_grant(self, email, kind):
        email = email.strip().lower()
        token = secrets.token_urlsafe(32)
        at = now()
        if kind not in ('invite', 'recovery'):
            raise HTTPException(422, 'invalid grant kind')
        with self.factory.begin() as db:
            if kind == 'invite':
                # New invited members start on the Individual entitlement:
                # one linked account and one active game session. Operators
                # can explicitly raise these limits for Alliance access.
                db.execute(
                    insert(User)
                    .values(
                        email=email,
                        role='member',
                        status='invited',
                        max_accounts=1,
                        max_active_accounts=1,
                        max_sessions=5,
                    )
                    .on_conflict_do_nothing(index_elements=[User.email])
                )
            user = db.scalar(select(User).where(User.email == email).with_for_update())
            allowed = user and user.role in VALID_ROLES and (
                (kind == 'invite' and user.role == 'member' and user.status == 'invited' and not user.password_hash)
                or (kind == 'recovery' and user.status == 'active' and user.password_hash))
            if not allowed:
                raise HTTPException(409, 'identity is not eligible for this grant; explicit operator review required')
            db.execute(update(PilotGrant).where(PilotGrant.user_id == user.id,
                                               PilotGrant.consumed_at.is_(None)).values(consumed_at=at))
            expiry = at + timedelta(hours=48 if kind == 'invite' else 1)
            db.add(PilotGrant(token_hash=digest(token), user_id=user.id, kind=kind, auth_version=user.auth_version,
                              created_at=at, expires_at=expiry))
        return {'token': token, 'expires_at': expiry, 'kind': kind}

    def redeem(self, token, password):
        password_hash = hash_password(password)
        at = now()
        with self.factory.begin() as db:
            user_id = db.scalar(select(PilotGrant.user_id).where(PilotGrant.token_hash == digest(token)))
            user = db.get(User, user_id, with_for_update=True) if user_id else None
            grant = db.get(PilotGrant, digest(token), with_for_update=True) if user else None
            allowed = (grant and not grant.consumed_at and grant.expires_at > at and
                       grant.auth_version == user.auth_version and user.role in VALID_ROLES and (
                           (grant.kind == 'invite' and user.role == 'member' and user.status == 'invited' and not user.password_hash)
                           or (grant.kind == 'recovery' and user.status == 'active' and user.password_hash)))
            if not allowed:
                raise HTTPException(400, 'grant invalid or expired')
            user.password_hash = password_hash
            user.status = 'active'
            user.auth_version += 1
            db.execute(update(PilotGrant).where(PilotGrant.user_id == user.id).values(consumed_at=at))
            db.execute(update(WebsiteSession).where(WebsiteSession.user_id == user.id).values(revoked_at=at))

    def update_user(self, user_id, *, status, max_accounts, max_sessions, max_active_accounts, player_scout_access=None):
        with self.factory.begin() as db:
            user = db.get(User, user_id, with_for_update=True)
            if user is None or user.role not in VALID_ROLES or not user.password_hash or user.status == 'invited':
                raise HTTPException(409, 'identity requires explicit provisioning')
            user.status = status
            user.max_accounts = max_accounts
            user.max_sessions = max_sessions
            user.max_active_accounts = max_active_accounts
            if player_scout_access is not None:
                user.player_scout_access = bool(player_scout_access)
            user.auth_version += 1

    def cleanup(self):
        at = now()
        with self.factory.begin() as db:
            db.execute(delete(AuthThrottle).where(AuthThrottle.started_at < at - timedelta(days=1)))
            db.execute(delete(WebsiteSession).where(WebsiteSession.expires_at < at - timedelta(days=7)))
            db.execute(delete(PilotGrant).where(PilotGrant.expires_at < at - timedelta(days=7)))
