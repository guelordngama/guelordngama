"""add position_updated_at to alerts (suivi en direct de la position du citoyen)

Revision ID: d2f6b8a0c4e1
Revises: c1d3e5f7a9b2
Create Date: 2026-10-11 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2f6b8a0c4e1'
down_revision = 'c1d3e5f7a9b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position_updated_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_column('position_updated_at')
