import datetime
from typing import Literal
from uuid import UUID

import aiohttp
from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends, Query
from fastapi_sqlalchemy import db

from rating_api.exceptions import ForbiddenAction, ObjectNotFound, AlreadyExists
from rating_api.models import Comment, Lecturer, LecturerUserComment, ReviewStatus, Like
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
        raise ObjectNotFound(Comment, uuid)

    existing_like: Like = (
        Like.query(session=db.session)
        .filter(Like.comment_uuid == comment_uuid, Like.user_id == user.get('id'), Like.is_deleted == False)
        .one_or_none
    )
    if existing_like:
        raise AlreadyExists(existing_like, comment_uuid)

    new_like = Like.create(session=db.session, user_id=user.get('id'), comment_uuid=like_info.comment_uuid)
    return LikeGet.model_validate(new_like)


@like.delete("/{comment_uuid}", response_model=StatusResponseModel)
async def delete_like(comment_uuid: UUID, user=Depends(UnionAuth())):
    """
    Удалить свой лайк на коммент
    """
    like = (
        Like.query(session=db.session)
        .filter(Like.comment_uuid == comment_uuid, Like.user_id == user.get('id'), Like.is_deleted == False)
        .one_or_none()
    )
    if not like:
        raise ObjectNotFound(Like, comment_uuid)
    Like.delete(session=db.session, id=like.id)
    return StatusResponseModel(
        status="Success", message="Like has been deleted", ru="Лайк на данный комментарий был удален"
    )
