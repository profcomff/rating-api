"""add-uuid-to-comment

Revision ID: 7354951f8e4c
Revises: dbe6ca79a40d
Create Date: 2024-10-17 15:25:02.529966

"""
import sqlalchemy as sa
from alembic import op


revision = '7354951f8e4c'
down_revision = 'dbe6ca79a40d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('comment', sa.Column('uuid', sa.UUID(), nullable=True))
    op.execute(f'UPDATE "comment" SET uuid = gen_random_uuid()')
    op.alter_column('comment', 'uuid', nullable=False)


def downgrade():
    op.drop_column('comment', 'uuid')
