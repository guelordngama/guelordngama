"""add citizen<->operator messages and citizen cancellation of alerts

Revision ID: f4b8d0a2c6e3
Revises: e3a7c9b1d5f2
Create Date: 2026-10-13 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4b8d0a2c6e3'
down_revision = 'e3a7c9b1d5f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cancelled_by_citizen', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('cancel_reason', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('cancelled_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('citizen_msg_unread', sa.Integer(),
                                      nullable=False, server_default='0'))
    op.create_table(
        'alert_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('sender', sa.String(length=10), nullable=False),
        sa.Column('sender_name', sa.String(length=120), nullable=True),
        sa.Column('text', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_alert_messages_alert_id'), 'alert_messages', ['alert_id'])
    op.create_index(op.f('ix_alert_messages_created_at'), 'alert_messages', ['created_at'])


def downgrade():
    op.drop_index(op.f('ix_alert_messages_created_at'), table_name='alert_messages')
    op.drop_index(op.f('ix_alert_messages_alert_id'), table_name='alert_messages')
    op.drop_table('alert_messages')
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_column('citizen_msg_unread')
        batch_op.drop_column('cancelled_at')
        batch_op.drop_column('cancel_reason')
        batch_op.drop_column('cancelled_by_citizen')
