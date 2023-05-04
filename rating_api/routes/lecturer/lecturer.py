import datetime

from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends
from fastapi_sqlalchemy import db

from rating_api.exceptions import ForbiddenAction, ObjectNotFound
from rating_api.models.db import ApproveStatuses
from rating_api.models.db import LecturerComment as DbCommentLecturer
from rating_api.routes.models import CommentLecturer, LecturerCommentPatch, LecturerCommentPost, LecturerComments, StatusResponseModel
from rating_api.settings import get_settings


lecturer_router = APIRouter(
    prefix="/rating/lecturer", tags=["Lecturer"]
)


@lecturer_router.get("/lecturer/rating/{id}", response_model=CommentLecturer)
async def get_comment(id: int, rate: int) -> CommentLecturer:
    comment = DbCommentLecturer.get(id, session=db.session)
    if not comment.lecturer_id == lecturer_id:
        raise ObjectNotFound(DbCommentLecturer, id)
    if comment.approve_status is not ApproveStatuses.APPROVED:
        raise ForbiddenAction(DbCommentLecturer, id)
    return CommentLecturer.from_orm(comment)