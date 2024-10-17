import datetime
from typing import Annotated, Literal

# from auth_backend.base import StatusResponseModel
# from auth_backend.models.db import Scope, UserSession
# from auth_backend.schemas.models import ScopeGet, ScopePatch, ScopePost
from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_sqlalchemy import db
from sqlalchemy import and_, func

from models import Comment, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.exceptions import AlreadyExists, ForbiddenAction, ObjectNotFound, TooManyCommentRequests
from rating_api.schemas.base import StatusResponseModel
from rating_api.schemas.models import (
    CommentGet,
    CommentGetAll,
    CommentPost,
    LecturerGet,
    LecturerGetAll,
    LecturerPatch,
    LecturerPost,
    LecturerUserCommentPost,
)
from rating_api.settings import Settings, get_settings


settings: Settings = get_settings()
comment = APIRouter(prefix="/comment", tags=["Comment"])


@comment.post("", response_model=CommentGet)
async def create_comment(lecturer_id: int, comment_info: CommentPost, user=Depends(UnionAuth())) -> CommentGet:
    """
    Создает комментарий к преподавателю в базе данных RatingAPI
    Для создания комментария нужно быть авторизованным
    """
    lecturer = Lecturer.get(session=db.session, id=lecturer_id)
    if not lecturer:
        raise ObjectNotFound(Lecturer, lecturer_id)

    user_comments: list[LecturerUserComment] = (
        LecturerUserComment.query(session=db.session).filter(LecturerUserComment.user_id == user.get("id")).all()
    )
    for user_comment in user_comments:
        if datetime.datetime.utcnow() - user_comment.update_ts < datetime.timedelta(
            minutes=settings.COMMENT_CREATE_FREQUENCY_IN_MINUTES
        ):
            raise TooManyCommentRequests(
                dtime=user_comment.update_ts
                + datetime.timedelta(minutes=settings.COMMENT_CREATE_FREQUENCY_IN_MINUTES)
                - datetime.datetime.utcnow()
            )

    LecturerUserComment.create(
        session=db.session,
        **LecturerUserCommentPost(
            **comment_info.dict(exclude_unset=True), lecturer_id=lecturer_id, user_id=user.get('id')
        ).dict(),
    )
    new_comment = Comment.create(
        session=db.session, **comment_info.dict(), lecturer_id=lecturer_id, review_status=ReviewStatus.PENDING
    )
    return CommentGet.model_validate(new_comment)


@comment.get("/{id}", response_model=CommentGet)
async def get_comment(id: int) -> CommentGet:
    """
    Возвращает комментарий по его ID в базе данных RatingAPI
    """
    comment: Comment = Comment.query(session=db.session).filter(Comment.id == id).one_or_none()
    if comment is None:
        raise ObjectNotFound(Comment, id)
    return CommentGet.model_validate(comment)


@comment.get("", response_model=CommentGetAll)
async def get_comments(
    limit: int = 10,
    offset: int = 0,
    lecturer_id: int | None = None,
    order_by: list[Literal["create_ts"]] = Query(default=[]),
    unreviewed: bool = False,
    user=Depends(UnionAuth(scopes=['rating.comment.review'], auto_error=False, allow_none=True)),
) -> CommentGetAll:
    """
    Scopes: `["rating.comment.review"]`

    `limit` - максимальное количество возвращаемых комментариев

    `offset` - нижняя граница получения комментариев, т.е. если по дефолту первым возвращается комментарий с условным номером N, то при наличии ненулевого offset будет возвращаться комментарий с номером N + offset

    `order_by` - возможное значение `'create_ts'` - возвращается список комментариев отсортированных по времени создания

    `lecturer_id` - вернет все комментарии для преподавателя с конкретным id, по дефолту возвращает вообще все аппрувнутые комментарии.

    `unreviewed` - вернет все непроверенные комментарии, если True. По дефолту False.
    """
    comments = Comment.query(session=db.session).all()
    if not comments:
        raise ObjectNotFound(Comment, 'all')
    result = CommentGetAll(limit=limit, offset=offset, total=len(comments))
    for comment in comments[offset : limit + offset]:
        result.comments.append(comment)
    if lecturer_id:
        result.comments = [comment for comment in result.comments if comment.lecturer_id == lecturer_id]
    if unreviewed:
        if not user:
            raise ForbiddenAction(Comment)
        if "rating.comment.review" in [scope['name'] for scope in user.get('session_scopes')]:
            result.comments = [comment for comment in result.comments if comment.review_status is ReviewStatus.PENDING]
        else:
            raise ForbiddenAction(Comment)
    else:
        result.comments = [comment for comment in result.comments if comment.review_status is ReviewStatus.APPROVED]
    if "create_ts" in order_by:
        result.comments.sort(key=lambda comment: comment.create_ts)
    result.total = len(result.comments)
    result.comments = [CommentGet.model_validate(comment) for comment in result.comments]
    return result


@comment.patch("/{id}", response_model=CommentGet)
async def review_comment(
    id: int,
    review_status: Literal[ReviewStatus.APPROVED, ReviewStatus.DISMISSED] = ReviewStatus.DISMISSED,
    _=Depends(UnionAuth(scopes=["rating.comment.review"], allow_none=False, auto_error=True)),
) -> CommentGet:
    """
    Scopes: `["rating.comment.review"]`
    Проверка комментария и присваивания ему статуса по его ID в базе данных RatingAPI

    `review_status` - возможные значения
    `approved` - комментарий одобрен и возвращается при запросе лектора
    `dismissed` - комментарий отклонен, не отображается в запросе лектора
    """
    check_comment: Comment = Comment.query(session=db.session).filter(Comment.id == id).one_or_none()
    if not check_comment:
        raise ObjectNotFound(Comment, id)
    return CommentGet.model_validate(Comment.update(session=db.session, id=id, review_status=review_status))


@comment.delete("/{id}", response_model=StatusResponseModel)
async def delete_comment(
    id: int,
    # _=Depends(UnionAuth(scopes=["rating.comment.delete"], allow_none=False, auto_error=True))
):
    """
    Scopes: `["rating.comment.delete"]`

    Удаляет комментарий по его ID в базе данных RatingAPI
    """
    check_comment = Comment.get(session=db.session, id=id)
    if check_comment is None:
        raise ObjectNotFound(Comment, id)
    Comment.delete(session=db.session, id=id)

    return StatusResponseModel(
        status="Success", message="Comment has been deleted", ru="Комментарий удален из RatingAPI"
    )