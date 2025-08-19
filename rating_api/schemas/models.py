import datetime
from typing import List
from uuid import UUID

from fastapi import Query
from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import ValidationInfo, field_validator

from rating_api.exceptions import WrongMark
from rating_api.models import Lecturer, ReviewStatus
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


class CommentGetWithStatus(CommentGet):
    review_status: ReviewStatus


class CommentGetWithAllInfo(CommentGetWithStatus):
    approved_by: int | None = None


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


class CommentPost(CommentUpdate):
    create_ts: datetime.datetime | None = None
    update_ts: datetime.datetime | None = None
    is_anonymous: bool = True


class CommentImport(CommentUpdate):
    lecturer_id: int
    create_ts: datetime.datetime | None = None
    update_ts: datetime.datetime | None = None


class CommentImportAll(Base):
    comments: list[CommentImport]


class CommentGetAll(Base):
    comments: list[CommentGet] = []
    limit: int
    offset: int
    total: int


class CommentGetAllWithStatus(Base):
    comments: list[CommentGetWithStatus] = []


class CommentGetAllWithAllInfo(Base):
    comments: list[CommentGetWithAllInfo] = []


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


class LecturerPatch(LecturerPost):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None


class LecturersFilter(Filter):
    subject: str = ''
    name: str = ''
    order_by: List[str] = [
        'mark_weighted',
    ]

    @field_validator("*", mode="before", check_fields=False)
    def validate_order_by(cls, value, field: ValidationInfo):
        return value

    @field_validator('order_by', mode='before')
    def check_order_param(cls, value: str) -> str:
        """Проверяет, что значение поля (без +/-) входит в список возможных."""
        allowed_ordering = {
            "mark_weighted",
            "mark_kindness",
            "mark_freebie",
            "mark_clarity",
            "mark_general",
            "last_name",
        }
        cleaned_value = value.replace("+", "").replace("-", "")
        if cleaned_value in allowed_ordering:
            return value
        else:
            raise ValueError(f'"order_by"-field must contain value from {allowed_ordering}.')

    def filter(self, query: Query) -> Query:
        if self.subject:
            query = query.filter(self.Constants.model.search_by_subject(self.subject))
        if self.name:
            query = query.filter(self.Constants.model.search_by_name(self.name))
        return query

    def sort(self, query: Query) -> Query:
        if not self.ordering_values:
            return query
        elif len(self.ordering_values) > 1:
            raise ValueError('order_by (хотя бы пока что) поддерживает лишь один параметр для сортировки!')

        for field_name in self.ordering_values:
            direction = True
            if field_name.startswith("-"):
                direction = False
            field_name = field_name.replace("-", "").replace("+", "")
            if field_name.startswith('mark_'):
                query = query.order_by(*self.Constants.model.order_by_mark(field_name, direction))
            else:
                query = query.order_by(*self.Constants.model.order_by_name(field_name, direction))
            return query

    class Constants(Filter.Constants):
        model = Lecturer
