"""add voice_path to messages

Revision ID: b3d7e1f2a9c4
Revises: a85802cdc489
Create Date: 2026-07-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3d7e1f2a9c4'
down_revision = 'a85802cdc489'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voice_path', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_column('voice_path')
