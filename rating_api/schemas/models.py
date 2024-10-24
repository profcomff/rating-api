import datetime
from uuid import UUID

from rating_api.schemas.base import Base


class CommentGet(Base):
    uuid: UUID
    create_ts: datetime.datetime
    update_ts: datetime.datetime
    subject: str
    text: str
    mark_kindness: int
    mark_freebie: int
    mark_clarity: int
    lecturer_id: int


class CommentPost(Base):
    subject: str
    text: str
    mark_kindness: int
    mark_freebie: int
    mark_clarity: int


class CommentGetAll(Base):
    comments: list[CommentGet] = []
    limit: int
    offset: int
    total: int


class LecturerUserCommentPost(Base):
    lecturer_id: int
    user_id: int


class LecturerGet(Base):
    id: int
    first_name: str
    last_name: str
    middle_name: str
    avatar_link: str | None = None
    subjects: list[str] | None = None
    timetable_id: int
    mark_kindness: float | None = None
    mark_freebie: float | None = None
    mark_clarity: float | None = None
    mark_general: float | None = None
    comments: list[CommentGet] | None = None


class LecturerGetAll(Base):
    lecturers: list[LecturerGet] = []
    limit: int
    offset: int
    total: int


class LecturerPost(Base):
    first_name: str
    last_name: str
    middle_name: str
    avatar_link: str | None = None
    timetable_id: int


class LecturerPatch(Base):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    avatar_link: str | None = None
    timetable_id: int | None = None
