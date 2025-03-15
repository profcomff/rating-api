import datetime
from typing import Literal
from uuid import UUID

import aiohttp
from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends, Query
from fastapi_sqlalchemy import db

from rating_api.exceptions import ForbiddenAction, ObjectNotFound, TooManyCommentRequests, TooManyCommentsToLecturer
from rating_api.models import Comment, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.schemas.base import StatusResponseModel
from rating_api.schemas.models import CommentGet, CommentGetAll, CommentImportAll, CommentPost
from rating_api.settings import Settings, get_settings


settings: Settings = get_settings()
comment = APIRouter(prefix="/comment", tags=["Comment"])


@comment.post("", response_model=CommentGet)
async def create_comment(lecturer_id: int, comment_info: CommentPost, user=Depends(UnionAuth())) -> CommentGet:
    """
    Scopes: `["rating.comment.import"]`
    Создает комментарий к преподавателю в базе данных RatingAPI
    Для создания комментария нужно быть авторизованным

    Для возможности создания комментария с указанием времени создания и изменения необходим скоуп ["rating.comment.import"]
    """
    lecturer = Lecturer.get(session=db.session, id=lecturer_id)
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    if not lecturer:
        raise ObjectNotFound(Lecturer, lecturer_id)

    has_create_scope = "rating.comment.import" in [scope['name'] for scope in user.get('session_scopes')]
    if (comment_info.create_ts or comment_info.update_ts) and not has_create_scope:
        raise ForbiddenAction(Comment)

    if not has_create_scope:
        # Определяем дату, до которой учитываем комментарии для проверки общего лимита.
        date_count = datetime.datetime(
            now.year + (now.month - settings.COMMENT_FREQUENCY_IN_MONTH) // 12,
            (now.month - settings.COMMENT_FREQUENCY_IN_MONTH) % 12,
            1,
        )
        user_comments_count = (
            LecturerUserComment.query(session=db.session)
            .filter(
                LecturerUserComment.user_id == user.get("id"),
                LecturerUserComment.update_ts >= date_count,
            )
            .count()
        )
        if user_comments_count >= settings.COMMENT_LIMIT:
            raise TooManyCommentRequests(settings.COMMENT_FREQUENCY_IN_MONTH, settings.COMMENT_LIMIT)

        # Дата, до которой учитываем комментарии для проверки лимита на комментарии конкретному лектору.
        cutoff_date_lecturer = datetime.datetime(
            now.year + (now.month - settings.COMMENT_LECTURER_FREQUENCE_IN_MONTH) // 12,
            (now.month - settings.COMMENT_LECTURER_FREQUENCE_IN_MONTH) % 12,
            1,
        )
        lecturer_comments_count = (
            LecturerUserComment.query(session=db.session)
            .filter(
                LecturerUserComment.user_id == user.get("id"),
                LecturerUserComment.lecturer_id == lecturer_id,
                LecturerUserComment.update_ts >= cutoff_date_lecturer,
            )
            .count()
        )
        if lecturer_comments_count >= settings.COMMENT_TO_LECTURER_LIMIT:
            raise TooManyCommentsToLecturer(
                settings.COMMENT_LECTURER_FREQUENCE_IN_MONTH, settings.COMMENT_TO_LECTURER_LIMIT
            )

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
        session=db.session,
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
            if response.status == 200:
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
            **comment_info.model_dump(exclude={"is_anonymous"}),
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


@comment.get("", response_model=CommentGetAll)
async def get_comments(
    limit: int = 10,
    offset: int = 0,
    lecturer_id: int | None = None,
    user_id: int | None = None,
    order_by: list[Literal["create_ts"]] = Query(default=[]),
    unreviewed: bool = False,
    user=Depends(UnionAuth(scopes=['rating.comment.review'], auto_error=False, allow_none=True)),
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
    result = CommentGetAll(limit=limit, offset=offset, total=len(comments))
    result.comments = comments
    if user_id is not None:
        result.comments = [comment for comment in result.comments if comment.user_id == user_id]

    if lecturer_id is not None:
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

    result.comments = result.comments[offset : limit + offset]

    if "create_ts" in order_by:
        result.comments.sort(key=lambda comment: comment.create_ts, reverse=True)
    result.total = len(result.comments)
    result.comments = [CommentGet.model_validate(comment) for comment in result.comments]
    result.comments.sort(key=lambda comment: comment.create_ts, reverse=True)
    return result


@comment.patch("/{uuid}", response_model=CommentGet)
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


@comment.delete("/{uuid}", response_model=StatusResponseModel)
async def delete_comment(
    uuid: UUID,
    user=Depends(UnionAuth(auto_error=True, allow_none=False)),
):
    """
    Scopes: `["rating.comment.delete"]`

    Удаляет комментарий по его UUID в базе данных RatingAPI
    """
    comment = Comment.get(uuid, session=db.session)
    if comment is None:
        raise ObjectNotFound(Comment, uuid)
    # Наличие скоупа для удаления любых комментариев
    has_delete_scope = "rating.comment.delete" in [scope['name'] for scope in user.get('session_scopes', [])]

    # Если нет привилегии - проверяем права обычного пользователя
    if not has_delete_scope:
        if comment.is_anonymous:
            raise ForbiddenAction(Comment)

    if not has_delete_scope or comment.user_id != user.id:
        raise ForbiddenAction(Comment)
    Comment.delete(session=db.session, id=uuid)

    return StatusResponseModel( 
        status="Success", message="Comment has been deleted", ru="Комментарий удален из RatingAPI"
    )
