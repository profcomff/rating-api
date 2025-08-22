"""likes

Revision ID: fc7cb93684e0
Revises: 1c001709fc55
Create Date: 2025-07-27 05:50:58.474948

"""

import sqlalchemy as sa
from alembic import op


revision = 'fc7cb93684e0'
down_revision = '1c001709fc55'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'comment_reaction',
        sa.Column('uuid', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('comment_uuid', sa.UUID(), nullable=False),
        sa.Column('reaction', sa.Enum('LIKE', 'DISLIKE', name='reaction', native_enum=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('edited_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['comment_uuid'],
            ['comment.uuid'],
        ),
        sa.PrimaryKeyConstraint('uuid'),
    )


def downgrade():
    op.drop_table('comment_reaction')
