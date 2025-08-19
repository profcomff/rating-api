import datetime
from uuid import UUID
from typing import List, Literal, Optional

from fastapi import Query
from pydantic import Field, field_validator, ValidationError, ValidationInfo
from fastapi_filter.contrib.sqlalchemy import Filter
from sqlalchemy import func, or_

from rating_api.exceptions import WrongMark
from rating_api.models import ReviewStatus, Lecturer, Comment
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


class LecturersFilter(Filter):
    subject: str = ''
    name: str = ''
    order_by: List[str] = ['mark_weighted',]

    @field_validator("*", mode="before", check_fields=False)
    def validate_order_by(cls, value, field: ValidationInfo):
        return value

    @field_validator('order_by', mode='before')
    @classmethod
    def check_order_param(cls, value: str) -> str:
        """Проверяет, что значение поля (без +/-) входит в список возможных."""
        allowed_ordering = {"mark_weighted", "mark_kindness", "mark_freebie", "mark_clarity", "mark_general", "last_name"}
        cleaned_value = value.replace("+", "").replace("-", "")
        if cleaned_value in allowed_ordering:
            return value
        else:
            raise ValueError(f'"order_by"-field must contain value from {allowed_ordering}.')

    def filter(self, query: Query) -> Query:
        # query = super().filter(query)  # FIXME: стоит ли оставлять классическое поведение? У нас ведь не предусмотрены такие фильтрации...
        if self.subject:
            query = query.filter(self.Constants.model.search_by_subject(self.subject))
        if self.name:
            query = query.filter(self.Constants.model.search_by_name(self.name))
        return query

        # if self.subject:
        #     subject = self.subject.lower()
        #     query.filter(func.lower(Comment.subject).contains(subject))
        # if self.name:
        #     full_name = self.name.split(' ')
        #     for name in full_name:
        #         name = name.lower()
        #         query.filter(
        #             or_(
        #                 func.lower(self.Constants.model.first_name).contains(name),
        #                 func.lower(self.Constants.model.middle_name).contains(name),
        #                 func.lower(self.Constants.model.last_name).contains(name)
        #             )
        #         )
    
    def sort(self, query: Query) -> Query:  # FIXME: почему-то при добавлении знака к order_by-параметру, все ломается!
        # print(f'{self.ordering_values=}')
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
