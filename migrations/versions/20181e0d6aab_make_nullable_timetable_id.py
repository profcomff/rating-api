"""make nullable timetable_id

Revision ID: 20181e0d6aab
Revises: edcc1a448ffb
Create Date: 2024-11-30 18:45:08.527638

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20181e0d6aab'
down_revision = 'edcc1a448ffb'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('lecturer_timetable_id_key', 'lecturer', type_='unique')


def downgrade():
    op.create_unique_constraint('lecturer_timetable_id_key', 'lecturer', ['timetable_id'])
