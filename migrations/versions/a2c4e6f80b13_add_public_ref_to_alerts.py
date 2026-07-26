"""add public_ref to alerts (suivi citoyen par référence)

Revision ID: a2c4e6f80b13
Revises: e7a1c9d4f2b6
Create Date: 2026-07-26 16:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2c4e6f80b13'
down_revision = 'e7a1c9d4f2b6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('public_ref', sa.String(length=16), nullable=True))
        batch_op.create_index(batch_op.f('ix_alerts_public_ref'), ['public_ref'], unique=True)


def downgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alerts_public_ref'))
        batch_op.drop_column('public_ref')
