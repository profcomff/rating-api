import datetime
from typing import Literal
from uuid import UUID

import aiohttp
from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends, Query
from fastapi_sqlalchemy import db

from rating_api.exceptions import AlreadyExists, ForbiddenAction, ObjectNotFound
from rating_api.models import Comment, CommentLike, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.schemas.base import StatusResponseModel
from rating_api.schemas.models import LikeGet
from rating_api.settings import Settings, get_settings


settings: Settings = get_settings()
like = APIRouter(prefix="/like", tags=["Like"])


@like.post("/{comment_uuid}", response_model=LikeGet)
async def create_like(comment_uuid, user=Depends(UnionAuth())) -> LikeGet:
    """
    Создает лайк на коммент
    """
    comment: Comment = Comment.query(session=db.session).filter(Comment.uuid == comment_uuid).one_or_none()
    if comment is None:
        raise ObjectNotFound(Comment, comment_uuid)

    existing_like: CommentLike = (
        CommentLike.query(session=db.session)
        .filter(
            CommentLike.comment_uuid == comment_uuid,
            CommentLike.user_id == user.get('id'),
            CommentLike.is_deleted == False,
        )
        .one_or_none()
    )
    if existing_like:
        raise AlreadyExists(CommentLike, comment_uuid)

    new_like = CommentLike.create(session=db.session, user_id=user.get('id'), comment_uuid=comment_uuid)
    return LikeGet.model_validate(new_like)


@like.delete("/{comment_uuid}", response_model=StatusResponseModel)
async def delete_like(comment_uuid: UUID, user=Depends(UnionAuth())):
    """
    Удалить свой лайк на коммент
    """
    like = (
        CommentLike.query(session=db.session)
        .filter(
            CommentLike.comment_uuid == comment_uuid,
            CommentLike.user_id == user.get('id'),
            CommentLike.is_deleted == False,
        )
        .one_or_none()
    )
    if not like:
        raise ObjectNotFound(CommentLike, comment_uuid)
    CommentLike.delete(session=db.session, id=like.id)
    return StatusResponseModel(
        status="Success", message="Like has been deleted", ru="Лайк на данный комментарий был удален"
    )
