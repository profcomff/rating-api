from .base import Base, CommentLecturer
from rating_api.models.base import ApproveStatuses


class LecturerCommentPost(Base):
    author_name: str
    text: str
    rate_general: int
    rate_kindness: int
    rate_free: int
    rate_understand: int


class LecturerCommentPatch(Base):
    author_name: str | None
    text: str | None
    rate_general: int
    rate_kindness: int
    rate_free: int
    rate_understand: int


class LecturerComments(Base):
    items: list[CommentLecturer]
    limit: int
    offset: int
    total: int


class Action(Base):
    action: ApproveStatuses
