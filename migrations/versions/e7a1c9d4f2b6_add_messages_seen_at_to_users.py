"""add messages_seen_at to users

Revision ID: e7a1c9d4f2b6
Revises: d5f9a3c1e8b2
Create Date: 2026-07-25 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a1c9d4f2b6'
down_revision = 'd5f9a3c1e8b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('messages_seen_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('messages_seen_at')
