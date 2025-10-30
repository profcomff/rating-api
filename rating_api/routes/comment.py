import datetime
import re
from typing import Literal, Union
from uuid import UUID

import aiohttp
from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends, Query
from fastapi_sqlalchemy import db
from rating_api.exceptions import (CommentTooLong, ForbiddenAction,
                                   ForbiddenSymbol, ObjectNotFound,
                                   TooManyCommentRequests,
                                   TooManyCommentsToLecturer)
from rating_api.models import (Comment, CommentReaction, Lecturer,
                               LecturerUserComment, Reaction, ReviewStatus)
from rating_api.schemas.base import StatusResponseModel
from rating_api.schemas.models import (CommentGet, CommentGetAll,
                                       CommentGetAllWithAllInfo,
                                       CommentGetAllWithStatus,
                                       CommentGetWithAllInfo,
                                       CommentGetWithStatus, CommentImportAll,
                                       CommentPost, CommentUpdate)
from rating_api.settings import Settings, get_settings

settings: Settings = get_settings()
comment = APIRouter(prefix="/comment", tags=["Comment"])


@comment.post("", response_model=CommentGet)
async def create_comment(
    lecturer_id: int, comment_info: CommentPost, user=Depends(UnionAuth())
) -> CommentGet:
    """
    Создает комментарий к преподавателю в базе данных RatingAPI
    Для создания комментария нужно быть авторизованным
    """
    # Проверяем, что лектор с заданным id существует
    Lecturer.get(session=db.session, id=lecturer_id)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    # Определяем дату, до которой учитываем комментарии для проверки общего лимита.
    cutoff_date_total = datetime.datetime(
        now.year + (now.month - settings.COMMENT_FREQUENCY_IN_MONTH) // 12,
        (now.month - settings.COMMENT_FREQUENCY_IN_MONTH - 1) % 12 + 1,
        1,
    )
    total_user_comments_count = (
        LecturerUserComment.query(session=db.session)
        .filter(
            LecturerUserComment.user_id == user.get("id"),
            LecturerUserComment.update_ts >= cutoff_date_total,
        )
        .count()
    )
    if total_user_comments_count >= settings.COMMENT_LIMIT:
        raise TooManyCommentRequests(
            settings.COMMENT_FREQUENCY_IN_MONTH, settings.COMMENT_LIMIT
        )

    # Дата, до которой учитываем комментарии для проверки лимита на комментарии конкретному лектору.
    cutoff_date_lecturer = datetime.datetime(
        now.year + (now.month - settings.COMMENT_LECTURER_FREQUENCE_IN_MONTH) // 12,
        (now.month - settings.COMMENT_LECTURER_FREQUENCE_IN_MONTH) % 12,
        1,
    )
    lecturer_user_comments_count = (
        LecturerUserComment.query(session=db.session)
        .filter(
            LecturerUserComment.user_id == user.get("id"),
            LecturerUserComment.lecturer_id == lecturer_id,
            LecturerUserComment.update_ts >= cutoff_date_lecturer,
        )
        .count()
    )
    if lecturer_user_comments_count >= settings.COMMENT_TO_LECTURER_LIMIT:
        raise TooManyCommentsToLecturer(
            settings.COMMENT_LECTURER_FREQUENCE_IN_MONTH,
            settings.COMMENT_TO_LECTURER_LIMIT,
        )

    if len(comment_info.text) > settings.MAX_COMMENT_LENGTH:
        raise CommentTooLong(settings.MAX_COMMENT_LENGTH)

    if (
        re.search(
            r"^[a-zA-Zа-яА-Я\d!?,_\-.\"\'\[\]{}`~<>^@#№$%;:&*()+=\\\/ \n]*$",
            comment_info.text,
        )
        is None
    ):
        raise ForbiddenSymbol()

    # Сначала добавляем с user_id, который мы получили при авторизации,
    # в LecturerUserComment, чтобы нельзя было слишком быстро добавлять комментарии
    create_ts = datetime.datetime(now.year, now.month, 1)
    LecturerUserComment.create(
        session=db.session,
        lecturer_id=lecturer_id,
        user_id=user.get("id"),
        create_ts=create_ts,
        update_ts=create_ts,
    )
    # Обрабатываем анонимность комментария, и удаляем этот флаг чтобы добавить запись в БД
    user_id = None if comment_info.is_anonymous else user.get("id")

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
                headers={
                    "Accept": "application/json",
                    "Authorization": settings.ACHIEVEMENT_GIVE_TOKEN,
                },
            )

    return CommentGet.model_validate(new_comment)


