"""add-user-id-to-lecturer-user

Revision ID: 7388a2c219d2
Revises: fee34ac4fcab
Create Date: 2024-11-10 04:07:42.997861

"""

import sqlalchemy as sa
from alembic import op

revision = "7388a2c219d2"
down_revision = "fee34ac4fcab"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lecturer_user_comment", sa.Column("user_id", sa.Integer(), nullable=False)
    )


def downgrade():
    op.drop_column("lecturer_user_comment", "user_id")
