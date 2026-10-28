"""fix users.email uniqueness representation: one unique index instead of
a separate unique constraint + separate non-unique index

Revision ID: 0002_fix_email_unique_index
Revises: 0001_initial_schema
Create Date: 2026-09-10

0001_initial_schema (hand-written, no live database available to
autogenerate against at the time) created `uq_users_email` as a separate
UNIQUE CONSTRAINT and `ix_users_email` as a separate, non-unique INDEX on
the same column. app/db/models.py's `mapped_column(unique=True,
index=True)` actually represents a single merged unique index, not those
two objects — `alembic check`, run for the first time against a real
database after 0001 was applied, correctly flagged this as drift. This
migration reconciles the live schema to match the model: no behavior change
(email was already effectively unique and indexed either way), just one
index object instead of two redundant ones. See the Stage 3 follow-up
report for how this was found.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = '0002_fix_email_unique_index'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f('uq_users_email'), 'users', type_='unique')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_unique_constraint(op.f('uq_users_email'), 'users', ['email'])
