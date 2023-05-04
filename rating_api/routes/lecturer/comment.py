import datetime

from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends
from fastapi_sqlalchemy import db

from rating_api.exceptions import ForbiddenAction, ObjectNotFound
from rating_api.models.db import ApproveStatuses
from rating_api.models.db import LecturerComment as DbCommentLecturer
from rating_api.routes.models import CommentLecturer, LecturerCommentPatch, LecturerCommentPost, LecturerComments, StatusResponseModel
from rating_api.settings import get_settings
from rating_api.utils import check_rating, get_general_rating
settings = get_settings()
lecturer_comment_router = APIRouter(prefix="/rating/lecturer/{lecturer_id}", tags=["Lecturer: Comment"])
router = APIRouter(prefix="/lecturer/{lecturer_id}", tags=["Lecturer: Comment"])


@lecturer_comment_router.post("/comment/", response_model=CommentLecturer)
async def comment_lecturer(lecturer_id: int, comment: LecturerCommentPost) -> CommentLecturer:
    approve_status = (
        ApproveStatuses.APPROVED if not settings.REQUIRE_REVIEW_LECTURER_COMMENT else ApproveStatuses.PENDING
    )
    if check_rating(comment):
        raise ForbiddenAction(DbCommentLecturer, lecturer_id)
    db_comment_lecturer = DbCommentLecturer.create(
        lecturer_id=lecturer_id,
        session=db.session,
        **comment.dict(),
        approve_status=approve_status,
    )
    db.session.commit()
    return CommentLecturer.from_orm(db_comment_lecturer)


@lecturer_comment_router.patch("/comment/{id}", response_model=CommentLecturer)
async def update_comment_lecturer(id: int, lecturer_id: int, comment_inp: LecturerCommentPatch) -> CommentLecturer:
    comment = DbCommentLecturer.get(id=id, only_approved=False, session=db.session)
    if comment.lecturer_id != lecturer_id:
        raise ObjectNotFound(DbCommentLecturer, id)
    if comment.approve_status is ApproveStatuses.DECLINED or check_rating(comment_inp):
        raise ForbiddenAction(DbCommentLecturer, id)
    patched = DbCommentLecturer.update(id, approve_status=ApproveStatuses.PENDING, update_ts=datetime.datetime.utcnow(), session=db.session, **comment_inp.dict(exclude_unset=True))
    db.session.commit()
    return CommentLecturer.from_orm(patched)


@lecturer_comment_router.delete("/comment/{id}", response_model=StatusResponseModel)
async def delete_comment(
    id: int, lecturer_id: int, _=Depends(UnionAuth(scopes=["rating.lecturer.comment.delete"]))
) -> StatusResponseModel:
    comment = DbCommentLecturer.get(id, only_approved=False, session=db.session)
    if comment.lecturer_id != lecturer_id:
        raise ObjectNotFound(DbCommentLecturer, id)
    DbCommentLecturer.delete(id=id, session=db.session)
    db.session.commit()
    return StatusResponseModel(**{"status": 'Success', "message": ''})


@lecturer_comment_router.get("/comment/{id}", response_model=CommentLecturer)
async def get_comment(id: int, lecturer_id: int) -> CommentLecturer:
    comment = DbCommentLecturer.get(id, session=db.session)
    if not comment.lecturer_id == lecturer_id:
        raise ObjectNotFound(DbCommentLecturer, id)
    if comment.approve_status is not ApproveStatuses.APPROVED:
        raise ForbiddenAction(DbCommentLecturer, id)
    return CommentLecturer.from_orm(comment)


@lecturer_comment_router.get("/comment/", response_model=LecturerComments)
async def get_all_lecturer_comments(lecturer_id: int, limit: int = 10, offset: int = 0) -> LecturerComments:
    res = DbCommentLecturer.get_all(session=db.session).filter(DbCommentLecturer.lecturer_id == lecturer_id)
    if limit:
        cnt, res = res.count(), res.offset(offset).limit(limit).all()
    else:
        cnt, res = res.count(), res.offset(offset).all()
    return LecturerComments(**{"items": res, "limit": limit, "offset": offset, "total": cnt})
