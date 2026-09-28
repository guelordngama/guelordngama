"""add incident_number to alerts (numéro d'intervention « SC-AAAA-NNNN »)

Revision ID: f3c7a9e1b5d2
Revises: e9b2d4f6a8c1
Create Date: 2026-09-28 18:30:00.000000

"""
from datetime import timedelta

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3c7a9e1b5d2'
down_revision = 'e9b2d4f6a8c1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('incident_number', sa.String(length=20), nullable=True))
        batch_op.create_index('ix_alerts_incident_number', ['incident_number'], unique=True)

    # Numérotation des incidents existants (principaux uniquement), par ordre
    # chronologique et par année (heure de Lubumbashi = UTC+2).
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, created_at FROM alerts WHERE duplicate_of_id IS NULL "
        "ORDER BY created_at, id")).fetchall()
    counters = {}
    for alert_id, created_at in rows:
        if isinstance(created_at, str):
            from datetime import datetime
            created_at = datetime.fromisoformat(created_at.split(".")[0])
        year = (created_at + timedelta(hours=2)).year if created_at else 2026
        counters[year] = counters.get(year, 0) + 1
        bind.execute(sa.text("UPDATE alerts SET incident_number = :n WHERE id = :i"),
                     {"n": f"SC-{year}-{counters[year]:04d}", "i": alert_id})


def downgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_index('ix_alerts_incident_number')
        batch_op.drop_column('incident_number')
