"""add dashboard login columns to users: password_hash, role

Revision ID: 0003_dashboard_auth_columns
Revises: 0002_fix_email_unique_index
Create Date: 2026-09-15

Reuses the existing `users` table for dashboard logins rather than adding a
second user system (see app/db/models.py's User docstring and
app/security/passwords.py). Both columns are nullable: every existing User
row (created via the account-linking flow or DEV_USER_EMAIL) keeps
password_hash/role as NULL and remains a Warpath-account owner only, not a
dashboard login. A row only becomes a dashboard login once
scripts/bootstrap_dashboard_admins.py sets password_hash for it.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0003_dashboard_auth_columns'
down_revision: Union[str, None] = '0002_fix_email_unique_index'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_hash', sa.String(length=256), nullable=True))
    op.add_column('users', sa.Column('role', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'role')
    op.drop_column('users', 'password_hash')
