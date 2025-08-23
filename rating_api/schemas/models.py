import datetime
from uuid import UUID

from pydantic import field_validator

from rating_api.exceptions import WrongMark
from rating_api.models import ReviewStatus
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
    like_count: int
    dislike_count: int


class CommentGetWithStatus(Base):
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
    review_status: ReviewStatus
    like_count: int
    dislike_count: int


class CommentGetWithAllInfo(Base):
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
    review_status: ReviewStatus
    approved_by: int | None = None
    like_count: int
    dislike_count: int


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


class CommentUpdate(Base):
    subject: str = None
    text: str = None
    mark_kindness: int = None
    mark_freebie: int = None
    mark_clarity: int = None

    @field_validator('mark_kindness', 'mark_freebie', 'mark_clarity')
    @classmethod
    def validate_mark(cls, value):
        if value not in [-2, -1, 0, 1, 2]:
            raise WrongMark()
        return value


class CommentImport(Base):
    lecturer_id: int
    subject: str | None = None
    text: str
    create_ts: datetime.datetime | None = None
    update_ts: datetime.datetime | None = None
    mark_kindness: int
    mark_freebie: int
    mark_clarity: int

    @field_validator('mark_kindness', 'mark_freebie', 'mark_clarity')
    @classmethod
    def validate_mark(cls, value):
        if value not in [-2, -1, 0, 1, 2]:
            raise WrongMark()
        return value


class CommentImportAll(Base):
    comments: list[CommentImport]


class CommentGetAll(Base):
    comments: list[CommentGet] = []
    limit: int
    offset: int
    total: int


class CommentGetAllWithStatus(Base):
    comments: list[CommentGetWithStatus] = []
    limit: int
    offset: int
    total: int


class CommentGetAllWithAllInfo(Base):
    comments: list[CommentGetWithAllInfo] = []
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
    mark_weighted: float | None = None
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


class LecturerRankRatingApi(Base):
    id: int | None = None
    mark_weighted: float | None = None
    mark_kindness_weighted: float | None = None
    mark_clarity_weighted: float | None = None
    mark_freebie_weighted: float | None = None
    rank: float | None = None


class LecturerRankDWH(Base):
    uuid: UUID | None = None
    id: int
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    subject: str | None = None
    avatar_link: str | None = None
    timetable_id: int | None = None
    valid_from_dt: datetime.datetime
    valid_to_dt: datetime.datetime
    rank: int
    mark_weighted: float
    mark_kindness_weighted: float
    mark_clarity_weighted: float
    mark_freebie_weighted: float
