import datetime

from rating_api.schemas.base import Base

class Comment(Base):
    id: int
    create_ts: datetime.datetime
    update_ts: datetime.datetime
    subject: str
    text: str
    mark_kindness: int
    mark_freebie: int
    mark_clarity: int
    lecturer_id: int

class LecturerGet(Base):
    id: int
    first_name: str
    last_name: str
    middle_name: str
    avatar_link: str | None = None
    subject: str | None = None
    timetable_id: int
    mark_kindness: float | None = None
    mark_freebie: float | None = None
    mark_clarity: float | None = None
    mark_general: float | None = None
    comments: list[Comment] | None = None

class LecturerGetAll(Base):
    lecturers: list[LecturerGet] = []
    limit: int
    offset: int
    total: int

class LecturerPost(Base):
    first_name: str
    last_name: str
    middle_name: str
    subject: str | None = None
    avatar_link: str | None = None
    timetable_id: int

class LecturerPatch(Base):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    subject: str | None = None
    avatar_link: str | None = None
    timetable_id: int | None = None
