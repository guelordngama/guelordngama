"""add avatar_path to users (photo de profil citoyens/personnel)

Revision ID: b8e2f4a6c9d3
Revises: a4d8c2e6f0b1
Create Date: 2026-10-01 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e2f4a6c9d3'
down_revision = 'a4d8c2e6f0b1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('avatar_path', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('avatar_path')
