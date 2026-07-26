"""add duplicate_of_id to alerts (regroupement de doublons)

Revision ID: b4d8f1a3c705
Revises: a2c4e6f80b13
Create Date: 2026-07-26 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4d8f1a3c705'
down_revision = 'a2c4e6f80b13'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('duplicate_of_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_alerts_duplicate_of_id'), ['duplicate_of_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_alerts_duplicate_of_id', 'alerts', ['duplicate_of_id'], ['id'])


def downgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_alerts_duplicate_of_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_alerts_duplicate_of_id'))
        batch_op.drop_column('duplicate_of_id')
