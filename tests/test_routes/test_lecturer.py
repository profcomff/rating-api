import logging

import pytest
from fastapi_sqlalchemy import db
from sqlalchemy import and_, func, select
from starlette import status

from rating_api.models import Comment, Lecturer, ReviewStatus
from rating_api.settings import get_settings
from rating_api.utils.mark import calc_weighted_mark


logger = logging.getLogger(__name__)
url: str = '/lecturer'

settings = get_settings()


@pytest.mark.parametrize('response_status', [status.HTTP_200_OK, status.HTTP_409_CONFLICT])
def test_create_lecturer(client, dbsession, response_status):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    post_response = client.post(url, json=body)
    assert post_response.status_code == response_status
    # cleanup on a last run
    if response_status == status.HTTP_409_CONFLICT:
        lecturer = dbsession.query(Lecturer).filter(Lecturer.timetable_id == 0).one_or_none()
        assert lecturer is not None
        dbsession.delete(lecturer)
        dbsession.commit()
        lecturer = dbsession.query(Lecturer).filter(Lecturer.timetable_id == 0).one_or_none()
        assert lecturer is None


@pytest.mark.parametrize(
    'lecturer_n,response_status',
    [
        (0, status.HTTP_200_OK),
        (1, status.HTTP_200_OK),
        (2, status.HTTP_200_OK),
        (3, status.HTTP_404_NOT_FOUND),
    ],
)
def test_get_lecturer(client, dbsession, lecturers, lecturer_n, response_status):
    lecturer = (
        dbsession.query(Lecturer).filter(Lecturer.timetable_id == lecturers[lecturer_n].timetable_id).one_or_none()
    )
    # check non-existing id request
    lecturer_id = -1
    if lecturer:
        lecturer_id = lecturer.id
    get_response = client.get(f'{url}/{lecturer_id}')
    assert get_response.status_code == response_status
    if response_status == status.HTTP_200_OK:
        json_response = get_response.json()
        assert json_response["mark_kindness"] is None
        assert json_response["mark_freebie"] is None
        assert json_response["mark_clarity"] is None
        assert json_response["mark_general"] is None
        assert json_response["comments"] is None


@pytest.mark.parametrize(
    'lecturer_n,mark_kindness,mark_freebie,mark_clarity,mark_general',
    [(0, 1.5, 1.5, 1.5, 1.5), (1, 0, 0, 0, 0), (2, 0.5, 0.5, 0.5, 0.5)],
)
def test_get_lecturer_with_comments(
    client, lecturers_with_comments, lecturer_n, mark_kindness, mark_freebie, mark_clarity, mark_general
):
    lecturers, comments = lecturers_with_comments
    query = {"info": ['comments', 'mark']}
    response = client.get(f'{url}/{lecturers[lecturer_n].id}', params=query)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["mark_kindness"] == mark_kindness
    assert json_response["mark_freebie"] == mark_freebie
    assert json_response["mark_clarity"] == mark_clarity
    assert json_response["mark_general"] == mark_general
    assert comments[lecturer_n * 6 + 0].subject in json_response["subjects"]
    assert comments[lecturer_n * 6 + 1].subject in json_response["subjects"]
    assert comments[lecturer_n * 6 + 2].subject not in json_response["subjects"]
    assert len(json_response["comments"]) == 4


@pytest.mark.parametrize(
    'query,total,response_status',
    [
        ({'name': 'test_lname1'}, 1, status.HTTP_200_OK),
        ({'name': 'TeSt_LnAmE1'}, 1, status.HTTP_200_OK),
        ({'name': 'test'}, 2, status.HTTP_200_OK),
        ({'name': 'testlname123'}, 0, status.HTTP_404_NOT_FOUND),
    ],
)
def test_get_lecturers_by_name(client, lecturers, query, total, response_status):
    get_response = client.get(f'{url}', params=query)
    assert get_response.status_code == response_status
    if response_status == status.HTTP_200_OK:
        json_response = get_response.json()
        json_response["total"] == total
        assert json_response["lecturers"][0]["first_name"] == lecturers[0].first_name


