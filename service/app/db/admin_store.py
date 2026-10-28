"""Administrative security/audit persistence and MFA helpers."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, Request
from sqlalchemy import delete, func, select

from app.db.models import AdminAuditEvent, User, WarpathAccount, WebsiteSession
from app.security.crypto import decrypt_secret, encrypt_secret
from app.security.totp import generate_secret, provisioning_uri, verify

_SENSITIVE_MARKERS = ('password', 'token', 'secret', 'code', 'device_id', 'authorization', 'cookie')


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _scrub(value: Any, *, key: str = '') -> Any:
    lowered = key.lower()
    if any(marker in lowered for marker in _SENSITIVE_MARKERS):
        return '[redacted]'
    if isinstance(value, dict):
        return {str(k): _scrub(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value[:50]]
    if isinstance(value, tuple):
        return [_scrub(v) for v in value[:50]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


class AdminSecurityStore:
    idle_timeout_seconds = 7200

    def __init__(self, session_factory):
        self.factory = session_factory

    def audit(
        self,
        *,
        action: str,
        target_type: str,
        outcome: str,
        actor_user_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        target_id: Optional[str] = None,
        request: Optional[Request] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        peer_ip = request.client.host[:64] if request and request.client and request.client.host else None
        user_agent = request.headers.get('user-agent', '')[:300] if request else None
        row = AdminAuditEvent(
            actor_user_id=actor_user_id,
            actor_email=(actor_email or None),
            action=action[:96],
            target_type=target_type[:32],
            target_id=(target_id[:128] if target_id else None),
            outcome=outcome[:16],
            peer_ip=peer_ip,
            user_agent=user_agent or None,
            detail=_scrub(detail or {}),
        )
        with self.factory.begin() as db:
            db.add(row)

    def list_audit(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        with self.factory() as db:
            stmt = select(AdminAuditEvent).order_by(AdminAuditEvent.created_at.desc())
            if action:
                stmt = stmt.where(AdminAuditEvent.action == action)
            if outcome:
                stmt = stmt.where(AdminAuditEvent.outcome == outcome)
            rows = db.scalars(stmt.limit(limit).offset(offset)).all()
            return [
                {
                    'id': row.id,
                    'actor_user_id': str(row.actor_user_id) if row.actor_user_id else None,
                    'actor_email': row.actor_email,
                    'action': row.action,
                    'target_type': row.target_type,
                    'target_id': row.target_id,
                    'outcome': row.outcome,
                    'peer_ip': row.peer_ip,
                    'user_agent': row.user_agent,
                    'detail': dict(row.detail or {}),
                    'created_at': row.created_at,
                }
                for row in rows
            ]

    def list_users(self, *, query: str = '', limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        at = _now()
        query = query.strip().lower()
        with self.factory() as db:
            account_count = (
                select(func.count())
                .select_from(WarpathAccount)
                .where(WarpathAccount.owner_user_id == User.id)
                .correlate(User)
                .scalar_subquery()
            )
            session_count = (
                select(func.count())
                .select_from(WebsiteSession)
                .where(
                    WebsiteSession.user_id == User.id,
                    WebsiteSession.revoked_at.is_(None),
                    WebsiteSession.expires_at > at,
                    WebsiteSession.last_used_at > at - timedelta(seconds=self.idle_timeout_seconds),
                    WebsiteSession.auth_version == User.auth_version,
                )
                .correlate(User)
                .scalar_subquery()
            )
            stmt = select(User, account_count.label('account_count'), session_count.label('session_count'))
            if query:
                stmt = stmt.where(User.email.ilike(f'%{query}%'))
            stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
            rows = db.execute(stmt).all()
            return [
                {
                    'id': str(user.id),
                    'email': user.email,
                    'role': user.role,
                    'status': user.status,
                    'plan': 'alliance' if user.max_accounts > 1 else 'individual',
                    'max_accounts': user.max_accounts,
                    'max_sessions': user.max_sessions,
                    'max_active_accounts': user.max_active_accounts,
                    'mfa_enabled': bool(user.mfa_enabled),
                    'player_scout_access': bool(user.player_scout_access),
                    'account_count': int(accounts or 0),
                    'active_sessions': int(sessions or 0),
                    'created_at': user.created_at,
                    'updated_at': user.updated_at,
                }
                for user, accounts, sessions in rows
            ]

    def mfa_status(self, user_id: uuid.UUID) -> dict[str, bool]:
        with self.factory() as db:
            user = db.get(User, user_id)
            if user is None:
                raise HTTPException(404, 'user not found')
            return {
                'enabled': bool(user.mfa_enabled),
                'setup_pending': bool(user.mfa_secret_encrypted and not user.mfa_enabled),
            }

    def begin_mfa_setup(self, user_id: uuid.UUID) -> dict[str, str]:
        secret = generate_secret()
        with self.factory.begin() as db:
            user = db.get(User, user_id, with_for_update=True)
            if user is None:
                raise HTTPException(404, 'user not found')
            if user.role != 'admin':
                raise HTTPException(403, 'administrator role required')
            if user.mfa_enabled:
                raise HTTPException(409, 'MFA is already enabled')
            user.mfa_secret_encrypted = encrypt_secret(secret)
            return {'secret': secret, 'otpauth_uri': provisioning_uri(secret, user.email)}

    def enable_mfa(self, user_id: uuid.UUID, code: str) -> None:
        with self.factory.begin() as db:
            user = db.get(User, user_id, with_for_update=True)
            if user is None or user.role != 'admin':
                raise HTTPException(404, 'administrator not found')
            if not user.mfa_secret_encrypted:
                raise HTTPException(409, 'MFA setup has not been started')
            secret = decrypt_secret(user.mfa_secret_encrypted)
            if not verify(secret, code):
                raise HTTPException(422, 'invalid authenticator code')
            user.mfa_enabled = True
            user.auth_version += 1
            db.query(WebsiteSession).filter(WebsiteSession.user_id == user.id).update({'revoked_at': _now()})

    def disable_mfa(self, user_id: uuid.UUID, code: str) -> None:
        with self.factory.begin() as db:
            user = db.get(User, user_id, with_for_update=True)
            if user is None or user.role != 'admin':
                raise HTTPException(404, 'administrator not found')
            if not user.mfa_enabled or not user.mfa_secret_encrypted:
                raise HTTPException(409, 'MFA is not enabled')
            if not verify(decrypt_secret(user.mfa_secret_encrypted), code):
                raise HTTPException(422, 'invalid authenticator code')
            user.mfa_enabled = False
            user.mfa_secret_encrypted = None
            user.auth_version += 1
            db.query(WebsiteSession).filter(WebsiteSession.user_id == user.id).update({'revoked_at': _now()})

    def cleanup(self) -> None:
        days = max(30, min(730, int(os.environ.get('ADMIN_AUDIT_RETENTION_DAYS', '180'))))
        cutoff = _now() - timedelta(days=days)
        with self.factory.begin() as db:
            db.execute(delete(AdminAuditEvent).where(AdminAuditEvent.created_at < cutoff))

    def verify_login_mfa(self, user_id: uuid.UUID, code: Optional[str]) -> tuple[bool, bool]:
        """Returns (required, valid)."""
        with self.factory() as db:
            user = db.get(User, user_id)
            if user is None or user.role != 'admin' or not user.mfa_enabled:
                return False, True
            if not user.mfa_secret_encrypted:
                return True, False
            return True, verify(decrypt_secret(user.mfa_secret_encrypted), code)
