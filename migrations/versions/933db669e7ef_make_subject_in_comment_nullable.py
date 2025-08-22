"""make subject in comment nullable

Revision ID: 933db669e7ef
Revises: 20181e0d6aab
Create Date: 2024-12-07 18:57:13.280516

"""

import sqlalchemy as sa
from alembic import op


revision = '933db669e7ef'
down_revision = '20181e0d6aab'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('comment', 'subject', existing_type=sa.VARCHAR(), nullable=True)


def downgrade():
    op.alter_column('comment', 'subject', existing_type=sa.VARCHAR(), nullable=False)
