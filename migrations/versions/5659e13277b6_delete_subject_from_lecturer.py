"""delete-subject-from-lecturer

Revision ID: 5659e13277b6
Revises: 656228b2d6e0
Create Date: 2024-10-24 23:55:41.835641

"""

import sqlalchemy as sa
from alembic import op

revision = "5659e13277b6"
down_revision = "656228b2d6e0"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("lecturer", "subject")


def downgrade():
    op.add_column(
        "lecturer",
        sa.Column("subject", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
