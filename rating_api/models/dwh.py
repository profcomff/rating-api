from datetime import date, datetime
from uuid import UUID

from models import DWHBaseDbModel
from sqlalchemy.orm import Mapped, mapped_column


class DWHLecturer(DWHBaseDbModel):
    __tablename__ = 'lecturer'
    __tableargs__ = {'schema': "DWH_RATING"}

    uuid: Mapped[UUID] = mapped_column(primary_key=True, comment="Техническое поле в dwh")
    api_id: Mapped[int] = mapped_column(comment="Идентифиактор в rating-api")
    first_name: Mapped[str] = mapped_column(comment="Имя преподавателя")
    last_name: Mapped[str] = mapped_column(comment="Фамилия преподавателя")
    middle_name: Mapped[str] = mapped_column(comment="отчество преподавателя")
    subject: Mapped[str | None] = mapped_column(comment="Список предметов преподавателя")
    avatar_link: Mapped[str | None] = mapped_column(comment="Ссылка на аватар преподавателя")
    timetable_id: Mapped[int] = mapped_column(comment="Идертификатор в timetable-api")
    rank: Mapped[int] = mapped_column(comment="Место в рейтинге", default=0, server_default="0")
    mark_weighted: Mapped[float] = mapped_column(
        nullable=False, comment="Взвешенная оценка преподавателя", default=0, server_default="0"
    )
    mark_kindness_weighted: Mapped[float] = mapped_column(
        nullable=False, comment="Взвешенная доброта преподавателя", default=0, server_default="0"
    )
    mark_clarity_weighted: Mapped[float] = mapped_column(
        nullable=False, comment="Взверешенная понятность преподавателя", default=0, server_default="0"
    )
    mark_freebie_weighted: Mapped[float] = mapped_column(
        nullable=False, comment="Взвешенная халявность преподавателя", default=0, server_default="0"
    )
    valid_from_dt: Mapped[date | None] = mapped_column(comment="Дата начала действия записи")
    valid_to_dt: Mapped[date | None] = mapped_column(comment="Дата конца действия записи")
