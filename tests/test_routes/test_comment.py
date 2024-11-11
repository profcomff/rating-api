import logging
import uuid

from starlette import status

from rating_api.models import Comment, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.settings import get_settings


logger = logging.getLogger(__name__)
url: str = '/comment'

settings = get_settings()


def test_create_comment(client, dbsession, comment, lecturer):
    lecturer = lecturer()
    body = {
        "subject": "Физика",
        "text": "Хороший препод",
        "mark_kindness": 1,
        "mark_freebie": -2,
        "mark_clarity": 0,
    }
    params = {"lecturer_id": lecturer.id}
    post_response = client.post(url, json=body, params=params)
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
    dbsession.commit()
    params = {"lecturer_id": 1}
    post_response = client.post(url, json=body, params=params)
    assert post_response.status_code == status.HTTP_404_NOT_FOUND


def test_post_bad_mark(client, lecturer):
    test_lecturer = lecturer()

    body = {
        "subject": "Физика",
        "text": "Хороший препод",
        "mark_kindness": 4,
        "mark_freebie": -2,
        "mark_clarity": 0,
    }
    params = {"lecturer_id": test_lecturer.id}
    post_response = client.post(url, json=body, params=params)
    assert post_response.status_code == status.HTTP_400_BAD_REQUEST


def test_get_comment(client, dbsession, lecturer, comment):
    test_lecturer = lecturer()
    test_comment = comment(lecturer_id=test_lecturer.id)
    random_uuid = uuid.uuid4()
    response = client.get(f'{url}/{random_uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response = client.get(f'{url}/{test_comment.uuid}')
    assert response.status_code == status.HTTP_200_OK
    comment1 = Comment.query(session=dbsession).filter(Comment.uuid == response.json()["uuid"]).one_or_none()
    assert comment1 is not None


def test_get_comments_by_lecturer_id(client, lecturer, comment):
    lecturer1 = lecturer()
    lecturer2 = lecturer()
    comment1_1 = comment(lecturer_id=lecturer1.id)
    comment1_2 = comment(lecturer_id=lecturer1.id)
    comment2_1 = comment(lecturer_id=lecturer2.id)
    query = {"lecturer_id": lecturer1.id}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["total"] == 2
    query = {"lecturer_id": lecturer2.id}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["total"] == 1
    query = {"lecturer_id": 2}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["total"] == 0


def test_get_comments_unreviewed(client, lecturer, comment):
    lecturer1 = lecturer()
    lecturer2 = lecturer()
    comment1_1 = comment(lecturer_id=lecturer1.id, review_status=ReviewStatus.APPROVED)
    comment1_2 = comment(lecturer_id=lecturer1.id, review_status=ReviewStatus.PENDING)
    comment2_1 = comment(lecturer_id=lecturer2.id, review_status=ReviewStatus.PENDING)
    comment2_2 = comment(lecturer_id=lecturer2.id, review_status=ReviewStatus.DISMISSED)
    query = {'unreviewed': True}
    response = client.get(f'{url}', params=query)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_delete_comment(client, dbsession, lecturer, comment):
    test_lecturer = lecturer()
    test_comment = comment(lecturer_id=test_lecturer.id)
    response = client.delete(f'{url}/{test_comment.uuid}')
    dbsession.refresh(test_comment)
    assert response.status_code == status.HTTP_200_OK
    response = client.get(f'{url}/{test_comment.uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
    random_uuid = uuid.uuid4()
    response = client.delete(f'{url}/{random_uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
    comment1 = Comment.query(session=dbsession).filter(Comment.uuid == test_comment.uuid).one_or_none()
    assert comment1 is None
    assert test_comment.is_deleted
