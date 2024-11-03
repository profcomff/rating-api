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
    assert "Физика" in json_response["subjects"]
    assert len(json_response["comments"]) != 0
    dbsession.delete(comment1)
    dbsession.delete(comment2)
    dbsession.delete(comment3)
    dbsession.delete(lecturer)
    dbsession.commit()


def test_get_lecturers_by_name(client, dbsession):
    body_list = [
        {"first_name": 'Алиса', "last_name": 'Селезнёва', "middle_name": 'Ивановна', "timetable_id": 0},
        {"first_name": 'Марат', "last_name": 'Сельков', "middle_name": 'Анатольевич', "timetable_id": 1},
        {"first_name": 'М.', "last_name": 'Измайлов', "middle_name": 'Р.', "timetable_id": 2},
        {"first_name": 'Михаил', "last_name": 'Измайлов', "middle_name": 'Ильич', "timetable_id": 3},
    ]
    lecturer_list: list[Lecturer] = [Lecturer(**body_list[i]) for i in range(4)]
    for lecturer in lecturer_list:
        dbsession.add(lecturer)
    dbsession.commit()
    db_lecturer: Lecturer = Lecturer.query(session=dbsession).filter(Lecturer.timetable_id == 0).one_or_none()
    assert db_lecturer is not None
    query = {"name": "Селезнёва"}
    get_response = client.get(f'{url}', params=query)
    assert get_response.status_code == status.HTTP_200_OK
    json_response = get_response.json()
    assert json_response["total"] == 1
    assert json_response["lecturers"][0]["first_name"] == "Алиса"

    query = {"name": "Селе"}
    get_response = client.get(f'{url}', params=query)
    assert get_response.status_code == status.HTTP_200_OK
    json_response = get_response.json()
    assert json_response["total"] == 2
    assert json_response["lecturers"][0]["first_name"] == "Алиса"
    assert json_response["lecturers"][1]["first_name"] == "Марат"

    query = {"name": "Сель"}
    get_response = client.get(f'{url}', params=query)
    assert get_response.status_code == status.HTTP_200_OK
    json_response = get_response.json()
    assert json_response["total"] == 2
    assert json_response["lecturers"][0]["first_name"] == "Марат"
    assert json_response["lecturers"][1]["first_name"] == "Алиса"

    query = {"name": "ИзмайлАв МихОил"}
    get_response = client.get(f'{url}', params=query)
    assert get_response.status_code == status.HTTP_200_OK
    json_response = get_response.json()
    assert json_response["total"] == 2
    assert json_response["lecturers"][0]["first_name"] == "Михаил"
    assert json_response["lecturers"][1]["first_name"] == "М."

    query = {"name": "Михаил Рашидович"}
    get_response = client.get(f'{url}', params=query)
    assert get_response.status_code == status.HTTP_200_OK
    json_response = get_response.json()
    assert json_response["total"] == 1
    assert json_response["lecturers"][0]["first_name"] == "М."

    for lecturer in lecturer_list:
        dbsession.delete(lecturer)
    dbsession.commit()


def test_update_lecturer(client, dbsession):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    lecturer: Lecturer = Lecturer(**body)
    dbsession.add(lecturer)
    dbsession.commit()
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
    dbsession.delete(lecturer)
    dbsession.commit()


def test_delete_lecturer(client, dbsession):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    lecturer: Lecturer = Lecturer(**body)
    dbsession.add(lecturer)
    dbsession.commit()
    comment: dict = {
        "subject": "Физика",
        "text": "Хороший преподаватель",
        "mark_kindness": 2,
        "mark_freebie": 0,
        "mark_clarity": 2,
        "lecturer_id": lecturer.id,
        "review_status": ReviewStatus.APPROVED,
    }
    comment: Comment = Comment.create(session=dbsession, **comment)
    dbsession.commit()
    lecturer = dbsession.query(Lecturer).filter(Lecturer.timetable_id == 0).one_or_none()
    assert lecturer is not None
    response = client.delete(f"{url}/{lecturer.id}")
    assert response.status_code == status.HTTP_200_OK
    response = client.delete(f"{url}/{lecturer.id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
