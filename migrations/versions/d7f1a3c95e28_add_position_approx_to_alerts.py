"""add position_approx to alerts (position GPS non obtenue)

Revision ID: d7f1a3c95e28
Revises: c6e0a2b48d19
Create Date: 2026-07-30 23:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7f1a3c95e28'
down_revision = 'c6e0a2b48d19'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position_approx', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_column('position_approx')
