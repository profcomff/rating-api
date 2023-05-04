import datetime
from typing import Literal

from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends
from fastapi_sqlalchemy import db
from pydantic import parse_obj_as

from rating_api.exceptions import ObjectNotFound
from rating_api.models.db import ApproveStatuses
from rating_api.models.db import LecturerComment as DbCommentLecturer
from rating_api.routes.models import CommentLecturer


lecturer_comment_review_router = APIRouter(
    prefix="/rating/lecturer/{lecturer_id}/comment", tags=["Lecturer: Comment Review"]
)
router = APIRouter(prefix="/lecturer/{lecturer_id}/comment", tags=["Lecturer: Comment Review"])


@lecturer_comment_review_router.get("/review/", response_model=list[CommentLecturer])
async def get_unreviewed_comments(
    lecturer_id: int, user=Depends(UnionAuth(scopes=["rating.lecturer.comment.review"]))
) -> list[CommentLecturer]:
    comments = (
        DbCommentLecturer.get_all(session=db.session, only_approved=False)
        .filter(
            DbCommentLecturer.lecturer_id == lecturer_id, DbCommentLecturer.approve_status == ApproveStatuses.PENDING
        )
        .all()
    )
    return parse_obj_as(list[CommentLecturer], comments)


@lecturer_comment_review_router.post("/{id}/review/", response_model=CommentLecturer)
async def review_comment(
    id: int,
    lecturer_id: int,
    action: Literal[ApproveStatuses.APPROVED, ApproveStatuses.DECLINED] = ApproveStatuses.DECLINED,
    user=Depends(UnionAuth(scopes=["rating.lecturer.comment.review"])),
) -> CommentLecturer:
    comment = DbCommentLecturer.get(id, only_approved=False, session=db.session)
    if comment.lecturer_id != lecturer_id or comment.approve_status is not ApproveStatuses.PENDING:
        raise ObjectNotFound(DbCommentLecturer, id)
    DbCommentLecturer.update(
        comment.id,
        approve_status=action,
        approve_author_id=user['id'],
        approve_time=datetime.datetime.utcnow(),
        session=db.session,
    )
    if action == ApproveStatuses.DECLINED:
        DbCommentLecturer.delete(comment.id, session=db.session)
    db.session.commit()
    return CommentLecturer.from_orm(comment)
