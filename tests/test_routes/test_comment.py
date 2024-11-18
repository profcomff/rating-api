import logging
import uuid

import pytest
from starlette import status

from rating_api.models import Comment, Lecturer, LecturerUserComment, ReviewStatus
from rating_api.settings import get_settings


logger = logging.getLogger(__name__)
url: str = '/comment'

settings = get_settings()


@pytest.mark.parametrize(
    'body,timetable_id,response_status',
    [
        (
            {
                "subject": "test_subject",
                "text": "test_text",
                "mark_kindness": 1,
                "mark_freebie": 0,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_200_OK,
        ),
        (
            {
                "subject": "test1_subject",
                "text": "test_text",
                "mark_kindness": -2,
                "mark_freebie": -2,
                "mark_clarity": -2,
            },
            1,
            status.HTTP_200_OK,
        ),
        (  # bad mark
            {
                "subject": "test_subject",
                "text": "test_text",
                "mark_kindness": 5,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            2,
            status.HTTP_400_BAD_REQUEST,
        ),
        (  # deleted lecturer
            {
                "subject": "test_subject",
                "text": "test_text",
                "mark_kindness": 5,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            3,
            status.HTTP_400_BAD_REQUEST,
        ),
    ],
)
def test_create_comment(client, dbsession, lecturers, body, timetable_id, response_status):
    params = {"lecturer_id": lecturers[timetable_id].id}  # Ensure we get the ID of the lecturer
    post_response = client.post(url, json=body, params=params)
    assert post_response.status_code == response_status
    if response_status == status.HTTP_200_OK:
        comment = Comment.query(session=dbsession).filter(Comment.uuid == post_response.json()["uuid"]).one_or_none()
        assert comment is not None
        user_comment = (
            LecturerUserComment.query(session=dbsession)
            .filter(LecturerUserComment.lecturer_id == lecturers[timetable_id].id)
            .one_or_none()
        )
        assert user_comment is not None


def test_get_comment(client, comment):
    response_comment = client.get(f'{url}/{comment.uuid}')
    assert response_comment.status_code == status.HTTP_200_OK
    random_uuid = uuid.uuid4()
    response = client.get(f'{url}/{random_uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    'timetable_id,response_status', [(0, status.HTTP_200_OK), (1, status.HTTP_200_OK), (3, status.HTTP_200_OK)]
)
def test_comments_by_lecturer_id(client, lecturers_with_comments, timetable_id, response_status):
    lecturers, comments = lecturers_with_comments
    response = client.get(f'{url}', params={"lecturer_id": lecturers[timetable_id].id})
    assert response.status_code == response_status
    if response.status_code == status.HTTP_200_OK:
        json_response = response.json()
        assert len(json_response["comments"]) == len(
            [
                comment
                for comment in lecturers[timetable_id].comments
                if comment.review_status == ReviewStatus.APPROVED and not comment.is_deleted
            ]
        )


def test_delete_comment(client, dbsession, comment):
    response = client.delete(f'{url}/{comment.uuid}')
    assert response.status_code == status.HTTP_200_OK
    response = client.get(f'{url}/{comment.uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
    random_uuid = uuid.uuid4()
    response = client.delete(f'{url}/{random_uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
    dbsession.refresh(comment)
    assert comment.is_deleted
    response = client.get(f'{url}/{comment.uuid}')
    assert response.status_code == status.HTTP_404_NOT_FOUND