@pytest.mark.usefixtures('lecturers_with_comments')
@pytest.mark.parametrize(
    'query, response_status',
    [
        ({'subject': 'test_subject'}, status.HTTP_200_OK),
        ({'subject': 'test_subject13'}, status.HTTP_200_OK),
        ({'subject': 'test_subject666'}, status.HTTP_404_NOT_FOUND),
    ],
    ids=[
        'get_all',
        'get_some',
        'wrong_subject',
    ],
)
def test_get_lecturers_by_subject(client, dbsession, query, response_status):
    """
    Проверка, что при передаче subject возвращаются только лекторы,
    в одобренных комментариях к которым есть поле subject, совпадающее с переданным.
    """
    resp = client.get(f'{url}', params=query)
    assert resp.status_code == response_status
    if response_status == status.HTTP_200_OK:
        db_lecturers = {
            comment.lecturer_id
            for comment in Comment.query(session=dbsession).filter(
                and_(Comment.review_status == ReviewStatus.APPROVED, Comment.subject == query['subject'])
            )
        }
        resp_lecturers = {lecturer['id'] for lecturer in resp.json()['lecturers']}
        assert resp_lecturers == db_lecturers


@pytest.mark.usefixtures('lecturers_with_comments')
@pytest.mark.parametrize(
    'query, response_status',
    [
        ({'mark': -2}, status.HTTP_200_OK),
        ({'mark': 0}, status.HTTP_200_OK),
        ({'mark': 2}, status.HTTP_404_NOT_FOUND),
        ({'mark': -3}, status.HTTP_422_UNPROCESSABLE_ENTITY),
        ({'mark': 3}, status.HTTP_422_UNPROCESSABLE_ENTITY),
    ],
    ids=['get_all', 'get_some', 'get_nothing', 'under_min', 'above_max'],
)
def test_get_lecturers_by_mark(client, dbsession, query, response_status):
    """
    Проверка, что при передаче mark возвращаются только лекторы
    со средним mark_general (по комментариям) не меньше, чем переданный mark.
    """
    resp = client.get(f'{url}', params=query)
    assert resp.status_code == response_status
    if response_status == status.HTTP_200_OK:
        res = dbsession.execute(
            (
                select(Lecturer.id.label('lecturer'), func.avg(Comment.mark_general).label('avg'))
                .join(Comment, and_(Comment.review_status == ReviewStatus.APPROVED, Lecturer.id == Comment.lecturer_id))
                .group_by(Lecturer.id)
                .having(func.avg(Comment.mark_general) >= query['mark'])
            )
        ).all()
        resp_lecturers = {lecturer['id'] for lecturer in resp.json()['lecturers']}
        db_lecturers = {req[0] for req in res}
        assert resp_lecturers == db_lecturers, 'Убедитесь, что все подходящие лекторы отправляются пользователю!'


@pytest.mark.usefixtures('lecturers_with_comments')
@pytest.mark.parametrize(
    'query, response_status',
    [
        ({'info': ['comments', 'mark']}, status.HTTP_200_OK),
        ({'info': ['comments']}, status.HTTP_200_OK),
        ({'info': ['mark']}, status.HTTP_200_OK),
        ({'info': []}, status.HTTP_200_OK),
        ({'info': {}}, status.HTTP_422_UNPROCESSABLE_ENTITY),
        ({'info': ['pupupu']}, status.HTTP_422_UNPROCESSABLE_ENTITY),
    ],
    ids=["comments_and_marks", "only_comments", "only_marks", "no_info", "invalid_iterator", "invalid_param"],
)
def test_get_lecturers_by_info(client, dbsession, query, response_status):
    """
    Проверка, что при передаче info разного состава возвращаются лекторы
    с полями комментариев и/или оценок на основе них для каждого лектора.
    """
    resp = client.get(f'{url}', params=query)
    assert resp.status_code == response_status
    if response_status == status.HTTP_200_OK:
        if 'mark' in query['info']:
            db_res = dbsession.execute(
                (
                    select(
                        Lecturer.id.label('lecturer'),
                        func.avg(Comment.mark_freebie).label('avg_freebie'),
                        func.avg(Comment.mark_kindness).label('avg_kindness'),
                        func.avg(Comment.mark_clarity).label('avg_clarity'),
                        func.avg(Comment.mark_general).label('avg_general'),
                    )
                    .join(
                        Comment,
                        and_(Comment.review_status == ReviewStatus.APPROVED, Lecturer.id == Comment.lecturer_id),
                    )
                    .group_by(Lecturer.id)
                )
            ).all()
            with db():
                mean_mark_general = Lecturer.mean_mark_general()
            db_lecturers = {
                (
                    *lecturer,
                    calc_weighted_mark(
                        float(lecturer[-1]),
                        Comment.query(session=dbsession)
                        .filter(
                            and_(Comment.review_status == ReviewStatus.APPROVED, Comment.lecturer_id == lecturer[0])
                        )
                        .count(),
                        mean_mark_general,
                    ),
                )
                for lecturer in db_res
            }
            resp_lecturers = {
                (
                    lecturer['id'],
                    lecturer['mark_freebie'],
                    lecturer['mark_kindness'],
                    lecturer['mark_clarity'],
                    lecturer['mark_general'],
                    lecturer['mark_weighted'],
                )
                for lecturer in resp.json()['lecturers']
            }
            assert resp_lecturers == db_lecturers
        if 'comments' in query['info']:
            db_res = dbsession.execute(
                (
                    select(Lecturer.id.label('lecturer'), func.count(Comment.uuid))
                    .join(
                        Comment,
                        and_(Comment.review_status == ReviewStatus.APPROVED, Lecturer.id == Comment.lecturer_id),
                    )
                    .group_by(Lecturer.id)
                )
            ).all()
            db_lecturers = {*db_res}
            assert len(resp.json()['lecturers']) == len(db_lecturers)
            for lecturer in resp.json()['lecturers']:
                assert (lecturer['id'], len(lecturer['comments'])) in db_lecturers


