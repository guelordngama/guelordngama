"""add voice_duration to messages

Revision ID: c4e8f2a1b6d7
Revises: b3d7e1f2a9c4
Create Date: 2026-07-24 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e8f2a1b6d7'
down_revision = 'b3d7e1f2a9c4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voice_duration', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_column('voice_duration')
