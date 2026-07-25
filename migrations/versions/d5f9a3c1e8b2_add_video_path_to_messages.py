"""add video_path to messages

Revision ID: d5f9a3c1e8b2
Revises: c4e8f2a1b6d7
Create Date: 2026-07-25 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5f9a3c1e8b2'
down_revision = 'c4e8f2a1b6d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('video_path', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_column('video_path')
