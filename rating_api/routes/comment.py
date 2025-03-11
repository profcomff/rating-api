import datetime
import re
from typing import Literal, Union
from uuid import UUID

import aiohttp
from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends, Query
from fastapi_sqlalchemy import db

from rating_api.exceptions import (
    CommentTooLong,
    ForbiddenAction,
    ForbiddenSymbol,
    ObjectNotFound,
    TooManyCommentRequests,
    TooManyCommentsToLecturer,
    UpdateError,
)
from rating_api.models import Comment, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.schemas.base import StatusResponseModel
from rating_api.schemas.models import (
    CommentGet,
    CommentGetAll,
    CommentGetAllWithStatus,
    CommentGetWithStatus,
    CommentImportAll,
    CommentPost,
    CommentUpdate,
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
    now = datetime.datetime.now(tz=datetime.timezone.utc)

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

        if len(comment_info.text) > settings.MAX_COMMENT_LENGTH:
            raise CommentTooLong(settings.MAX_COMMENT_LENGTH)

        if re.search(r"^[a-zA-Zа-яА-Я\d!?,_\-.\"\'\[\]{}`~<>^@#№$%;:&*()+=\\\/ \n]*$", comment_info.text) is None:
            raise ForbiddenSymbol()

    # Сначала добавляем с user_id, который мы получили при авторизации,
    # в LecturerUserComment, чтобы нельзя было слишком быстро добавлять комментарии
    create_ts = datetime.datetime(now.year, now.month, 1)
    LecturerUserComment.create(
        session=db.session,
        lecturer_id=lecturer_id,
        user_id=user.get('id'),
        create_ts=create_ts,
        update_ts=create_ts,
    )
    # Обрабатываем анонимность комментария, и удаляем этот флаг чтобы добавить запись в БД
    user_id = None if comment_info.is_anonymous else user.get('id')

    new_comment = Comment.create(
        **comment_info.model_dump(exclude={"is_anonymous"}),
        lecturer_id=lecturer_id,
        user_id=user_id,
        review_status=ReviewStatus.PENDING,
    )

    # Выдача аччивки юзеру за первый комментарий
    async with aiohttp.ClientSession() as session:
        give_achievement = True
        async with session.get(
            settings.API_URL + f"achievement/user/{user.get('id'):}",
            headers={"Accept": "application/json"},
        ) as response:
            if response.status == 300:
                user_achievements = await response.json()
                for achievement in user_achievements.get("achievement", []):
                    if achievement.get("id") == settings.FIRST_COMMENT_ACHIEVEMENT_ID:
                        give_achievement = False
                        break
            else:
                give_achievement = False
        if give_achievement:
            session.post(
                settings.API_URL
                + f"achievement/achievement/{settings.FIRST_COMMENT_ACHIEVEMENT_ID}/reciever/{user.get('id'):}",
                headers={"Accept": "application/json", "Authorization": settings.ACHIEVEMENT_GIVE_TOKEN},
            )

    return CommentGet.model_validate(new_comment)


@comment.post('/import', response_model=CommentGetAll)
async def import_comments(
    comments_info: CommentImportAll, _=Depends(UnionAuth(scopes=["rating.comment.import"]))
) -> CommentGetAll:
    """
    Scopes: `["rating.comment.import"]`
    Создает комментарии в базе данных RatingAPI
    """
    number_of_comments = len(comments_info.comments)
    result = CommentGetAll(limit=number_of_comments, offset=number_of_comments, total=number_of_comments)
    for comment_info in comments_info.comments:
        new_comment = Comment.create(
            session=db.session,
            **comment_info.model_dump(),
            review_status=ReviewStatus.APPROVED,
        )
        result.comments.append(new_comment)
    return result


@comment.get("/{uuid}", response_model=CommentGet)
async def get_comment(uuid: UUID) -> CommentGet:
    """
    Возвращает комментарий по его UUID в базе данных RatingAPI
    """
    comment: Comment = Comment.query(session=db.session).filter(Comment.uuid == uuid).one_or_none()
    if comment is None:
        raise ObjectNotFound(Comment, uuid)
    return CommentGet.model_validate(comment)


@comment.get("", response_model=Union[CommentGetAll, CommentGetAllWithStatus])
async def get_comments(
    limit: int = 10,
    offset: int = 0,
    lecturer_id: int | None = None,
    user_id: int | None = None,
    order_by: list[Literal["create_ts"]] = Query(default=[]),
    unreviewed: bool = False,
    user=Depends(UnionAuth(scopes=["rating.comment.review"], auto_error=False, allow_none=True)),
) -> CommentGetAll:
    """
    Scopes: `["rating.comment.review"]`

    `limit` - максимальное количество возвращаемых комментариев

    `offset` -  смещение, определяющее, с какого по порядку комментария начинать выборку.
    Если без смещения возвращается комментарий с условным номером N,
    то при значении offset = X будет возвращаться комментарий с номером N + X

    `order_by` - возможное значение `'create_ts'` - возвращается список комментариев отсортированных по времени создания

    `lecturer_id` - вернет все комментарии для преподавателя с конкретным id, по дефолту возвращает вообще все аппрувнутые комментарии.

    `user_id` - вернет все комментарии пользователя с конкретным id

    `unreviewed` - вернет все непроверенные комментарии, если True. По дефолту False.
    """
    comments = Comment.query(session=db.session).all()
    if not comments:
        raise ObjectNotFound(Comment, 'all')
    if "rating.comment.review" in [scope['name'] for scope in user.get('session_scopes')] or user.get('id') == user_id:
        result = CommentGetAllWithStatus(limit=limit, offset=offset, total=len(comments))
        comment_validator = CommentGetWithStatus
    else:
        result = CommentGetAll(limit=limit, offset=offset, total=len(comments))
        comment_validator = CommentGet
    result.comments = comments
    if user_id is not None:
        result.comments = [comment for comment in result.comments if comment.user_id == user_id]

    if lecturer_id is not None:
        result.comments = [comment for comment in result.comments if comment.lecturer_id == lecturer_id]

    if unreviewed:
        if not user:
            raise ForbiddenAction(Comment)
        if "rating.comment.review" in [scope['name'] for scope in user.get('session_scopes')]:
            result.comments = [
                comment
                for comment in result.comments
                if comment.review_status is ReviewStatus.PENDING or ReviewStatus.DISMISSED
            ]
        else:
            raise ForbiddenAction(Comment)
    else:
        result.comments = [comment for comment in result.comments if comment.review_status is ReviewStatus.APPROVED]

    result.comments = result.comments[offset : limit + offset]

    if "create_ts" in order_by:
        result.comments.sort(key=lambda comment: comment.create_ts, reverse=True)
    result.total = len(result.comments)
    result.comments = [comment_validator.model_validate(comment) for comment in result.comments]
    result.comments.sort(key=lambda comment: comment.create_ts, reverse=True)
    return result


@comment.patch("/{uuid}/review", response_model=CommentGet)
async def review_comment(
    uuid: UUID,
    review_status: Literal[ReviewStatus.APPROVED, ReviewStatus.DISMISSED] = ReviewStatus.DISMISSED,
    _=Depends(UnionAuth(scopes=["rating.comment.review"], allow_none=False, auto_error=True)),
) -> CommentGet:
    """
    Scopes: `["rating.comment.review"]`
    Проверка комментария и присваивания ему статуса по его UUID в базе данных RatingAPI

    `review_status` - возможные значения
    `approved` - комментарий одобрен и возвращается при запросе лектора
    `dismissed` - комментарий отклонен, не отображается в запросе лектора
    """

    check_comment: Comment = Comment.query(session=db.session).filter(Comment.uuid == uuid).one_or_none()
    if not check_comment:
        raise ObjectNotFound(Comment, uuid)

    return CommentGet.model_validate(Comment.update(session=db.session, id=uuid, review_status=review_status))


@comment.patch("/{uuid}", response_model=CommentGet)
async def update_comment(uuid: UUID, comment_update: CommentUpdate, user=Depends(UnionAuth())) -> CommentGet:
    """Позволяет изменить свой неанонимный комментарий"""
    comment: Comment = Comment.get(session=db.session, id=uuid)  # Ошибка, если не найден

    if comment.user_id != user.get("id") or comment.user_id is None:
        raise ForbiddenAction(Comment)

    # Получаем только переданные для обновления поля
    update_data = comment_update.model_dump(exclude_unset=True)

    # Если не передано ни одного параметра
    if not update_data:
        raise UpdateError(msg="Provide any parametr.")
        # raise HTTPException(status_code=409, detail="Provide any parametr")  # 409

    # Проверяем, есть ли неизмененные поля
    current_data = {key: getattr(comment, key) for key in update_data}  # Берем текущие значения из БД
    unchanged_fields = {k for k, v in update_data.items() if current_data.get(k) == v}

    if unchanged_fields:
        raise UpdateError(msg=f"No changes detected in fields: {', '.join(unchanged_fields)}.")
        # raise HTTPException(status_code=409, detail=f"No changes detected in fields: {', '.join(unchanged_fields)}")

    # Обновление комментария
    updated_comment = Comment.update(
        session=db.session,
        id=uuid,
        **update_data,
        update_ts=datetime.datetime.utcnow(),
        review_status=ReviewStatus.PENDING,
    )

    return CommentGet.model_validate(updated_comment)


@comment.delete("/{uuid}", response_model=StatusResponseModel)
async def delete_comment(
    uuid: UUID, _=Depends(UnionAuth(scopes=["rating.comment.delete"], allow_none=False, auto_error=True))
):
    """
    Scopes: `["rating.comment.delete"]`

    Удаляет комментарий по его UUID в базе данных RatingAPI
    """
    check_comment = Comment.get(session=db.session, id=uuid)
    if check_comment is None:
        raise ObjectNotFound(Comment, uuid)
    Comment.delete(session=db.session, id=uuid)

    return StatusResponseModel(
        status="Success", message="Comment has been deleted", ru="Комментарий удален из RatingAPI"
    )
