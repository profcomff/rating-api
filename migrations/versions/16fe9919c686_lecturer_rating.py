"""lecturer-rating

Revision ID: 16fe9919c686
Revises: fc7cb93684e0
Create Date: 2025-08-24 00:25:32.995215

"""

import sqlalchemy as sa
from alembic import op


revision = '16fe9919c686'
down_revision = 'fc7cb93684e0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'lecturer_rating',
        sa.Column('id', sa.Integer(), nullable=False, comment='Идентификатор препода'),
        sa.Column(
            'mark_weighted', sa.Float(), nullable=True, comment='Взвешенная оценка преподавателя, посчитана в dwh'
        ),
        sa.Column(
            'mark_kindness_weighted', sa.Float(), nullable=True, comment='Взвешенная оценка доброты, посчитана в dwh'
        ),
        sa.Column(
            'mark_clarity_weighted', sa.Float(), nullable=True, comment='Взвешенная оценка понятности, посчитана в dwh'
        ),
        sa.Column(
            'mark_freebie_weighted', sa.Float(), nullable=True, comment='Взвешенная оценка халявности, посчитана в dwh'
        ),
        sa.Column('rank', sa.Integer(), nullable=True, comment='Место в рейтинге, посчитана в dwh'),
        sa.Column('update_ts', sa.DateTime(), nullable=True, comment='Время обновления записи'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('lecturer_rating')
