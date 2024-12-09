import datetime
import logging
import uuid

import pytest
from starlette import status

from rating_api.models import Comment, LecturerUserComment, ReviewStatus
from rating_api.settings import get_settings


logger = logging.getLogger(__name__)
url: str = '/comment'

settings = get_settings()


@pytest.mark.parametrize(
    'body,lecturer_n,response_status',
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
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            3,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            {
                "subject": "test_subject",
                "text": "test_text",
                "create_ts": "2077-11-16T19:15:27.306Z",
                "update_ts": "2077-11-16T19:15:27.306Z",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_200_OK,
        ),
        (  # Anonymous comment
            {
                "subject": "test_subject",
                "text": "test_text",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
                "is_anonymous": True,
            },
            0,
            status.HTTP_200_OK,
        ),
        (
            {
                "subject": "test_subject",
                "text": "test_text",
                "update_ts": "2077-11-16T19:15:27.306Z",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_200_OK,
        ),
        (  # NotAnonymous comment
            {
                "subject": "test_subject",
                "text": "test_text",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
                "is_anonymous": False,
            },
            0,
            status.HTTP_200_OK,
        ),
        (
            {
                "subject": "test_subject",
                "text": "test_text",
                "create_ts": "2077-11-16T19:15:27.306Z",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_200_OK,
        ),
        (  # wrong date
            {
                "subject": "test_subject",
                "text": "test_text",
                "create_ts": "wasd",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (  # Bad anonymity
            {
                "subject": "test_subject",
                "text": "test_text",
                "create_ts": "wasd",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (  # Not provided anonymity
            {
                "subject": "test_subject",
                "text": "test_text",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
                "is_anonymous": 'asd',
            },
            0,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    ],
)
def test_create_comment(client, dbsession, lecturers, body, lecturer_n, response_status):
    params = {"lecturer_id": lecturers[lecturer_n].id}
    post_response = client.post(url, json=body, params=params)
    assert post_response.status_code == response_status
    if response_status == status.HTTP_200_OK:
        comment = Comment.query(session=dbsession).filter(Comment.uuid == post_response.json()["uuid"]).one_or_none()
        assert comment is not None

        if "create_ts" in body:
            assert comment.create_ts == datetime.datetime.fromisoformat(body["create_ts"]).replace(tzinfo=None)
        if "update_ts" in body:
            assert comment.update_ts == datetime.datetime.fromisoformat(body["update_ts"]).replace(tzinfo=None)

        user_comment = (
            LecturerUserComment.query(session=dbsession)
            .filter(LecturerUserComment.lecturer_id == lecturers[lecturer_n].id)
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
    'lecturer_n,response_status', [(0, status.HTTP_200_OK), (1, status.HTTP_200_OK), (3, status.HTTP_200_OK)]
)
def test_comments_by_lecturer_id(client, lecturers_with_comments, lecturer_n, response_status):
    lecturers, comments = lecturers_with_comments
    response = client.get(f'{url}', params={"lecturer_id": lecturers[lecturer_n].id})
    assert response.status_code == response_status
    if response.status_code == status.HTTP_200_OK:
        json_response = response.json()
        assert len(json_response["comments"]) == len(
            [
                comment
                for comment in lecturers[lecturer_n].comments
                if comment.review_status == ReviewStatus.APPROVED and not comment.is_deleted
            ]
        )


@pytest.mark.parametrize(
    'user_id,response_status', [(0, status.HTTP_200_OK), (1, status.HTTP_200_OK), (2, status.HTTP_200_OK)]
)
def test_comments_by_user_id(client, lecturers_with_comments, user_id, response_status):
    _, comments = lecturers_with_comments
    response = response = client.get(f'{url}', params={"user_id": user_id})
    assert response.status_code == response_status
    if response.status_code == status.HTTP_200_OK:
        json_response = response.json()
        assert len(json_response["comments"]) == len(
            [
                comment
                for comment in comments
                if comment.user_id == user_id
                and comment.review_status == ReviewStatus.APPROVED
                and not comment.is_deleted
            ]
        )


@pytest.mark.parametrize(
    'review_status, response_status,is_reviewed',
    [
        ("approved", status.HTTP_200_OK, True),
        ("approved", status.HTTP_200_OK, False),
        ("dismissed", status.HTTP_200_OK, True),
        ("dismissed", status.HTTP_200_OK, False),
        ("wrong_status", status.HTTP_422_UNPROCESSABLE_ENTITY, True),
        ("wrong_status", status.HTTP_422_UNPROCESSABLE_ENTITY, False),
    ],
)
def test_review_comment(client, dbsession, unreviewed_comment, comment, review_status, response_status, is_reviewed):
    commment_to_reivew = comment if is_reviewed else unreviewed_comment
    query = {"review_status": review_status}
    response = client.patch(f"{url}/{commment_to_reivew.uuid}/review", params=query)
    assert response.status_code == response_status
    if response.status_code == status.HTTP_200_OK:
        dbsession.refresh(commment_to_reivew)
        assert commment_to_reivew.review_status == ReviewStatus(review_status)


@pytest.mark.parametrize(
    'body, response_status',
    [
        (
            {
                "subject": "test_subject",
                "text": "test_text",
                "mark_kindness": 0,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            status.HTTP_200_OK,
        ),
        (
            {
                "subject": 0,
                "text": "test_text",
                "mark_kindness": 0,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (  # Отсутсвует одно поле
            {
                "subject": "test_subject",
                "mark_kindness": 0,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            status.HTTP_200_OK,
        ),
        (
            {
                "subject": "test_subject",
                "text": "test_text",
                "mark_kindness": 5,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            status.HTTP_400_BAD_REQUEST,
        ),
        (  # Отсутсвует все поля
            {},
            status.HTTP_409_CONFLICT,
        ),
        (  # Переданы НЕизмененные поля
            {
                "subject": "subject",
                "text": "comment",
                "mark_kindness": 1,
                "mark_clarity": 1,
                "mark_freebie": 1,
            },
            status.HTTP_426_UPGRADE_REQUIRED,
        ),
        (  # НЕизмененным перелано одно поле
            {
                "subject": "asf",
                "text": "asf",
                "mark_kindness": 2,
                "mark_clarity": 2,
                "mark_freebie": 1,
            },
            status.HTTP_426_UPGRADE_REQUIRED,
        ),
    ],
)
def test_update_comment(client, dbsession, nonanonymous_comment, body, response_status):
    response = client.patch(f"{url}/{nonanonymous_comment.uuid}", json=body)
    assert response.status_code == response_status
    if response.status_code == status.HTTP_200_OK:
        dbsession.refresh(nonanonymous_comment)
        assert nonanonymous_comment.review_status == ReviewStatus.PENDING
        for k, v in body.items():
            getattr(nonanonymous_comment, k, None) == v  # Есть ли изменения в БД


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
