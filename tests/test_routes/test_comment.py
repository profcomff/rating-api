import datetime
import logging
import uuid

import pytest
from starlette import status

from rating_api.models import Comment, CommentReaction, LecturerUserComment, Reaction, ReviewStatus
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
                "text": "test text",
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
                "text": "test text",
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
                "text": "test text",
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
                "text": "test text",
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
                "text": "test text",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            3,
            status.HTTP_404_NOT_FOUND,
        ),
        (  # Anonymous comment
            {
                "subject": "test_subject",
                "text": "test text",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
                "is_anonymous": True,
            },
            0,
            status.HTTP_200_OK,
        ),
        (  # NotAnonymous comment
            {
                "subject": "test_subject",
                "text": "test text",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
                "is_anonymous": False,
            },
            0,
            status.HTTP_200_OK,
        ),
        (  # Not provided anonymity
            {
                "subject": "test_subject",
                "text": "test text",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_200_OK,
        ),
        (  # Bad anonymity
            {
                "subject": "test_subject",
                "text": "test text",
                "mark_kindness": 1,
                "mark_freebie": -2,
                "mark_clarity": 0,
                "is_anonymous": 'asd',
            },
            0,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (  # regex test
            {
                "subject": "test_subject",
                "text": """ABCDEFGHIJKLMNOPQRSTUVWXYZ
                        abcdefghijklmnopqrstuvwxyz.,!?-
                        абвгдежзийклмнопрстуфхцчшщъыьэюя1234567890
                        \"\'[]{}`~<>^@#№$%;:&*()+=\\/""",
                "mark_kindness": 1,
                "mark_freebie": 0,
                "mark_clarity": 0,
                "is_anonymous": False,
            },
            0,
            status.HTTP_200_OK,
        ),
        (  # forbidden symbols
            {
                "subject": "test_subject",
                "text": """ABCDEFGHIJKLMNOPQRSTUVWXYZ
                        abcdefghijklmnopqrstuvwxyz.,!?-
                        абвгдежзийк☻☺☺лмнопрстуфхцчшщъыьэюя1234567890""",
                "mark_kindness": 1,
                "mark_freebie": 0,
                "mark_clarity": 0,
                "is_anonymous": False,
            },
            0,
            status.HTTP_400_BAD_REQUEST,
        ),
        (  # long comment
            {
                "subject": "test_subject",
                "text": 'a' * 3001,
                "mark_kindness": 1,
                "mark_freebie": 0,
                "mark_clarity": 0,
                "is_anonymous": False,
            },
            0,
            status.HTTP_400_BAD_REQUEST,
        ),
        (  # long comment but not that long
            {
                "subject": "test_subject",
                "text": 'a' * 3000,
                "mark_kindness": 1,
                "mark_freebie": 0,
                "mark_clarity": 0,
                "is_anonymous": False,
            },
            0,
            status.HTTP_200_OK,
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


@pytest.mark.parametrize(
"reaction_data, expected_reaction, comment_user_id",
[
    (None, None, 0),
    ((0, Reaction.LIKE), "is_liked", 0), #my like on my comment
    ((0, Reaction.DISLIKE), "is_disliked", 0),
    ((999, Reaction.LIKE), None,  0), #someone else's like on my comment
    ((999, Reaction.DISLIKE), None, 0),
    ((0, Reaction.LIKE), "is_liked", 999), # my like on someone else's comment
    ((0, Reaction.DISLIKE), "is_disliked", 999),
    ((333, Reaction.LIKE), None, 999), # someone else's like on another person's comment
    ((333, Reaction.DISLIKE), None, 999),
    (None, None, None) #anonymous

],
)
def test_get_comment_with_reaction(client, dbsession, comment, reaction_data, expected_reaction, comment_user_id):
    comment.user_id = comment_user_id

    if reaction_data:
        user_id, reaction_type  = reaction_data
        reaction = CommentReaction(
            user_id = user_id,
            comment_uuid = comment.uuid,
            reaction = reaction_type
        )
        dbsession.add(reaction)

    dbsession.commit()

    response_comment = client.get(f'{url}/{comment.uuid}')

    if response_comment.status_code == status.HTTP_404_NOT_FOUND:
        return

    data = response_comment.json()
    if expected_reaction:
        assert data[expected_reaction]
    else:
        assert data["is_liked"] == False
        assert data["is_disliked"] == False



@pytest.fixture
def comments_with_likes(client, dbsession, lecturers):
    """
    Создает несколько комментариев с разным количеством лайков/дизлайков
    """
    comments = []

    user_id = 9999

    comment_data = [
        {
            "user_id": user_id,
            "lecturer_id": lecturers[0].id,
            "subject": "test_subject",
            "text": "Comment with many likes",
            "mark_kindness": 1,
            "mark_freebie": 0,
            "mark_clarity": 0,
            "review_status": ReviewStatus.APPROVED,
        },
        {
            "user_id": user_id,
            "lecturer_id": lecturers[0].id,
            "subject": "test_subject",
            "text": "Comment with many dislikes",
            "mark_kindness": 1,
            "mark_freebie": 0,
            "mark_clarity": 0,
            "review_status": ReviewStatus.APPROVED,
        },
        {
            "user_id": user_id,
            "lecturer_id": lecturers[0].id,
            "subject": "test_subject",
            "text": "Comment with balanced reactions",
            "mark_kindness": 1,
            "mark_freebie": 0,
            "mark_clarity": 0,
            "review_status": ReviewStatus.APPROVED,
        },
    ]

    for data in comment_data:
        comment = Comment(**data)
        dbsession.add(comment)
        comments.append(comment)

    dbsession.commit()

    for _ in range(10):
        reaction = CommentReaction(comment_uuid=comments[0].uuid, user_id=user_id, reaction=Reaction.LIKE)
        dbsession.add(reaction)
    for _ in range(2):
        reaction = CommentReaction(comment_uuid=comments[0].uuid, user_id=user_id, reaction=Reaction.DISLIKE)
        dbsession.add(reaction)

    for _ in range(3):
        reaction = CommentReaction(comment_uuid=comments[1].uuid, user_id=user_id, reaction=Reaction.LIKE)
        dbsession.add(reaction)
    for _ in range(8):
        reaction = CommentReaction(comment_uuid=comments[1].uuid, user_id=user_id, reaction=Reaction.DISLIKE)
        dbsession.add(reaction)

    for _ in range(5):
        reaction = CommentReaction(comment_uuid=comments[2].uuid, user_id=user_id, reaction=Reaction.LIKE)
        dbsession.add(reaction)
    for _ in range(5):
        reaction = CommentReaction(comment_uuid=comments[2].uuid, user_id=user_id, reaction=Reaction.DISLIKE)
        dbsession.add(reaction)

    dbsession.commit()

    for comment in comments:
        dbsession.refresh(comment)

    return comments


@pytest.mark.parametrize(
    'order_by, asc_order',
    [
        ('like_diff', False),
        ('like_diff', True),
    ],
)
def test_comments_sort_by_like_diff(client, comments_with_likes, order_by, asc_order):
    """
    Тестирует сортировку комментариев по разнице лайков (like_diff)
    """
    params = {"order_by": order_by, "asc_order": asc_order, "limit": 10}

    response = client.get('/comment', params=params)
    assert response.status_code == status.HTTP_200_OK

    json_response = response.json()
    returned_comments = json_response["comments"]

    if order_by == 'like_diff':
        if asc_order:
            for i in range(len(returned_comments) - 1):
                current_like_diff = returned_comments[i]["like_count"] - returned_comments[i]["dislike_count"]
                next_like_diff = returned_comments[i + 1]["like_count"] - returned_comments[i + 1]["dislike_count"]
                assert current_like_diff <= next_like_diff
        else:
            for i in range(len(returned_comments) - 1):
                current_like_diff = returned_comments[i]["like_count"] - returned_comments[i]["dislike_count"]
                next_like_diff = returned_comments[i + 1]["like_count"] - returned_comments[i + 1]["dislike_count"]
                assert current_like_diff >= next_like_diff


@pytest.mark.parametrize(
    'lecturer_n,response_status',
    [(0, status.HTTP_200_OK), (1, status.HTTP_200_OK), (2, status.HTTP_200_OK), (3, status.HTTP_404_NOT_FOUND)],
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
                for comment in comments
                if comment.lecturer_id == lecturers[lecturer_n].id
                and comment.review_status == ReviewStatus.APPROVED
                and not comment.is_deleted
            ]
        )


@pytest.mark.parametrize(
    'user_id,response_status', [(0, status.HTTP_200_OK), (1, status.HTTP_200_OK), (2, status.HTTP_200_OK)]
)
def test_comments_by_user_id(client, lecturers_with_comments, user_id, response_status):
    _, comments = lecturers_with_comments
    response = client.get(f'{url}', params={"user_id": 9990 + user_id})
    assert response.status_code == response_status
    if response.status_code == status.HTTP_200_OK:
        json_response = response.json()
        assert len(json_response["comments"]) == len(
            [
                comment
                for comment in comments
                if comment.user_id == 9990 + user_id
                and comment.review_status == ReviewStatus.APPROVED
                and not comment.is_deleted
            ]
        )


@pytest.mark.parametrize(
    'review_status, response_status, is_reviewed',
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
    commment_to_review = comment if is_reviewed else unreviewed_comment
    query = {"review_status": review_status}
    response = client.patch(f"{url}/{commment_to_review.uuid}/review", params=query)
    assert response.status_code == response_status
    if response.status_code == status.HTTP_200_OK:
        dbsession.refresh(commment_to_review)
        assert commment_to_review.review_status == ReviewStatus(review_status)


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
            status.HTTP_409_CONFLICT,
        ),
        (  # НЕизмененным передано одно поле
            {
                "subject": "asf",
                "text": "asf",
                "mark_kindness": 2,
                "mark_clarity": 2,
                "mark_freebie": 1,
            },
            status.HTTP_200_OK,
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
            assert getattr(nonanonymous_comment, k, None) == v  # Есть ли изменения в БД


# TODO: переписать под новую логику
# def test_delete_comment(client, dbsession, comment):
#     response = client.delete(f'{url}/{comment.uuid}')
#     assert response.status_code == status.HTTP_200_OK
#     response = client.get(f'{url}/{comment.uuid}')
#     assert response.status_code == status.HTTP_404_NOT_FOUND
#     random_uuid = uuid.uuid4()
#     response = client.delete(f'{url}/{random_uuid}')
#     assert response.status_code == status.HTTP_404_NOT_FOUND
#     dbsession.refresh(comment)
#     assert comment.is_deleted
#     response = client.get(f'{url}/{comment.uuid}')
#     assert response.status_code == status.HTTP_404_NOT_FOUND


def test_post_like(client, dbsession, comment):
    # Like
    response = client.put(f'{url}/{comment.uuid}/like')
    assert response.status_code == status.HTTP_200_OK
    dbsession.refresh(comment)
    assert comment.like_count == 1

    # Dislike
    response = client.put(f'{url}/{comment.uuid}/dislike')
    assert response.status_code == status.HTTP_200_OK
    dbsession.refresh(comment)
    assert comment.like_count == 0
    assert comment.dislike_count == 1

    # click dislike one more time
    response = client.put(f'{url}/{comment.uuid}/dislike')
    assert response.status_code == status.HTTP_200_OK
    dbsession.refresh(comment)
    assert comment.like_count == 0
    assert comment.dislike_count == 0
