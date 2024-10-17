"""init

Revision ID: dbe6ca79a40d
Revises:
Create Date: 2024-10-16 23:21:37.960911

"""

import sqlalchemy as sa
from alembic import op


revision = 'dbe6ca79a40d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'lecturer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('middle_name', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('avatar_link', sa.String(), nullable=True),
        sa.Column('timetable_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('timetable_id'),
    )
    op.create_table(
        'comment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('create_ts', sa.DateTime(), nullable=False),
        sa.Column('update_ts', sa.DateTime(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('text', sa.String(), nullable=True),
        sa.Column('mark_kindness', sa.Integer(), nullable=False),
        sa.Column('mark_freebie', sa.Integer(), nullable=False),
        sa.Column('mark_clarity', sa.Integer(), nullable=False),
        sa.Column('lecturer_id', sa.Integer(), nullable=False),
        sa.Column(
            'review_status',
            sa.Enum('APPROVED', 'PENDING', 'DISMISSED', name='reviewstatus', native_enum=False),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['lecturer_id'],
            ['lecturer.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'lecturer_user_comment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lecturer_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('create_ts', sa.DateTime(), nullable=False),
        sa.Column('update_ts', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['lecturer_id'],
            ['lecturer.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('lecturer_user_comment')
    op.drop_table('comment')
    op.drop_table('lecturer')
