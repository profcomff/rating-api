from typing import Literal

from auth_lib.fastapi import UnionAuth
from fastapi import APIRouter, Depends, Query
from fastapi_sqlalchemy import db
from sqlalchemy import and_

from rating_api.exceptions import AlreadyExists, ObjectNotFound
from rating_api.models import Comment, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.schemas.base import StatusResponseModel
from rating_api.schemas.models import CommentGet, LecturerGet, LecturerGetAll, LecturerPatch, LecturerPost


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
        return LecturerGet.model_validate(new_lecturer)
    raise AlreadyExists(Lecturer, lecturer_info.timetable_id)


@lecturer.get("/{id}", response_model=LecturerGet)
async def get_lecturer(
    id: int,
    info: list[Literal["comments", "mark"]] = Query(default=[])
) -> LecturerGet:
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
            result.comments = approved_comments
        if "mark" in info and approved_comments:
            result.mark_freebie = sum([comment.mark_freebie for comment in approved_comments]) / len(approved_comments)
            result.mark_kindness = sum(comment.mark_kindness for comment in approved_comments) / len(approved_comments)
            result.mark_clarity = sum(comment.mark_clarity for comment in approved_comments) / len(approved_comments)
            general_marks = [result.mark_freebie, result.mark_kindness, result.mark_clarity]
            result.mark_general = sum(general_marks) / len(general_marks)
        if approved_comments:
            result.subjects = list({comment.subject for comment in approved_comments})
    return result


@lecturer.get("", response_model=LecturerGetAll)
async def get_lecturers(
    limit: int = 10,
    offset: int = 0,
    info: list[Literal["comments", "mark"]] = Query(default=[]),
    order_by: list[Literal["general", '']] = Query(default=[]),
    subject: str = Query(''),
    name: str = Query(''),
) -> LecturerGetAll:
    """
    Scopes: `["rating.lecturer.read"]`

    `limit` - максимальное количество возвращаемых преподавателей

    `offset` - нижняя граница получения преподавателей, т.е. если по дефолту первым возвращается преподаватель с условным номером N, то при наличии ненулевого offset будет возвращаться преподаватель с номером N + offset

    `order_by` - возможные значения `'general'`.
    Если передано `'general'` - возвращается список преподавателей отсортированных по общей оценке

    `info` - возможные значения `'comments'`, `'mark'`.
    Если передано `'comments'`, то возвращаются одобренные комментарии к преподавателю.
    Если передано `'mark'`, то возвращаются общие средние оценки, а также суммарная средняя оценка по всем одобренным комментариям.

    `subject`
    Если передано `subject` - возвращает всех преподавателей, для которых переданное значение совпадает с одним из их предметов преподавания.
    Также возвращает всех преподавателей, у которых есть комментарий с совпадающим с данным subject.

    `name`
    Поле для ФИО. Если передано `name` - возвращает всех преподователей, для которых нашлись совпадения с переданной строкой
    """
    lecturers = Lecturer.query(session=db.session).filter(Lecturer.search(name)).all()
    if not lecturers:
        raise ObjectNotFound(Lecturer, 'all')
    result = LecturerGetAll(limit=limit, offset=offset, total=len(lecturers))
    for db_lecturer in lecturers[offset : limit + offset]:
        lecturer_to_result: LecturerGet = LecturerGet.model_validate(db_lecturer)
        lecturer_to_result.comments = None
        if db_lecturer.comments:
            approved_comments: list[CommentGet] = [
                CommentGet.model_validate(comment)
                for comment in db_lecturer.comments
                if comment.review_status is ReviewStatus.APPROVED
            ]
            if "comments" in info and approved_comments:
                lecturer_to_result.comments = approved_comments
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
                general_marks = [
                    lecturer_to_result.mark_freebie,
                    lecturer_to_result.mark_kindness,
                    lecturer_to_result.mark_clarity,
                ]
                lecturer_to_result.mark_general = sum(general_marks) / len(general_marks)
            if approved_comments:
                lecturer_to_result.subjects = list({comment.subject for comment in approved_comments})
        result.lecturers.append(lecturer_to_result)
    if "general" in order_by:
        result.lecturers.sort(key=lambda item: (item.mark_general is None, item.mark_general))
    if subject:
        result.lecturers = [
            lecturer for lecturer in result.lecturers if lecturer.subjects and subject in lecturer.subjects
        ]
    result.total = len(result.lecturers)
    return result


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
