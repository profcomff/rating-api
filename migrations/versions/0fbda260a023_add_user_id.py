"""add user_id

Revision ID: 0fbda260a023
Revises: 5659e13277b6
Create Date: 2024-11-08 12:49:18.796942

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0fbda260a023"
down_revision = "5659e13277b6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("comment", sa.Column("user_id", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("comment", "user_id")
