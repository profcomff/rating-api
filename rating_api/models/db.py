from __future__ import annotations
from .base import BaseDbModel
import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as DbEnum

from .base import ApproveStatuses


class Lecturer(BaseDbModel):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    _comment: Mapped[list[LecturerComment]] = relationship(
        "LecturerComment",
        back_populates="_lecturer",
        foreign_keys="LecturerComment.lecturer_id",
        primaryjoin="and_(Lecturer.id==LecturerComment.lecturer_id, not_(LecturerComment.is_deleted))",
    )


class LecturerComment(BaseDbModel):
    lecturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("lecturer.id"), nullable=False)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    rate_general: Mapped[int] = mapped_column(Integer)
    rate_kindness: Mapped[int] = mapped_column(Integer)
    rate_free: Mapped[int] = mapped_column(Integer)
    rate_understand: Mapped[int] = mapped_column(Integer)
    create_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    update_ts: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )
    approve_author_id: Mapped[int] = mapped_column(Integer, nullable=True, default=None)
    approve_status: Mapped[ApproveStatuses] = mapped_column(DbEnum(ApproveStatuses, native_enum=False), nullable=False)
    approve_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    _lecturer: Mapped[Lecturer] = relationship(
        "Lecturer",
        back_populates="_comment",
        foreign_keys="LecturerComment.lecturer_id",
        primaryjoin="and_(Lecturer.id==LecturerComment.lecturer_id, not_(Lecturer.is_deleted))",
    )
