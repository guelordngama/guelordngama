"""add stage and arrived_at to alerts (progression Nouvelle→Reçue→Assignée→
Agent en route→Sur place→Résolue, additif : ne change pas `status`)

Revision ID: c1d3e5f7a9b2
Revises: b8e2f4a6c9d3
Create Date: 2026-10-02 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d3e5f7a9b2'
down_revision = 'b8e2f4a6c9d3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stage', sa.String(length=20), nullable=False,
                                      server_default='received'))
        batch_op.add_column(sa.Column('arrived_at', sa.DateTime(), nullable=True))

    # Alertes existantes : reconstitue une progression cohérente avec leur
    # statut actuel (sans quoi une alerte déjà clôturée afficherait « Reçue »).
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE alerts SET stage = 'assigned' "
        "WHERE status = 'assignee' AND accepted_at IS NOT NULL"
    ))
    conn.execute(sa.text(
        "UPDATE alerts SET stage = 'resolved' WHERE status = 'cloturee'"
    ))


def downgrade():
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_column('arrived_at')
        batch_op.drop_column('stage')