@comment.post("/import", response_model=CommentGetAll)
async def import_comments(
    comments_info: CommentImportAll,
    _=Depends(UnionAuth(scopes=["rating.comment.import"])),
) -> CommentGetAll:
    """
    Scopes: `["rating.comment.import"]`
    Создает комментарии в базе данных RatingAPI
    """
    number_of_comments = len(comments_info.comments)
    result = CommentGetAll(
        limit=number_of_comments, offset=number_of_comments, total=number_of_comments
    )
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
    comment: Comment = (
        Comment.query(session=db.session).filter(Comment.uuid == uuid).one_or_none()
    )
    if comment is None:
        raise ObjectNotFound(Comment, uuid)
    return CommentGet.model_validate(comment)


@comment.get(
    "",
    response_model=Union[
        CommentGetAll, CommentGetAllWithAllInfo, CommentGetAllWithStatus
    ],
)
async def get_comments(
    limit: int = 10,
    offset: int = 0,
    lecturer_id: int | None = None,
    user_id: int | None = None,
    subject: str | None = None,
    order_by: str = Query(
        enum=[
            "create_ts",
            "mark_kindness",
            "mark_freebie",
            "mark_clarity",
            "mark_general",
        ],
        default="create_ts",
    ),
    unreviewed: bool = False,
    asc_order: bool = False,
    user=Depends(
        UnionAuth(scopes=["rating.comment.review"], auto_error=False, allow_none=False)
    ),
) -> CommentGetAll:
    """
     Scopes: `["rating.comment.review"]`

     `limit` - максимальное количество возвращаемых комментариев

     `offset` -  смещение, определяющее, с какого по порядку комментария начинать выборку.
     Если без смещения возвращается комментарий с условным номером N,
     то при значении offset = X будет возвращаться комментарий с номером N + X

    `order_by` - возможные значения `"create_ts", "mark_kindness", "mark_freebie", "mark_clarity", "mark_general"`.
     Если передано `'create_ts'` - возвращается список комментариев отсортированных по времени
     Если передано `'mark_...'` - возвращается список комментариев отсортированных по конкретной оценке

     `lecturer_id` - вернет все комментарии для преподавателя с конкретным id, по дефолту возвращает вообще все аппрувнутые комментарии.

     `user_id` - вернет все комментарии пользователя с конкретным id

     `unreviewed` - вернет все непроверенные комментарии, если True. По дефолту False.

     `asc_order` -Если передано true, сортировать в порядке возрастания. Иначе - в порядке убывания
    """
    comments_query = (
        Comment.query(session=db.session)
        .filter(Comment.search_by_lectorer_id(lecturer_id))
        .filter(Comment.search_by_user_id(user_id))
        .filter(Comment.search_by_subject(subject))
        .order_by(
            Comment.order_by_mark(order_by, asc_order)
            if "mark" in order_by
            else Comment.order_by_create_ts(order_by, asc_order)
        )
    )
    comments = comments_query.limit(limit).offset(offset).all()
    if not comments:
        raise ObjectNotFound(Comment, "all")
    if user and "rating.comment.review" in [
        scope["name"] for scope in user.get("session_scopes")
    ]:
        result = CommentGetAllWithAllInfo(
            limit=limit, offset=offset, total=len(comments)
        )
        comment_validator = CommentGetWithAllInfo
    elif user and user.get("id") == user_id:
        result = CommentGetAllWithStatus(
            limit=limit, offset=offset, total=len(comments)
        )
        comment_validator = CommentGetWithStatus
    else:
        result = CommentGetAll(limit=limit, offset=offset, total=len(comments))
        comment_validator = CommentGet

    result.comments = comments

    if unreviewed:
        if not user:
            raise ForbiddenAction(Comment)
        if "rating.comment.review" in [
            scope["name"] for scope in user.get("session_scopes")
        ]:
            result.comments = [
                comment
                for comment in result.comments
                if comment.review_status is ReviewStatus.PENDING
            ]
        else:
            raise ForbiddenAction(Comment)
    else:
        result.comments = [
            comment
            for comment in result.comments
            if comment.review_status is ReviewStatus.APPROVED
        ]

    result.total = len(result.comments)
    result.comments = [
        comment_validator.model_validate(comment) for comment in result.comments
    ]

    return result


