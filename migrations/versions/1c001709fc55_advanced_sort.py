"""advanced_sort

Revision ID: 1c001709fc55
Revises: dd44854aa12a
Create Date: 2025-04-26 17:01:57.140143

"""

import sqlalchemy as sa
from alembic import op

revision = "1c001709fc55"
down_revision = "dd44854aa12a"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("comment", "approved_by", existing_type=sa.INTEGER(), nullable=True)


def downgrade():
    op.alter_column(
        "comment", "approved_by", existing_type=sa.INTEGER(), nullable=False
    )
