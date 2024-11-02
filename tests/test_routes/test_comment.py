import logging
import uuid

from starlette import status

from rating_api.models import Comment, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.settings import get_settings


logger = logging.getLogger(__name__)
url: str = '/comment'

settings = get_settings()


def test_create_comment(client, dbsession):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    lecturer: Lecturer = Lecturer(**body)
    dbsession.add(lecturer)
    dbsession.commit()

    body = {
        "subject": "Физика",
        "text": "Хороший препод",
        "mark_kindness": 1,
        "mark_freebie": -2,
        "mark_clarity": 0,
    }
    params = {"lecturer_id": lecturer.id}
    post_response = client.post(url, json=body, params=params)
    print(post_response.json())
    assert post_response.status_code == status.HTTP_200_OK
    json_response = post_response.json()
    comment = Comment.query(session=dbsession).filter(Comment.uuid == json_response["uuid"]).one_or_none()
    assert comment is not None
    user_comment = (
        LecturerUserComment.query(session=dbsession)
        .filter(LecturerUserComment.lecturer_id == lecturer.id)
        .one_or_none()
    )
    assert user_comment is not None
    dbsession.delete(user_comment)
    dbsession.delete(comment)
    dbsession.delete(lecturer)
    dbsession.commit()
    post_response = client.post(url, json=body, params=params)
    assert post_response.status_code == status.HTTP_404_NOT_FOUND


def test_post_bad_mark(client, dbsession):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    lecturer: Lecturer = Lecturer(**body)
    dbsession.add(lecturer)
    dbsession.commit()

    body = {
        "subject": "Физика",
        "text": "Хороший препод",
        "mark_kindness": 4,
        "mark_freebie": -2,
        "mark_clarity": 0,
    }
    params = {"lecturer_id": lecturer.id}
    post_response = client.post(url, json=body, params=params)
    assert post_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    dbsession.delete(lecturer)
    dbsession.commit()


def test_get_comment(client, dbsession):
    body = {
        "first_name": 'Иван',
        "last_name": 'Иванов',
        "middle_name": 'Иванович',
        "timetable_id": 0,
    }
    lecturer: Lecturer = Lecturer(**body)
    dbsession.add(lecturer)
    dbsession.commit()

    body = {
        "lecturer_id": lecturer.id,
        "subject": "Физика",
        "text": "Хороший препод",
        "mark_kindness": 1,
        "mark_freebie": -2,
        "mark_clarity": 0,
        "review_status": ReviewStatus.APPROVED,
    }
    comment: Comment = Comment(**body)
    dbsession.add(comment)
    dbsession.commit()
    response_comment = client.get(f'{url}/{comment.uuid}')
    assert response_comment.status_code == status.HTTP_200_OK
    random_uuid = uuid.uuid4()
    response = client.get(f'{url}/{random_uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
    comment = Comment.query(session=dbsession).filter(Comment.uuid == response_comment.json()["uuid"]).one_or_none()
    assert comment is not None
    dbsession.delete(comment)
    dbsession.delete(lecturer)
    dbsession.commit()


def test_delete_comment(client, dbsession):
    body = {"first_name": 'Иван', "last_name": 'Иванов', "middle_name": 'Иванович', "timetable_id": 0}
    lecturer: Lecturer = Lecturer(**body)
    dbsession.add(lecturer)
    dbsession.commit()

    body = {
        "lecturer_id": lecturer.id,
        "subject": "Физика",
        "text": "Хороший препод",
        "mark_kindness": 1,
        "mark_freebie": -2,
        "mark_clarity": 0,
        "review_status": ReviewStatus.APPROVED,
    }
    comment: Comment = Comment(**body)
    dbsession.add(comment)
    dbsession.commit()
    response = client.delete(f'{url}/{comment.uuid}')
    assert response.status_code == status.HTTP_200_OK
    random_uuid = uuid.uuid4()
    response = client.delete(f'{url}/{random_uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
    comment = Comment.query(session=dbsession).filter(Comment.uuid == comment.uuid).one_or_none()
    assert comment is None
    dbsession.delete(lecturer)
    dbsession.commit()
