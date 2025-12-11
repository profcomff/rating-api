from __future__ import annotations

import datetime
import logging
import uuid
from enum import Enum

from sqlalchemy import (
    UUID,
    Boolean,
    DateTime,
)
from sqlalchemy import Enum as DbEnum
from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    UnaryExpression,
    and_,
    case,
    desc,
    func,
    nulls_last,
    or_,
    select,
    true,
)
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from .base import BaseDbModel


logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    APPROVED: str = "approved"
    PENDING: str = "pending"
    DISMISSED: str = "dismissed"


class Lecturer(BaseDbModel):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Идентификатор преподавателя")
    first_name: Mapped[str] = mapped_column(String, nullable=False, comment="Имя препода")
    last_name: Mapped[str] = mapped_column(String, nullable=False, comment="Фамилия препода")
    middle_name: Mapped[str] = mapped_column(String, nullable=False, comment="Отчество препода")
    avatar_link: Mapped[str] = mapped_column(String, nullable=True, comment="Ссылка на аву препода")
    timetable_id: Mapped[int]
    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="lecturer")
    mark_weighted: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default='0.0',
        default=0,
        comment="Взвешенная оценка преподавателя, посчитана в dwh",
    )
    mark_kindness_weighted: Mapped[float] = mapped_column(
        Float, nullable=False, server_default='0.0', default=0, comment="Взвешенная оценка доброты, посчитана в dwh"
    )
    mark_clarity_weighted: Mapped[float] = mapped_column(
        Float, nullable=False, server_default='0.0', default=0, comment="Взвешенная оценка понятности, посчитана в dwh"
    )
    mark_freebie_weighted: Mapped[float] = mapped_column(
        Float, nullable=False, server_default='0.0', default=0, comment="Взвешенная оценка халявности, посчитана в dwh"
    )
    rank: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default='0', default=0, comment="Место в рейтинге, посчитана в dwh"
    )
    rank_update_ts: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=datetime.datetime.now(),
        comment="Время обновления записи",
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Идентификатор софт делита"
    )

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
            expression = self.mark_weighted
        elif "mark_clarity_weighted" in query:
            expression = self.mark_clarity_weighted
        elif "mark_freebie_weighted" in query:
            expression = self.mark_freebie_weighted
        elif "mark_kindness_weighted" in query:
            expression = self.mark_kindness_weighted
        elif "rank" in query:
            expression = self.rank
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
    def like_count(self):
        """Python доступ к числу лайков"""
        return sum(1 for reaction in self.reactions if reaction.reaction == Reaction.LIKE)

    @like_count.expression
    def like_count(cls):
        """SQL выражение для подсчета лайков"""
        return (
            select(func.count(CommentReaction.uuid))
            .where(and_(CommentReaction.comment_uuid == cls.uuid, CommentReaction.reaction == Reaction.LIKE))
            .label('like_count')
        )

    @hybrid_property
    def dislike_count(self):
        """Python доступ к числу дизлайков"""
        return sum(1 for reaction in self.reactions if reaction.reaction == Reaction.DISLIKE)

    @dislike_count.expression
    def dislike_count(cls):
        """SQL выражение для подсчета дизлайков"""
        return (
            select(func.count(CommentReaction.uuid))
            .where(and_(CommentReaction.comment_uuid == cls.uuid, CommentReaction.reaction == Reaction.DISLIKE))
            .label('dislike_count')
        )

    @hybrid_property
    def like_dislike_diff(self):
        """Python доступ к разнице лайков и дизлайков"""
        if hasattr(self, '_like_dislike_diff'):
            return self._like_dislike_diff
        return self.like_count - self.dislike_count

    @like_dislike_diff.expression
    def like_dislike_diff(cls):
        """SQL выражение для вычисления разницы лайков/дизлайков"""
        return (
            select(
                func.sum(
                    case(
                        (CommentReaction.reaction == Reaction.LIKE, 1),
                        (CommentReaction.reaction == Reaction.DISLIKE, -1),
                        else_=0,
                    )
                )
            )
            .where(CommentReaction.comment_uuid == cls.uuid)
            .label('like_dislike_diff')
        )

    @hybrid_method
    def order_by_like_diff(cls, asc_order: bool = False):
        """Метод для сортировки по разнице лайков/дизлайков"""
        if asc_order:
            return cls.like_dislike_diff.asc()
        else:
            return cls.like_dislike_diff.desc()

    @hybrid_method
    def has_reaction(self, user_id: int, react: Reaction) -> bool:
        return any(reaction.user_id == user_id and reaction.reaction == react for reaction in self.reactions)

    @has_reaction.expression
    def has_reaction(cls, user_id: int, react: Reaction):
        return (
            select([true()])
            .where(
                and_(
                    CommentReaction.comment_uuid == cls.uuid,
                    CommentReaction.user_id == user_id,
                    CommentReaction.reaction == react,
                )
            )
            .exists()
        )

    @classmethod
    def reactions_for_comments(cls, user_id: int, session, comments):
        if not user_id or not comments:
            return {}
        comments_uuid = [c.uuid for c in comments]
        reactions = (
            session.query(CommentReaction)
            .filter(CommentReaction.user_id == user_id, CommentReaction.comment_uuid.in_(comments_uuid))
            .all()
        )
        return {r.comment_uuid: r.reaction for r in reactions}


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
