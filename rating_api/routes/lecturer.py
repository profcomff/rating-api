from typing import Literal

from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends, Query
from fastapi_sqlalchemy import db
from sqlalchemy import and_
from fastapi_filter import FilterDepends

from rating_api.exceptions import AlreadyExists, ObjectNotFound
from rating_api.models import Comment, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.schemas.base import StatusResponseModel
from rating_api.schemas.models import CommentGet, LecturerGet, LecturerGetAll, LecturerPatch, LecturerPost, LecturersFilter
from rating_api.utils.mark import calc_weighted_mark


lecturer = APIRouter(prefix="/lecturer", tags=["Lecturer"])


@lecturer.post("", response_model=LecturerGet)
async def create_lecturer(
    lecturer_info: LecturerPost,
    _=Depends(UnionAuth(scopes=["rating.lecturer.create"], allow_none=False, auto_error=True)),
) -> LecturerGet:
    """
    Scopes: `["rating.lecturer.create"]`

    Создает преподавателя в базе данных RatingAPI
    """
    get_lecturer: Lecturer = (
        Lecturer.query(session=db.session).filter(Lecturer.timetable_id == lecturer_info.timetable_id).one_or_none()
    )
    if get_lecturer is None:
        new_lecturer: Lecturer = Lecturer.create(session=db.session, **lecturer_info.model_dump())
        db.session.commit()
        return LecturerGet.model_validate(new_lecturer)
    raise AlreadyExists(Lecturer, lecturer_info.timetable_id)


@lecturer.get("/{id}", response_model=LecturerGet)
async def get_lecturer(id: int, info: list[Literal["comments", "mark"]] = Query(default=[])) -> LecturerGet:
    """
    Scopes: `["rating.lecturer.read"]`

    Возвращает преподавателя по его ID в базе данных RatingAPI

    *QUERY* `info: string` - возможные значения `'comments'`, `'mark'`.
    Если передано `'comments'`, то возвращаются одобренные комментарии к преподавателю.
    Если передано `'mark'`, то возвращаются общие средние оценки, а также суммарная средняя оценка по всем одобренным комментариям.

    Subject лектора возвращшается либо из базы данных, либо из любого аппрувнутого комментария
    """
    lecturer: Lecturer = Lecturer.query(session=db.session).filter(Lecturer.id == id).one_or_none()
    if lecturer is None:
        raise ObjectNotFound(Lecturer, id)
    result = LecturerGet.model_validate(lecturer)
    result.comments = None
    if lecturer.comments:
        approved_comments: list[CommentGet] = [
            CommentGet.model_validate(comment)
            for comment in lecturer.comments
            if comment.review_status is ReviewStatus.APPROVED
        ]
        if "comments" in info and approved_comments:
            result.comments = sorted(approved_comments, key=lambda comment: comment.create_ts, reverse=True)
        if "mark" in info and approved_comments:
            result.mark_freebie = sum(comment.mark_freebie for comment in approved_comments) / len(approved_comments)
            result.mark_kindness = sum(comment.mark_kindness for comment in approved_comments) / len(approved_comments)
            result.mark_clarity = sum(comment.mark_clarity for comment in approved_comments) / len(approved_comments)
            result.mark_general = sum(comment.mark_general for comment in approved_comments) / len(approved_comments)
            result.mark_weighted = calc_weighted_mark(
                result.mark_general, len(approved_comments), Lecturer.mean_mark_general()
            )
        if approved_comments:
            result.subjects = list({comment.subject for comment in approved_comments})
    return result


# @lecturer.get("", response_model=LecturerGetAll)
# async def get_lecturers(
#     limit: int = 10,
#     offset: int = 0,
#     info: list[Literal["comments", "mark"]] = Query(default=[]),
#     order_by: str = Query(
#         enum=["mark_weighted", "mark_kindness", "mark_freebie", "mark_clarity", "mark_general", "last_name"],
#         default="mark_weighted",
#     ),
#     mark: float = Query(default=None, ge=-2, le=2),
#     subject: str = Query(''),
#     name: str = Query(''),
#     asc_order: bool = False,
# ) -> LecturerGetAll:
#     """
#     `limit` - максимальное количество возвращаемых преподавателей

#     `offset` - нижняя граница получения преподавателей, т.е. если по дефолту первым возвращается преподаватель с условным номером N, то при наличии ненулевого offset будет возвращаться преподаватель с номером N + offset

#     `order_by` - возможные значения `"mark_weighted", "mark_kindness", "mark_freebie", "mark_clarity", "mark_general", "last_name"`.
#     Если передано `'last_name'` - возвращается список преподавателей отсортированных по алфавиту по фамилиям
#     Если передано `'mark_...'` - возвращается список преподавателей отсортированных по конкретной оценке

#     `info` - возможные значения `'comments'`, `'mark'`.
#     Если передано `'comments'`, то возвращаются одобренные комментарии к преподавателю.
#     Если передано `'mark'`, то возвращаются общие средние оценки, а также суммарная средняя оценка по всем одобренным комментариям.

