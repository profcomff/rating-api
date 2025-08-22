"""fixing comments pk

Revision ID: 5cf69f1026d9
Revises: 933db669e7ef
Create Date: 2024-12-11 21:58:13.081083

"""

from alembic import op


revision = '5cf69f1026d9'
down_revision = '933db669e7ef'
branch_labels = None
depends_on = None


def upgrade():
    op.create_primary_key('pk_comment', 'comment', ['uuid'])


def downgrade():
    op.drop_constraint('pk_comment', 'comment', type_='primary')
