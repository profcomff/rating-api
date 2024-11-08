"""add user_id

Revision ID: 0fbda260a023
Revises: 5659e13277b6
Create Date: 2024-11-08 12:49:18.796942

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0fbda260a023'
down_revision = '5659e13277b6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('comment', sa.Column('user_id', sa.Integer(), nullable=True))
    op.alter_column('lecturer_user_comment', 'user_id', existing_type=sa.INTEGER(), nullable=True)


def downgrade():
    op.alter_column('lecturer_user_comment', 'user_id', existing_type=sa.INTEGER(), nullable=False)
    op.drop_column('comment', 'user_id')
