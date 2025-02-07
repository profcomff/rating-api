from __future__ import annotations

import datetime
import logging
import uuid
from enum import Enum

from sqlalchemy import UUID, Boolean, DateTime
from sqlalchemy import Enum as DbEnum
from sqlalchemy import ForeignKey, Integer, String, UnaryExpression, and_, func, nulls_last, or_, true
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from rating_api.settings import get_settings

from .base import BaseDbModel


settings = get_settings()
logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    APPROVED: str = "approved"
    PENDING: str = "pending"
    DISMISSED: str = "dismissed"


class Lecturer(BaseDbModel):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    middle_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_link: Mapped[str] = mapped_column(String, nullable=True)
    timetable_id: Mapped[int]
    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="lecturer")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @hybrid_method
    def search_by_name(self, query: str) -> bool:
        response = true
        query = query.split(' ')
        for q in query:
            q = q.lower()
            response = and_(
                response,
                or_(
                    func.lower(self.first_name).contains(q),
                    func.lower(self.middle_name).contains(q),
                    func.lower(self.last_name).contains(q),
                ),
            )
        return response

    @hybrid_method
    def search_by_subject(self, query: str) -> bool:
        query = query.lower()
        response = true
        if query:
            response = and_(Comment.review_status == ReviewStatus.APPROVED, func.lower(Comment.subject).contains(query))
        return response

    @hybrid_method
    def order_by_mark(self, query: str, asc_order: bool) -> UnaryExpression[float]:
        return (
            nulls_last(func.avg(getattr(Comment, query)))
            if asc_order
            else nulls_last(func.avg(getattr(Comment, query)).desc())
        )

    @hybrid_method
    def order_by_name(self, query: str, asc_order: bool) -> UnaryExpression[str] | InstrumentedAttribute[str]:
        return getattr(Lecturer, query) if asc_order else getattr(Lecturer, query).desc()


class Comment(BaseDbModel):
    uuid: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True)
    create_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    update_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(String, nullable=True)
    mark_kindness: Mapped[int] = mapped_column(Integer, nullable=False)
    mark_freebie: Mapped[int] = mapped_column(Integer, nullable=False)
    mark_clarity: Mapped[int] = mapped_column(Integer, nullable=False)
    lecturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lecturer.id"))
    lecturer: Mapped[Lecturer] = relationship(
        "Lecturer",
        back_populates="comments",
        primaryjoin="and_(Comment.lecturer_id == Lecturer.id, not_(Lecturer.is_deleted))",
    )
    review_status: Mapped[ReviewStatus] = mapped_column(DbEnum(ReviewStatus, native_enum=False), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @hybrid_property
    def mark_general(self):
        return (self.mark_kindness + self.mark_freebie + self.mark_clarity) / 3


class LecturerUserComment(BaseDbModel):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lecturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lecturer.id"))
    create_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    update_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
