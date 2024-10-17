"""delete-id-from-comment

Revision ID: 656228b2d6e0
Revises: 7354951f8e4c
Create Date: 2024-10-17 15:30:15.168365

"""

import sqlalchemy as sa
from alembic import op

revision = '656228b2d6e0'
down_revision = '7354951f8e4c'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('comment', 'id')


def downgrade():
    op.add_column('comment', sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False))
