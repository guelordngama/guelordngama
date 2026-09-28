"""add location details to alerts (avenue/rue, commune, ville, précision GPS)

Revision ID: e9b2d4f6a8c1
Revises: d7f1a3c95e28
Create Date: 2026-09-28 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9b2d4f6a8c1'
down_revision = 'd7f1a3c95e28'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('street', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('commune', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('city', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('gps_accuracy_m', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('position_manual', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))
        batch_op.create_index('ix_alerts_commune', ['commune'], unique=False)


def downgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_index('ix_alerts_commune')
        batch_op.drop_column('position_manual')
        batch_op.drop_column('gps_accuracy_m')
        batch_op.drop_column('city')
        batch_op.drop_column('commune')
        batch_op.drop_column('street')
