"""lecturer-rating

Revision ID: 687b0ca503b8
Revises: fc7cb93684e0
Create Date: 2025-08-22 21:16:52.770661

"""

import sqlalchemy as sa
from alembic import op


revision = '687b0ca503b8'
down_revision = 'fc7cb93684e0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'lecturer_rating',
        sa.Column('id', sa.Integer(), nullable=False, comment='Идентификатор препода'),
        sa.Column(
            'mark_weighted', sa.Float(), nullable=False, comment='Взвешенная оценка преподавателя, посчитана в dwh'
        ),
        sa.Column(
            'mark_kindness_weighted', sa.Float(), nullable=False, comment='Взвешенная оценка доброты, посчитана в dwh'
        ),
        sa.Column(
            'mark_clarity_weighted', sa.Float(), nullable=False, comment='Взвешенная оценка понятности, посчитана в dwh'
        ),
        sa.Column(
            'mark_freebie_weighted', sa.Float(), nullable=False, comment='Взвешенная оценка халявности, посчитана в dwh'
        ),
        sa.Column('rank', sa.Integer(), nullable=False, comment='Место в рейтинге, посчитана в dwh'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('lecturer_rating')
