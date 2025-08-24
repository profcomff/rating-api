from __future__ import annotations

import datetime
import logging
import uuid
from enum import Enum

from fastapi_sqlalchemy import db
from sqlalchemy import (
    UUID,
    Boolean,
    DateTime,
)
from sqlalchemy import Enum as DbEnum
from sqlalchemy import (
    ForeignKey,
    Integer,
    Float,
    String,
    UnaryExpression,
    and_,
    desc,
    func,
    nulls_last,
    or_,
    true,
)
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from rating_api.utils.mark import calc_weighted_mark

from .base import BaseDbModel


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
    def order_by_mark(
        self, query: str, asc_order: bool
    ) -> tuple[UnaryExpression[float], InstrumentedAttribute, InstrumentedAttribute]:
        if "mark_weighted" in query:
            comments_num = func.count(self.comments).filter(Comment.review_status == ReviewStatus.APPROVED)
            lecturer_mark_general = func.avg(Comment.mark_general).filter(
                Comment.review_status == ReviewStatus.APPROVED
            )
            expression = calc_weighted_mark(lecturer_mark_general, comments_num, Lecturer.mean_mark_general())
        else:
            expression = func.avg(getattr(Comment, query)).filter(Comment.review_status == ReviewStatus.APPROVED)
        if not asc_order:
            expression = expression.desc()
        return nulls_last(expression), Lecturer.last_name, Lecturer.id

    @hybrid_method
    def order_by_name(
        self, query: str, asc_order: bool
    ) -> tuple[UnaryExpression[str] | InstrumentedAttribute, InstrumentedAttribute]:
        return (getattr(Lecturer, query) if asc_order else getattr(Lecturer, query).desc()), Lecturer.id

    @staticmethod
    def mean_mark_general() -> float:
        mark_general_rows = (
            db.session.query(func.avg(Comment.mark_general))
            .filter(Comment.review_status == ReviewStatus.APPROVED)
            .group_by(Comment.lecturer_id)
            .all()
        )
        mean_mark_general = float(
            sum(mark_general_row[0] for mark_general_row in mark_general_rows) / len(mark_general_rows)
            if len(mark_general_rows) != 0
            else 0
        )
        return mean_mark_general


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
    approved_by: Mapped[int] = mapped_column(Integer, nullable=True)
    lecturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lecturer.id"))
    lecturer: Mapped[Lecturer] = relationship(
        "Lecturer",
        back_populates="comments",
        primaryjoin="and_(Comment.lecturer_id == Lecturer.id, not_(Lecturer.is_deleted))",
    )
    review_status: Mapped[ReviewStatus] = mapped_column(DbEnum(ReviewStatus, native_enum=False), nullable=False)
    reactions: Mapped[list[CommentReaction]] = relationship(
        "CommentReaction", back_populates="comment", cascade="all, delete-orphan"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @hybrid_property
    def mark_general(self):
        return (self.mark_kindness + self.mark_freebie + self.mark_clarity) / 3

    @hybrid_method
    def order_by_create_ts(
        self, query: str, asc_order: bool
    ) -> UnaryExpression[datetime.datetime] | InstrumentedAttribute:
        return getattr(Comment, query) if asc_order else desc(getattr(Comment, query))

    @hybrid_method
    def order_by_mark(self, query: str, asc_order: bool) -> UnaryExpression[float] | InstrumentedAttribute:
        return getattr(Comment, query) if asc_order else desc(getattr(Comment, query))

    @hybrid_method
    def search_by_lectorer_id(self, query: int) -> bool:
        if not query:
            return true()
        return and_(Comment.review_status == ReviewStatus.APPROVED, Comment.lecturer_id == query)

    @hybrid_method
    def search_by_user_id(self, query: int) -> bool:
        if not query:
            return true()
        return Comment.user_id == query

    @hybrid_method
    def search_by_subject(self, query: str) -> bool:
        if not query:
            return true()
        return and_(Comment.review_status == ReviewStatus.APPROVED, func.lower(Comment.subject).contains(query))

    @hybrid_property
    def like_count(self) -> int:
        """Python access to like count"""
        return sum(1 for like in self.reactions if like.reaction == 'like')

    @hybrid_property
    def dislike_count(self) -> int:
        """Python access to dislike count"""
        return sum(1 for like in self.reactions if like.reaction == 'dislike')


class LecturerUserComment(BaseDbModel):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lecturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lecturer.id"))
    create_ts: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now(datetime.timezone.utc), nullable=False
    )
    update_ts: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now(datetime.timezone.utc), nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Reaction(str, Enum):
    LIKE: str = "like"
    DISLIKE: str = "dislike"


class CommentReaction(BaseDbModel):
    uuid: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    comment_uuid: Mapped[UUID] = mapped_column(UUID, ForeignKey("comment.uuid"), nullable=False)
    reaction: Mapped[Reaction] = mapped_column(
        DbEnum(Reaction, native_enum=False), nullable=False
    )  # 1 for like, -1 for dislike
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now(datetime.timezone.utc)
    )
    edited_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    comment = relationship("Comment", back_populates="reactions")


class LecturerRating(BaseDbModel):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Идентификатор препода")
    mark_weighted: Mapped[float] = mapped_column(
        Float, nullable=True, comment="Взвешенная оценка преподавателя, посчитана в dwh"
    )
    mark_kindness_weighted: Mapped[float] = mapped_column(
        Float, nullable=True, comment="Взвешенная оценка доброты, посчитана в dwh"
    )
    mark_clarity_weighted: Mapped[float] = mapped_column(
        Float, nullable=True, comment="Взвешенная оценка понятности, посчитана в dwh"
    )
    mark_freebie_weighted: Mapped[float] = mapped_column(
        Float, nullable=True, comment="Взвешенная оценка халявности, посчитана в dwh"
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=True, comment="Место в рейтинге, посчитана в dwh")
    update_ts: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True, comment="Время обновления записи")