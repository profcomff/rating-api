import datetime
from uuid import UUID

from pydantic import field_validator

from rating_api.exceptions import WrongMark
from rating_api.schemas.base import Base


class CommentGet(Base):
    uuid: UUID
    user_id: int | None = None
    create_ts: datetime.datetime
    update_ts: datetime.datetime
    subject: str | None = None
    text: str
    mark_kindness: int
    mark_freebie: int
    mark_clarity: int
    mark_general: float
    lecturer_id: int
    like_count: int | None = None


class CommentPost(Base):
    subject: str
    text: str
    create_ts: datetime.datetime | None = None
    update_ts: datetime.datetime | None = None
    mark_kindness: int
    mark_freebie: int
    mark_clarity: int
    is_anonymous: bool = True

    @field_validator('mark_kindness', 'mark_freebie', 'mark_clarity')
    @classmethod
    def validate_mark(cls, value):
        if value not in [-2, -1, 0, 1, 2]:
            raise WrongMark()
        return value


class CommentImport(CommentPost):
    lecturer_id: int
    subject: str | None = None


class CommentImportAll(Base):
    comments: list[CommentImport]


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
    timetable_id: int | None = None


class LecturerPatch(Base):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    avatar_link: str | None = None
    timetable_id: int | None = None


class LikeGet(Base):
    id: int
    user_id: int
    comment_uuid: int
    create_ts: datetime.datetime
