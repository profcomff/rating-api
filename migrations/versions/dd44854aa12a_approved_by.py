"""approved_by

Revision ID: dd44854aa12a
Revises: 5cf69f1026d9
Create Date: 2025-04-12 07:55:31.393429

"""

import sqlalchemy as sa
from alembic import op


revision = 'dd44854aa12a'
down_revision = '5cf69f1026d9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('comment', sa.Column('approved_by', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('comment', 'approved_by')
