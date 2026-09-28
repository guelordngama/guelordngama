"""add false alarm fields to alerts + role/alert_id to audit logs

Revision ID: a4d8c2e6f0b1
Revises: f3c7a9e1b5d2
Create Date: 2026-09-28 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4d8c2e6f0b1'
down_revision = 'f3c7a9e1b5d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('false_alarm', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
        batch_op.add_column(sa.Column('false_alarm_reason', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('false_alarm_by', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('false_alarm_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_alerts_false_alarm', ['false_alarm'], unique=False)
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('alert_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_audit_logs_alert_id', ['alert_id'], unique=False)


def downgrade():
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index('ix_audit_logs_alert_id')
        batch_op.drop_column('alert_id')
        batch_op.drop_column('role')
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_index('ix_alerts_false_alarm')
        batch_op.drop_column('false_alarm_at')
        batch_op.drop_column('false_alarm_by')
        batch_op.drop_column('false_alarm_reason')
        batch_op.drop_column('false_alarm')
