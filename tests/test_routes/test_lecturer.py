import logging

import pytest
from starlette import status

from rating_api.models import Comment, Lecturer, ReviewStatus
from rating_api.settings import get_settings


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
    assert comments[lecturer_n * 4 + 0].subject in json_response["subjects"]
    assert comments[lecturer_n * 4 + 1].subject in json_response["subjects"]
    assert comments[lecturer_n * 4 + 2].subject not in json_response["subjects"]
    assert len(json_response["comments"]) == 2


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
