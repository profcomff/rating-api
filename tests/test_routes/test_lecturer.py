import logging

from starlette import status

from rating_api.models import Comment, Lecturer, ReviewStatus
from rating_api.settings import get_settings


logger = logging.getLogger(__name__)
url: str = '/lecturer'

settings = get_settings()


def test_create_lecturer(client, dbsession):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    post_response = client.post(url, json=body)
    assert post_response.status_code == status.HTTP_200_OK
    check_same_response = client.post(url, json=body)
    assert check_same_response.status_code == status.HTTP_409_CONFLICT
    lecturer = dbsession.query(Lecturer).filter(Lecturer.timetable_id == 0).one_or_none()
    assert lecturer is not None
    dbsession.delete(lecturer)
    dbsession.commit()
    lecturer = dbsession.query(Lecturer).filter(Lecturer.timetable_id == 0).one_or_none()
    assert lecturer is None


def test_get_lecturer(client, dbsession):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    lecturer: Lecturer = Lecturer(**body)
    dbsession.add(lecturer)
    dbsession.commit()
    db_lecturer: Lecturer = Lecturer.query(session=dbsession).filter(Lecturer.timetable_id == 0).one_or_none()
    assert db_lecturer is not None
    get_response = client.get(f'{url}/{db_lecturer.id}')
    print(get_response.json())
    assert get_response.status_code == status.HTTP_200_OK
    json_response = get_response.json()
    assert json_response["mark_kindness"] is None
    assert json_response["mark_freebie"] is None
    assert json_response["mark_clarity"] is None
    assert json_response["mark_general"] is None
    assert json_response["comments"] is None
    dbsession.delete(lecturer)
    dbsession.commit()


def test_get_lecturer_with_comments(client, dbsession):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    lecturer: Lecturer = Lecturer(**body)
    dbsession.add(lecturer)
    dbsession.commit()
    db_lecturer: Lecturer = Lecturer.query(session=dbsession).filter(Lecturer.timetable_id == 0).one_or_none()
    assert db_lecturer is not None

    comment1: dict = {
        "subject": "Физика",
        "text": "Хороший преподаватель",
        "mark_kindness": 2,
        "mark_freebie": 0,
        "mark_clarity": 2,
        "lecturer_id": db_lecturer.id,
        "review_status": ReviewStatus.APPROVED,
    }
    comment2: dict = {
        "subject": "Физика",
        "text": "Средне",
        "mark_kindness": -1,
        "mark_freebie": 1,
        "mark_clarity": -1,
        "lecturer_id": db_lecturer.id,
        "review_status": ReviewStatus.APPROVED,
    }
    comment3: dict = {
        "subject": "Физика",
        "text": "Средне",
        "mark_kindness": 2,
        "mark_freebie": 2,
        "mark_clarity": 2,
        "lecturer_id": db_lecturer.id,
        "review_status": ReviewStatus.PENDING,
    }
    comment1: Comment = Comment.create(session=dbsession, **comment1)
    comment2: Comment = Comment.create(session=dbsession, **comment2)
    comment3: Comment = Comment.create(session=dbsession, **comment3)
    dbsession.commit()
    assert comment1 is not None
    assert comment2 is not None
    assert comment3 is not None
    query = {
        "info": ['comments', 'mark'],
    }
    response = client.get(f'{url}/{db_lecturer.id}', params=query)
    print(response.json())
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["mark_kindness"] == 0.5
    assert json_response["mark_freebie"] == 0.5
    assert json_response["mark_clarity"] == 0.5
    assert json_response["mark_general"] == 0.5
    assert json_response["subject"] == "Физика"
    assert len(json_response["comments"]) != 0


def test_update_lecturer(client, dbsession):
    body = {
        "first_name": 'Алексей',
        "last_name": 'Алексеев',
        "middle_name": 'Алексеевич',
    }
    db_lecturer: Lecturer = Lecturer.query(session=dbsession).filter(Lecturer.timetable_id == 0).one_or_none()
    assert db_lecturer is not None
    response = client.patch(f"{url}/{db_lecturer.id}", json=body)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["first_name"] == 'Алексей'
    assert json_response["last_name"] == 'Алексеев'
    assert json_response["middle_name"] == "Алексеевич"
    body = {
        "first_name": 'Иван',
        "last_name": 'Иванов',
        "middle_name": 'Иванович',
    }
    response = client.patch(f"{url}/{db_lecturer.id}", json=body)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["first_name"] == 'Иван'
    assert json_response["last_name"] == 'Иванов'
    assert json_response["middle_name"] == "Иванович"


def test_delete_lecturer(client, dbsession):
    lecturer = dbsession.query(Lecturer).filter(Lecturer.timetable_id == 0).one_or_none()
    assert lecturer is not None
    response = client.delete(f"{url}/{lecturer.id}")
    assert response.status_code == status.HTTP_200_OK
    response = client.delete(f"{url}/{lecturer.id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
