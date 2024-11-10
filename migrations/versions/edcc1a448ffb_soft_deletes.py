"""soft-deletes

Revision ID: edcc1a448ffb
Revises: 7388a2c219d2
Create Date: 2024-11-10 09:23:32.307828

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'edcc1a448ffb'
down_revision = '7388a2c219d2'
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