@pytest.mark.usefixtures('lecturers_with_comments')
@pytest.mark.parametrize(
    'query, response_status',
    [
        ({'order_by': 'mark_kindness'}, status.HTTP_200_OK),
        ({}, status.HTTP_200_OK),
        ({'order_by': '+mark_freebie'}, status.HTTP_200_OK),
        ({'order_by': '-mark_clarity'}, status.HTTP_200_OK),
        ({'order_by': 'pupupu'}, status.HTTP_422_UNPROCESSABLE_ENTITY),
        ({'order_by': 'mark_kindness,mark_freebie'}, status.HTTP_422_UNPROCESSABLE_ENTITY),
    ],
    ids=["valid", "valid_default", "valid_plus", "valid_minus", "invalid_param", "invalid_many_params"],
)
def test_get_lecturers_order_by(client, dbsession, query, response_status):
    """
    Проверка, что при передаче (или нет) параметра order_by возвращаемый
    список лекторов верно сортируется.
    """
    resp = client.get(f'{url}', params=query)
    assert resp.status_code == response_status
    if response_status == status.HTTP_200_OK:
        if 'order_by' not in query:
            field_name = 'mark_weighted'
            asc_order = True
        elif query['order_by'].startswith('+'):
            field_name = query['order_by'][1:]
            asc_order = True
        elif query['order_by'].startswith('-'):
            field_name = query['order_by'][1:]
            asc_order = False
        else:
            field_name = query['order_by']
            asc_order = True
        with db():
            db_res = (
                Lecturer.query(session=dbsession)
                .join(Comment, and_(Comment.review_status == ReviewStatus.APPROVED, Lecturer.id == Comment.lecturer_id))
                .group_by(Lecturer.id)
                .order_by(*Lecturer.order_by_mark(field_name, asc_order))
                .all()
            )
        db_lecturers = [lecturer.id for lecturer in db_res]
        resp_lecturers = [lecturer['id'] for lecturer in resp.json()['lecturers']]
        assert resp_lecturers == db_lecturers


@pytest.mark.parametrize(
    'body,response_status',
    [
        (
            {
                "first_name": 'Test',
                "last_name": 'Testov',
                "middle_name": 'Testovich',
            },
            status.HTTP_200_OK,
        ),
        (
            {
                "first_name": 'Testa',
                "last_name": 'Testova',
                "middle_name": 'Testovna',
            },
            status.HTTP_200_OK,
        ),
        (
            {
                "first_name": 'Test',
                "last_name": 'Testov',
                "middle_name": 1,
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    ],
)
def test_update_lecturer(client, lecturer, body, response_status):
    response = client.get(f'{url}/{lecturer.id}')
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response['first_name'] == lecturer.first_name
    assert json_response['last_name'] == lecturer.last_name
    assert json_response['middle_name'] == lecturer.middle_name
    response = client.patch(f"{url}/{lecturer.id}", json=body)
    assert response.status_code == response_status
    if response_status == status.HTTP_200_OK:
        json_response = response.json()
        assert json_response["first_name"] == body["first_name"]
        assert json_response["last_name"] == body["last_name"]
        assert json_response["middle_name"] == body["middle_name"]


def test_delete_lecturer(client, dbsession, lecturers_with_comments):
    lecturers, comments = lecturers_with_comments
    response = client.delete(f"{url}/{lecturers[0].id}")
    assert response.status_code == status.HTTP_200_OK
    # trying to delete deleted
    response = client.delete(f"{url}/{lecturers[0].id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    dbsession.refresh(comments[0])
    dbsession.refresh(comments[1])
    dbsession.refresh(comments[2])
    dbsession.refresh(lecturers[0])
    assert comments[0].is_deleted
    assert comments[1].is_deleted
    assert comments[2].is_deleted
    assert lecturers[0].is_deleted
    # trying to get deleted
    response = client.get(f'{url}/{lecturers[0].id}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
