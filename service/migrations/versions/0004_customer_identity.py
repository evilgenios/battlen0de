"""Durable website identity and canonical game accounts. See PHASE3_MIGRATION.md.

Requires a stopped single worker. Duplicates abort; no ownership is inferred.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0004_customer_identity'
down_revision = '0003_dashboard_auth_columns'
branch_labels = depends_on = None

# Frozen migration expression (do not import evolving application logic).
CANONICAL = "CASE WHEN btrim(app_uid) ~ '^[0-9]{1,64}$' AND ltrim(btrim(app_uid), '0') <> '' THEN 'warpath:lilith:' || ltrim(btrim(app_uid), '0') ELSE NULL END"


def upgrade():
    # Lock out concurrent legacy writers throughout preflight and index creation.
    op.execute('LOCK TABLE warpath_accounts IN ACCESS EXCLUSIVE MODE')
    duplicate = op.get_bind().execute(sa.text(
        f'SELECT 1 FROM warpath_accounts GROUP BY ({CANONICAL}) '
        f'HAVING ({CANONICAL}) IS NOT NULL AND count(*) > 1 LIMIT 1'
    )).first()
    if duplicate:
        raise RuntimeError('Duplicate canonical Warpath identities: reconcile ownership offline before migration. No rows were merged.')
    for name, kind, default in [('status', sa.String(32), 'active'), ('auth_version', sa.Integer(), '0'),
                                ('max_accounts', sa.Integer(), '5'), ('max_sessions', sa.Integer(), '5'),
                                ('max_active_accounts', sa.Integer(), '2')]:
        op.add_column('users', sa.Column(name, kind, server_default=default, nullable=False))
    op.create_check_constraint('positive_limits', 'users', 'max_accounts > 0 AND max_sessions > 0 AND max_active_accounts > 0')
    op.add_column('warpath_accounts', sa.Column('canonical_identity', sa.String(80), sa.Computed(CANONICAL, persisted=True), nullable=True))
    op.create_unique_constraint('uq_warpath_accounts_canonical_identity', 'warpath_accounts', ['canonical_identity'])
    op.execute("UPDATE warpath_accounts SET status='needs_reauth' WHERE canonical_identity IS NULL AND status NOT IN ('disabled','restricted')")
    op.create_table('website_sessions',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('auth_version', sa.Integer(), nullable=False),
        sa.Column('csrf_token', sa.String(64), nullable=False),
        sa.Column('cache_key', sa.String(64), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('pilot_grants',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('auth_version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('auth_throttles',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False))
    for table in ('website_sessions', 'pilot_grants'):
        for column in ('user_id', 'expires_at'):
            op.create_index(f'ix_{table}_{column}', table, [column])
    op.create_index('ix_auth_throttles_started_at', 'auth_throttles', ['started_at'])


def downgrade():
    for table in ('auth_throttles', 'pilot_grants', 'website_sessions'):
        op.drop_table(table)
    op.drop_constraint('uq_warpath_accounts_canonical_identity', 'warpath_accounts', type_='unique')
    op.drop_column('warpath_accounts', 'canonical_identity')
    op.drop_constraint(op.f('ck_users_positive_limits'), 'users', type_='check')
    for column in ('max_active_accounts', 'max_sessions', 'max_accounts', 'auth_version', 'status'):
        op.drop_column('users', column)