@comment.patch("/{uuid}/review", response_model=CommentGetWithAllInfo)
async def review_comment(
    uuid: UUID,
    user=Depends(
        UnionAuth(scopes=["rating.comment.review"], auto_error=True, allow_none=True)
    ),
    review_status: Literal[
        ReviewStatus.APPROVED, ReviewStatus.DISMISSED
    ] = ReviewStatus.DISMISSED,
) -> CommentGetWithAllInfo:
    """
    Scopes: `["rating.comment.review"]`
    Проверка комментария и присваивания ему статуса по его UUID в базе данных RatingAPI

    `review_status` - возможные значения
    `approved` - комментарий одобрен и возвращается при запросе лектора
    `dismissed` - комментарий отклонен, не отображается в запросе лектора
    """
    check_comment: Comment = (
        Comment.query(session=db.session).filter(Comment.uuid == uuid).one_or_none()
    )

    if not check_comment:
        raise ObjectNotFound(Comment, uuid)

    return CommentGetWithAllInfo.model_validate(
        Comment.update(
            session=db.session,
            id=uuid,
            review_status=review_status,
            approved_by=user.get("id"),
        )
    )


@comment.patch("/{uuid}", response_model=CommentGet)
async def update_comment(
    uuid: UUID, comment_update: CommentUpdate, user=Depends(UnionAuth())
) -> CommentGet:
    """Позволяет изменить свой неанонимный комментарий"""
    comment: Comment = Comment.get(
        session=db.session, id=uuid
    )  # Ошибка, если не найден

    if comment.user_id != user.get("id") or comment.user_id is None:
        raise ForbiddenAction(Comment)

    # Получаем только переданные для обновления поля
    update_data = comment_update.model_dump(exclude_unset=True)

    # Обновляем комментарий
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
    has_delete_scope = "rating.comment.delete" in [
        scope["name"] for scope in user.get("session_scopes")
    ]

    # Если нет привилегии - проверяем права обычного пользователя
    if not has_delete_scope and (
        comment.user_id == None or comment.user_id != user.get("id")
    ):
        raise ForbiddenAction(Comment)
    Comment.delete(session=db.session, id=uuid)

    return StatusResponseModel(
        status="Success",
        message="Comment has been deleted",
        ru="Комментарий удален из RatingAPI",
    )


@comment.put("/{uuid}/{reaction}", response_model=CommentGet)
async def like_comment(
    uuid: UUID,
    reaction: Reaction,
    user=Depends(UnionAuth()),
) -> CommentGet:
    """
    Handles like/dislike reactions for a comment.

    This endpoint allows authenticated users to react to a comment (like/dislike) or change their existing reaction.
    If the user has no existing reaction, a new one is created. If the user changes their reaction, it gets updated.
    If the user clicks the same reaction again, the reaction is removed.

    Args:
        uuid (UUID): The UUID of the comment to react to.
        reaction (Reaction): The reaction type (like/dislike).
        user (dict): Authenticated user data from UnionAuth dependency.

    Returns:
        CommentGet: The updated comment with reactions in CommentGet format.

    Raises:
        ObjectNotFound: If the comment with given UUID doesn't exist.
    """
    comment = Comment.get(session=db.session, id=uuid)
    if not comment:
        raise ObjectNotFound(Comment, uuid)

    existing_reaction = (
        CommentReaction.query(session=db.session)
        .filter(
            CommentReaction.user_id == user.get("id"),
            CommentReaction.comment_uuid == comment.uuid,
        )
        .first()
    )

    if existing_reaction and existing_reaction.reaction != reaction:
        new_reaction = CommentReaction.update(
            session=db.session, id=existing_reaction.uuid, reaction=reaction
        )
    elif not existing_reaction:
        CommentReaction.create(
            session=db.session,
            user_id=user.get("id"),
            comment_uuid=comment.uuid,
            reaction=reaction,
        )
    else:
        CommentReaction.delete(session=db.session, id=existing_reaction.uuid)
    return CommentGet.model_validate(comment)
