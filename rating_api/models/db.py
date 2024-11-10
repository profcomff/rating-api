from __future__ import annotations

import datetime
import logging
import uuid
from enum import Enum

from sqlalchemy import UUID, DateTime
from sqlalchemy import Enum as DbEnum
from sqlalchemy import ForeignKey, Integer, String, and_, func, or_, true
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    timetable_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="lecturer")

    @hybrid_method
    def search_by_name(self, query: str) -> bool:
        response = true
        query = query.split(' ')
        for q in query:
            response = and_(
                response, or_(self.first_name.contains(q), self.middle_name.contains(q), self.last_name.contains(q))
            )
        return response

    @hybrid_method
    def search_by_subject(self, query: str) -> bool:
        query = query.lower()
        response = true
        if query != "":
            response = and_(Comment.review_status == ReviewStatus.APPROVED, func.lower(Comment.subject) == query)
        return response


class Comment(BaseDbModel):
    uuid: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True)
    create_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    update_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=True)
    mark_kindness: Mapped[int] = mapped_column(Integer, nullable=False)
    mark_freebie: Mapped[int] = mapped_column(Integer, nullable=False)
    mark_clarity: Mapped[int] = mapped_column(Integer, nullable=False)
    lecturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lecturer.id"))
    lecturer: Mapped[Lecturer] = relationship("Lecturer", back_populates="comments")
    review_status: Mapped[ReviewStatus] = mapped_column(DbEnum(ReviewStatus, native_enum=False), nullable=False)


class LecturerUserComment(BaseDbModel):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lecturer.id"))
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    create_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    update_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
