"""lecturer-rating

Revision ID: beb11fd89531
Revises: fc7cb93684e0
Create Date: 2025-08-25 14:59:47.363354

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "beb11fd89531"
down_revision = "fc7cb93684e0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lecturer",
        sa.Column(
            "mark_weighted",
            sa.Float(),
            server_default="0.0",
            nullable=False,
            comment="Взвешенная оценка преподавателя, посчитана в dwh",
        ),
    )
    op.add_column(
        "lecturer",
        sa.Column(
            "mark_kindness_weighted",
            sa.Float(),
            server_default="0.0",
            nullable=False,
            comment="Взвешенная оценка доброты, посчитана в dwh",
        ),
    )
    op.add_column(
        "lecturer",
        sa.Column(
            "mark_clarity_weighted",
            sa.Float(),
            server_default="0.0",
            nullable=False,
            comment="Взвешенная оценка понятности, посчитана в dwh",
        ),
    )
    op.add_column(
        "lecturer",
        sa.Column(
            "mark_freebie_weighted",
            sa.Float(),
            server_default="0.0",
            nullable=False,
            comment="Взвешенная оценка халявности, посчитана в dwh",
        ),
    )
    op.add_column(
        "lecturer",
        sa.Column(
            "rank",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Место в рейтинге, посчитана в dwh",
        ),
    )
    op.add_column(
        "lecturer",
        sa.Column(
            "rank_update_ts",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            comment="Время обновления записи",
        ),
    )
    op.alter_column(
        "lecturer",
        "id",
        existing_type=sa.INTEGER(),
        comment="Идентификатор преподавателя",
        existing_nullable=False,
        autoincrement=True,
        existing_server_default=sa.text("nextval('lecturer_id_seq'::regclass)"),
    )
    op.alter_column(
        "lecturer",
        "first_name",
        existing_type=sa.VARCHAR(),
        comment="Имя препода",
        existing_nullable=False,
    )
    op.alter_column(
        "lecturer",
        "last_name",
        existing_type=sa.VARCHAR(),
        comment="Фамилия препода",
        existing_nullable=False,
    )
    op.alter_column(
        "lecturer",
        "middle_name",
        existing_type=sa.VARCHAR(),
        comment="Отчество препода",
        existing_nullable=False,
    )
    op.alter_column(
        "lecturer",
        "avatar_link",
        existing_type=sa.VARCHAR(),
        comment="Ссылка на аву препода",
        existing_nullable=True,
    )
    op.alter_column(
        "lecturer",
        "is_deleted",
        existing_type=sa.BOOLEAN(),
        comment="Идентификатор софт делита",
        existing_nullable=False,
        existing_server_default=sa.text("false"),
    )


def downgrade():
    op.alter_column(
        "lecturer",
        "is_deleted",
        existing_type=sa.BOOLEAN(),
        comment=None,
        existing_comment="Идентификатор софт делита",
        existing_nullable=False,
        existing_server_default=sa.text("false"),
    )
    op.alter_column(
        "lecturer",
        "avatar_link",
        existing_type=sa.VARCHAR(),
        comment=None,
        existing_comment="Ссылка на аву препода",
        existing_nullable=True,
    )
    op.alter_column(
        "lecturer",
        "middle_name",
        existing_type=sa.VARCHAR(),
        comment=None,
        existing_comment="Отчество препода",
        existing_nullable=False,
    )
    op.alter_column(
        "lecturer",
        "last_name",
        existing_type=sa.VARCHAR(),
        comment=None,
        existing_comment="Фамилия препода",
        existing_nullable=False,
    )
    op.alter_column(
        "lecturer",
        "first_name",
        existing_type=sa.VARCHAR(),
        comment=None,
        existing_comment="Имя препода",
        existing_nullable=False,
    )
    op.alter_column(
        "lecturer",
        "id",
        existing_type=sa.INTEGER(),
        comment=None,
        existing_comment="Идентификатор преподавателя",
        existing_nullable=False,
        autoincrement=True,
        existing_server_default=sa.text("nextval('lecturer_id_seq'::regclass)"),
    )
    op.drop_column("lecturer", "rank_update_ts")
    op.drop_column("lecturer", "rank")
    op.drop_column("lecturer", "mark_freebie_weighted")
    op.drop_column("lecturer", "mark_clarity_weighted")
    op.drop_column("lecturer", "mark_kindness_weighted")
    op.drop_column("lecturer", "mark_weighted")
