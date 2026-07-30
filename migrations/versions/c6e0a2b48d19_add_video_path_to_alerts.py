"""add video_path to alerts (vidéo jointe par le citoyen)

Revision ID: c6e0a2b48d19
Revises: b4d8f1a3c705
Create Date: 2026-07-27 10:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6e0a2b48d19'
down_revision = 'b4d8f1a3c705'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('video_path', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_column('video_path')
