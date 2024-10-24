"""adding_is_deleted_fields

Revision ID: 0c117913717b
Revises: 656228b2d6e0
Create Date: 2024-10-24 06:59:27.285029

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '0c117913717b'
down_revision = '656228b2d6e0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('comment', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('lecturer', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        'lecturer_user_comment', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade():
    op.drop_column('lecturer_user_comment', 'is_deleted')
    op.drop_column('lecturer', 'is_deleted')
    op.drop_column('comment', 'is_deleted')
