"""Restrict Player Scout / Player Locate to explicitly entitled customers."""

from alembic import op
import sqlalchemy as sa

revision = '0006_player_scout_access'
down_revision = '0005_admin_security_center'
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column(
            'player_scout_access',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column('users', 'player_scout_access')
