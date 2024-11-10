"""delete-user-id-from-lectureruser

Revision ID: fee34ac4fcab
Revises: 0fbda260a023
Create Date: 2024-11-10 02:38:49.538788

"""

import sqlalchemy as sa
from alembic import op


revision = 'fee34ac4fcab'
down_revision = '0fbda260a023'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('lecturer_user_comment', 'user_id')


def downgrade():
    op.add_column('lecturer_user_comment', sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False))