#     `subject`
#     Если передано `subject` - возвращает всех преподавателей, для которых переданное значение совпадает с одним из их предметов преподавания.
#     Также возвращает всех преподавателей, у которых есть комментарий с совпадающим с данным subject.

#     `name`
#     Поле для ФИО. Если передано `name` - возвращает всех преподователей, для которых нашлись совпадения с переданной строкой

#     `asc_order`
#     Если передано true, сортировать в порядке возрастания
#     Иначе - в порядке убывания
#     """
#     lecturers_query = (
#         Lecturer.query(session=db.session)
#         .outerjoin(Lecturer.comments)  # TODO: переписать с LEFT JOIN только комментов, которые Comment.review_status == ReviewStatus.APPROVED.
#         .group_by(Lecturer.id)
#         .filter(Lecturer.search_by_subject(subject))
#         .filter(Lecturer.search_by_name(name))
        # .order_by(
#             *(
#                 Lecturer.order_by_mark(order_by, asc_order)
#                 if "mark" in order_by
#                 else Lecturer.order_by_name(order_by, asc_order)
#             )
#         )
#     )

#     lecturers = lecturers_query.offset(offset).limit(limit).all()
#     lecturers_count = lecturers_query.group_by(Lecturer.id).count()

#     if not lecturers:
#         raise ObjectNotFound(Lecturer, 'all')
#     result = LecturerGetAll(limit=limit, offset=offset, total=lecturers_count)
#     if "mark" in info:
#         mean_mark_general = Lecturer.mean_mark_general()
#     for db_lecturer in lecturers:
#         lecturer_to_result: LecturerGet = LecturerGet.model_validate(db_lecturer)
#         lecturer_to_result.comments = None
#         if db_lecturer.comments:
#             approved_comments: list[CommentGet] = [
#                 CommentGet.model_validate(comment)
#                 for comment in db_lecturer.comments
#                 if comment.review_status is ReviewStatus.APPROVED
#             ]
#             if (mark is not None
#                 and approved_comments
#                 and sum(comment.mark_general for comment in approved_comments) / len(approved_comments) < mark):
#                 continue
#             if "comments" in info and approved_comments:
#                 lecturer_to_result.comments = sorted(
#                     approved_comments, key=lambda comment: comment.create_ts, reverse=True
#                 )
#             if "mark" in info and approved_comments:
#                 lecturer_to_result.mark_freebie = sum([comment.mark_freebie for comment in approved_comments]) / len(
#                     approved_comments
#                 )
#                 lecturer_to_result.mark_kindness = sum(comment.mark_kindness for comment in approved_comments) / len(
#                     approved_comments
#                 )
#                 lecturer_to_result.mark_clarity = sum(comment.mark_clarity for comment in approved_comments) / len(
#                     approved_comments
#                 )
#                 lecturer_to_result.mark_general = sum(comment.mark_general for comment in approved_comments) / len(
#                     approved_comments
#                 )
#                 lecturer_to_result.mark_weighted = calc_weighted_mark(
#                     lecturer_to_result.mark_general, len(approved_comments), mean_mark_general
#                 )
#             if approved_comments:
#                 lecturer_to_result.subjects = list({comment.subject for comment in approved_comments})
#         result.lecturers.append(lecturer_to_result)
#     return result


