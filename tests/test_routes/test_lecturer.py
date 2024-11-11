import logging

from starlette import status
import pytest
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


def test_get_lecturer(client, lecturer):
    lecturer = lecturer()
    get_response = client.get(f'{url}/{lecturer.id}')
    print(get_response.json())
    assert get_response.status_code == status.HTTP_200_OK
    json_response = get_response.json()
    assert json_response["mark_kindness"] is None
    assert json_response["mark_freebie"] is None
    assert json_response["mark_clarity"] is None
    assert json_response["mark_general"] is None
    assert json_response["comments"] is None


def test_get_lecturer_with_comments(client, lecturer, comment):
    test_lecturer = lecturer()
    comment1 = comment(lecturer_id=test_lecturer.id, review_status=ReviewStatus.APPROVED)
    comment2 = comment(lecturer_id=test_lecturer.id, review_status=ReviewStatus.PENDING)
    comment3 = comment(lecturer_id=test_lecturer.id, review_status=ReviewStatus.DISMISSED)
    query = {
        "info": ['comments', 'mark'],
    }
    response = client.get(f'{url}/{test_lecturer.id}', params=query)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["mark_kindness"] == comment1.mark_kindness
    assert json_response["mark_freebie"] == comment1.mark_freebie
    assert json_response["mark_clarity"] == comment1.mark_clarity
    assert json_response["mark_general"] == (comment1.mark_kindness + comment1.mark_freebie + comment1.mark_clarity) / 3
    assert len(json_response["comments"]) == 1
    assert json_response["comments"][0]["text"] == comment1.text


def test_get_lecturers_by_name(client, lecturer):
    lecturer1 = lecturer(first_name='Алиса', last_name='Селезнёва', middle_name='Ивановна')
    lecturer2 = lecturer(first_name='Марат', last_name='Сельков', middle_name='Анатольевич')
    lecturer3 = lecturer(first_name='М', last_name='Измайлов', middle_name='Р')
    lecturer4 = lecturer(first_name='Михаил', last_name='Измайлов', middle_name='Ильич')
    query = {"name": "Селезнёва"}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["total"] == 1
    assert json_response["lecturers"][0]["first_name"] == "Алиса"

    query = {"name": "Сел"}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["total"] == 2
    assert json_response["lecturers"][0]["first_name"] == "Алиса"
    assert json_response["lecturers"][1]["first_name"] == "Марат"

    query = {"name": "Измайлова"}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_lecturers_by_subject(client, lecturer, comment):
    lecturer1 = lecturer()
    comment1 = comment(lecturer_id=lecturer1.id, subject="bibki")
    lecturer2 = lecturer()
    comment2 = comment(lecturer_id=lecturer2.id, subject="bibki")
    lecturer3 = lecturer()
    comment3 = comment(lecturer_id=lecturer2.id, subject="bobki")
    query = {"subject": "bibki"}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["total"] == 2
    query = {"subject": "bibobki"}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_lecturer(client, lecturer):
    test_lecturer = lecturer()
    body = {
        "first_name": 'Алексей',
        "last_name": 'Алексеев',
        "middle_name": 'Алексеевич',
    }
    response = client.patch(f"{url}/{test_lecturer.id}", json=body)
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
    response = client.patch(f"{url}/{test_lecturer.id}", json=body)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["first_name"] == 'Иван'
    assert json_response["last_name"] == 'Иванов'
    assert json_response["middle_name"] == "Иванович"


def test_delete_lecturer(client, lecturer, comment, dbsession):
    test_lecturer = lecturer()
    test_comment = comment(lecturer_id=test_lecturer.id)
    response = client.delete(f"{url}/{test_lecturer.id}")
    assert response.status_code == status.HTTP_200_OK
    response = client.delete(f"{url}/{test_lecturer.id}")
    dbsession.refresh(test_lecturer)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response = client.get(f"{url}/{test_lecturer.id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert test_comment.is_deleted
    assert test_lecturer.is_deleted
