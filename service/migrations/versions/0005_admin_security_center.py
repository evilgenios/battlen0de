"""Admin security center: MFA state and dedicated operator audit trail."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005_admin_security_center'
down_revision = '0004_customer_identity'
branch_labels = depends_on = None


def upgrade():
    op.add_column('users', sa.Column('mfa_secret_encrypted', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    op.create_table(
        'admin_audit_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor_email', sa.String(320), nullable=True),
        sa.Column('action', sa.String(96), nullable=False),
        sa.Column('target_type', sa.String(32), nullable=False),
        sa.Column('target_id', sa.String(128), nullable=True),
        sa.Column('outcome', sa.String(16), nullable=False),
        sa.Column('peer_ip', sa.String(64), nullable=True),
        sa.Column('user_agent', sa.String(300), nullable=True),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_admin_audit_events_actor_user_id', 'admin_audit_events', ['actor_user_id'])
    op.create_index('ix_admin_audit_events_action', 'admin_audit_events', ['action'])
    op.create_index('ix_admin_audit_events_created_at', 'admin_audit_events', ['created_at'])


def downgrade():
    op.drop_table('admin_audit_events')
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'mfa_secret_encrypted')