# //////////////// Мое переписывание ручки
@lecturer.get("", response_model=LecturerGetAll)
async def get_lecturers(
    lecturer_filter = FilterDepends(LecturersFilter),
    limit: int = 10,
    offset: int = 0,
    info: list[Literal["comments", "mark"]] = Query(default=[]),
    # order_by: str = Query(
    #     enum=["mark_weighted", "mark_kindness", "mark_freebie", "mark_clarity", "mark_general", "last_name"],
    #     default="mark_weighted",
    # ),
    mark: float = Query(default=None, ge=-2, le=2),
    # subject: str = Query(''),lecturers_query
    # name: str = Query(''),
    # asc_order: bool = False,
) -> LecturerGetAll:
    """
    `limit` - максимальное количество возвращаемых преподавателей

    `offset` - нижняя граница получения преподавателей, т.е. если по дефолту первым возвращается преподаватель с условным номером N, то при наличии ненулевого offset будет возвращаться преподаватель с номером N + offset

    `order_by` - возможные значения `"mark_weighted", "mark_kindness", "mark_freebie", "mark_clarity", "mark_general", "last_name"`.
    Если передано `'last_name'` - возвращается список преподавателей отсортированных по алфавиту по фамилиям
    Если передано `'mark_...'` - возвращается список преподавателей отсортированных по конкретной оценке
    Если передано просто так (или с '+' в начале параметра), то сортирует по возрастанию
    С '-' в начале -- по убыванию.

    `info` - возможные значения `'comments'`, `'mark'`.
    Если передано `'comments'`, то возвращаются одобренные комментарии к преподавателю.
    Если передано `'mark'`, то возвращаются общие средние оценки, а также суммарная средняя оценка по всем одобренным комментариям.

    `subject`
    Если передано `subject` - возвращает всех преподавателей, для которых переданное значение совпадает с одним из их предметов преподавания.
    Также возвращает всех преподавателей, у которых есть комментарий с совпадающим с данным subject.

    `name`
    Поле для ФИО. Если передано `name` - возвращает всех преподователей, для которых нашлись совпадения с переданной строкой

    `mark`
    Поле для оценки. Если передано, то возвращает только тех преподавателей, для которых средняя общая оценка ('general_mark')
    больше, чем переданный 'mark'.
    """
    lecturers_query = lecturer_filter.filter(
        Lecturer.query(session=db.session).outerjoin(Lecturer.comments).group_by(Lecturer.id)
    )
    lecturers_query = lecturer_filter.sort(lecturers_query)
    lecturers_query = lecturer_filter.sort(lecturers_query)
    lecturers = lecturers_query.offset(offset).limit(limit).all()
    lecturers_count = lecturers_query.group_by(Lecturer.id).count()

    # if not lecturers:
    #     raise ObjectNotFound(Lecturer, 'all')
    result = LecturerGetAll(limit=limit, offset=offset, total=lecturers_count)
    if "mark" in info:
        mean_mark_general = Lecturer.mean_mark_general()
    for db_lecturer in lecturers:
        lecturer_to_result: LecturerGet = LecturerGet.model_validate(db_lecturer)
        lecturer_to_result.comments = None
        if db_lecturer.comments:
            approved_comments: list[CommentGet] = [
                CommentGet.model_validate(comment)
                for comment in db_lecturer.comments
                if comment.review_status is ReviewStatus.APPROVED
            ]
            if (mark is not None
                and approved_comments
                and sum(comment.mark_general for comment in approved_comments) / len(approved_comments) < mark):
                continue
            if "comments" in info and approved_comments:
                lecturer_to_result.comments = sorted(
                    approved_comments, key=lambda comment: comment.create_ts, reverse=True
                )
            if "mark" in info and approved_comments:
                lecturer_to_result.mark_freebie = sum([comment.mark_freebie for comment in approved_comments]) / len(
                    approved_comments
                )
                lecturer_to_result.mark_kindness = sum(comment.mark_kindness for comment in approved_comments) / len(
                    approved_comments
                )
                lecturer_to_result.mark_clarity = sum(comment.mark_clarity for comment in approved_comments) / len(
                    approved_comments
                )
                lecturer_to_result.mark_general = sum(comment.mark_general for comment in approved_comments) / len(
                    approved_comments
                )
                lecturer_to_result.mark_weighted = calc_weighted_mark(
                    lecturer_to_result.mark_general, len(approved_comments), mean_mark_general
                )
            if approved_comments:
                lecturer_to_result.subjects = list({comment.subject for comment in approved_comments})
        result.lecturers.append(lecturer_to_result)
    if len(result.lecturers) == 0:
        raise ObjectNotFound(Lecturer, 'all')
    return result
# ////////////////


@lecturer.patch("/{id}", response_model=LecturerGet)
async def update_lecturer(
    id: int,
    lecturer_info: LecturerPatch,
    _=Depends(UnionAuth(scopes=["rating.lecturer.update"], allow_none=False, auto_error=True)),
) -> LecturerGet:
    """
    Scopes: `["rating.lecturer.update"]`
    """
    lecturer = Lecturer.get(id, session=db.session)
    if lecturer is None:
        raise ObjectNotFound(Lecturer, id)

    check_timetable_id = (
        Lecturer.query(session=db.session)
        .filter(and_(Lecturer.timetable_id == lecturer_info.timetable_id, Lecturer.id != id))
        .one_or_none()
    )
    if check_timetable_id:
        raise AlreadyExists(Lecturer.timetable_id, lecturer_info.timetable_id)

    result = LecturerGet.model_validate(
        Lecturer.update(lecturer.id, **lecturer_info.model_dump(exclude_unset=True), session=db.session)
    )
    result.comments = None
    return result


@lecturer.delete("/{id}", response_model=StatusResponseModel)
async def delete_lecturer(
    id: int, _=Depends(UnionAuth(scopes=["rating.lecturer.delete"], allow_none=False, auto_error=True))
):
    """
    Scopes: `["rating.lecturer.delete"]`
    """
    check_lecturer = Lecturer.get(session=db.session, id=id)
    if check_lecturer is None:
        raise ObjectNotFound(Lecturer, id)
    for comment in check_lecturer.comments:
        Comment.delete(id=comment.uuid, session=db.session)

    lecturer_user_comments = LecturerUserComment.query(session=db.session).filter(LecturerUserComment.lecturer_id == id)
    for lecturer_user_comment in lecturer_user_comments:
        LecturerUserComment.delete(lecturer_user_comment.id, session=db.session)

    Lecturer.delete(session=db.session, id=id)
    return StatusResponseModel(
        status="Success", message="Lecturer has been deleted", ru="Преподаватель удален из RatingAPI"
    )
