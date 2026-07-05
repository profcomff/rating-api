import datetime
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette import status

from rating_api.models import Comment, CommentReaction, LecturerUserComment, Reaction, ReviewStatus
from rating_api.settings import get_settings


logger = logging.getLogger(__name__)
url: str = '/comment'

settings = get_settings()


def create_response_mock(status=status.HTTP_200_OK, payload=None):
    """Вспомогательная функция, создающая мок-объекты-ответы типа aiohttp.ClientResponse."""
    mock_post_response = AsyncMock()
    mock_post_response.status = status
    mock_post_response.json = AsyncMock(return_value=payload or {})
    return mock_post_response


def create_ae_context_manager(mock_response):
    """
    Вспомогательная функция, создающая мок-объекты имитируютщие асинхронный контекстный
    менеджер возвращающий мок-объекты-ответы типа aiohttp.ClientResponse
    (для подмены async with session.get(...) as response: ...).
    """
    ctx = AsyncMock()
    ctx.__aenter__.return_value = mock_response
    return ctx


def aiohttp_mock(authlib_user_id, aiohttp_response_status, achievement_id, get_url, post_url):
    """Функция создающая мок-объект сессию типа aiohttp.ClientSession. Реализует моки get- и post- методов данного объекта."""

    # url для проверки логики выдачи ачивок
    achive_get_url = get_url
    achive_post_url = post_url

    # coздаем моки ответов aiohttp get- и post- запросов
    mock_get_response = create_response_mock(
        status=aiohttp_response_status,
        payload={
            "user_id": authlib_user_id,
            "achievement": [
                {
                    "id": achievement_id,
                }
            ],
        },
    )
    mock_post_response = create_response_mock(payload={})
    get_responses = {achive_get_url: create_ae_context_manager(mock_get_response)}
    post_responses = {achive_post_url: mock_post_response}

    # функции для side_effect моков get- и post- aiohttp запросов, если запрос был к не тому url, мок всегда вернет 404(не используется для проверки)
    def get_side_effect(url, *args, **kwargs):
        return get_responses.get(url, create_ae_context_manager(create_response_mock(status=status.HTTP_404_NOT_FOUND)))

    def post_side_effect(url, *args, **kwargs):
        return post_responses.get(url, (create_response_mock(status=status.HTTP_404_NOT_FOUND)))

    # создаем мок сессии aiohttp.ClientSession
    mock_aiohttp_session = AsyncMock()
    # для мока session.get(...) используем MagicMock вместо AsyncMock, потому что это синхронный метод
    mock_aiohttp_session.get = MagicMock(side_effect=get_side_effect)
    mock_aiohttp_session.post.side_effect = post_side_effect
    mock_aiohttp_session.__aenter__.return_value = mock_aiohttp_session

    return mock_aiohttp_session


@pytest.mark.parametrize(
    'body,lecturer_n,response_status,aiohttp_response_status,achievement_id',
    [
        (  # тест логики выдачи ачивки за первый комментарий
            {
                "subject": "test_subject",
                "text": "test text",
                "mark_kindness": 1,
                "mark_freebie": 0,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_200_OK,
            status.HTTP_200_OK,
            0,
        ),
        (  # тест логики блокирующей выдачу ачивки за первый комментарий, если она уже есть у юзера
            {
                "subject": "test_subject",
                "text": "test text",
                "mark_kindness": 1,
                "mark_freebie": 0,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_200_OK,
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
        ),
        (  # тест логики выдачи ачивки в случае неудачного get-запроса к серверу
            {
                "subject": "test_subject",
                "text": "test text",
                "mark_kindness": 1,
                "mark_freebie": 0,
                "mark_clarity": 0,
            },
            0,
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            0,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
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
            status.HTTP_200_OK,
            settings.FIRST_COMMENT_ACHIEVEMENT_ID,
        ),
    ],
)
def test_create_comment(
    client,
    dbsession,
    lecturers,
    authlib_user,
    mocker,
    body,
    lecturer_n,
    response_status,
    aiohttp_response_status,
    achievement_id,
):
    # url для проверки логики выдачи ачивок
    achive_get_url = settings.API_URL + f"achievement/user/{authlib_user.get('id'):}"
    achive_post_url = (
        settings.API_URL
        + f"achievement/achievement/{settings.FIRST_COMMENT_ACHIEVEMENT_ID}/reciever/{authlib_user.get('id'):}"
    )

    # мок aiohttp get- и post- запросов связанных с выдачей ачивки
    mock_aiohttp_session = aiohttp_mock(
        authlib_user_id=authlib_user.get("id"),
        aiohttp_response_status=aiohttp_response_status,
        achievement_id=achievement_id,
        get_url=achive_get_url,
        post_url=achive_post_url,
    )

    mocker.patch("aiohttp.ClientSession", return_value=mock_aiohttp_session)

    params = {"lecturer_id": lecturers[lecturer_n].id}
    post_response = client.post(url, json=body, params=params)

    assert post_response.status_code == response_status

    if response_status == status.HTTP_200_OK:
        comment = Comment.query(session=dbsession).filter(Comment.uuid == post_response.json()["uuid"]).one_or_none()
        assert comment is not None
        assert comment.review_status is ReviewStatus.PENDING

        # проверка корректной записи user_id и fullname при анонимных и не анонимных комментариях
        if body.get("is_anonymous") is not False:
            assert comment.user_id is None
            assert comment.user_fullname is None
        else:
            assert comment.user_id == authlib_user.get("id")
            assert comment.user_fullname == authlib_user.get("userdata")[0]["value"]

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

        # Проверка логики ачивки
        check_get_response = mock_aiohttp_session.get
        check_post_response = mock_aiohttp_session.post

        if aiohttp_response_status == status.HTTP_200_OK:
            # Проверяем правильность заголовков и url get-запроса
            get_headers = {"Accept": "application/json"}
            try:
                check_get_response.assert_any_call(achive_get_url, headers=get_headers)
            except AssertionError as e:
                raise AssertionError(
                    f"Ожидался GET-запрос на {achive_get_url} c загловками {get_headers},"
                    f"но вызов, либо не состоялся, либо были переданы неверные заголовки."
                ) from e

            if achievement_id != settings.FIRST_COMMENT_ACHIEVEMENT_ID:
                # проверяем правильность заголовков и url post-запроса
                post_headers = {"Accept": "application/json", "Authorization": settings.ACHIEVEMENT_GIVE_TOKEN}
                try:
                    check_post_response.assert_any_await(achive_post_url, headers=post_headers)
                except AssertionError as e:
                    raise AssertionError(
                        f"Ожидался POST-запрос на {achive_post_url} c загловками {post_headers},"
                        f"но вызов, либо не состоялся, либо были переданы неверные заголовки."
                    )

            else:
                check_post_response.assert_not_awaited()
        else:
            check_post_response.assert_not_awaited()


@pytest.mark.parametrize(
    "body, total, response_status",
    [
        (
            {
                "comments": [
                    {
                        "subject": "string",
                        "text": "string",
                        "mark_kindness": 0,
                        "mark_freebie": 0,
                        "mark_clarity": 0,
                        "lecturer_id": 1,
                        "create_ts": "2026-05-25T11:41:26.777Z",
                        "update_ts": "2026-05-25T11:41:26.777Z",
                    },
                    {
                        "subject": "string",
                        "text": "string",
                        "mark_kindness": 0,
                        "mark_freebie": 0,
                        "mark_clarity": 0,
                        "lecturer_id": 2,
                        "create_ts": "2026-05-25T11:41:26.777Z",
                        "update_ts": "2026-05-25T11:41:26.777Z",
                    },
                ],
            },
            2,
            status.HTTP_200_OK,
        ),
        (
            {"comments": []},
            0,
            status.HTTP_200_OK,
        ),
        (
            {
                "comments": [
                    {
                        "subject": "string",
                        "text": "string",
                        "mark_kindness": 0,
                        "mark_freebie": 0,
                        "mark_clarity": 0,
                        "lecturer_id": 4,
                        "create_ts": "2026-05-25T11:41:26.777Z",
                        "update_ts": "2026-05-25T11:41:26.777Z",
                    },
                ],
            },
            1,
            status.HTTP_200_OK,
        ),
        (
            {
                "comments": [
                    {
                        "subdject": "string",
                        "text": "string",
                        "mark_kindness": 0,
                        "mark_freebie": 0,
                        "mark_clarity": 0,
                        "lecturer_id": "abc",
                    },
                ],
            },
            None,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    ],
)
def test_import_comments(client, dbsession, lecturers, body, total, response_status):
    response = client.post(f"{url}/import", json=body)

    assert response.status_code == response_status

    new_comments = response.json()
    print(new_comments)

    assert total == new_comments.get("total")

    if new_comments.get("total") and total > 0:
        for comment in new_comments.get("comments"):
            comment_from_db = Comment.query(session=dbsession).filter(Comment.uuid == comment.get("uuid")).one_or_none()
            assert comment_from_db is not None


@pytest.mark.parametrize(
    "reaction_data, expected_reaction, comment_user_id, response_status",
    [
        (None, None, 0, status.HTTP_200_OK),
        ((0, Reaction.LIKE), "is_liked", 0, status.HTTP_200_OK),  # my like on my comment
        ((0, Reaction.DISLIKE), "is_disliked", 0, status.HTTP_200_OK),
        ((999, Reaction.LIKE), None, 0, status.HTTP_200_OK),  # someone else's like on my comment
        ((999, Reaction.DISLIKE), None, 0, status.HTTP_200_OK),
        ((0, Reaction.LIKE), "is_liked", 999, status.HTTP_200_OK),  # my like on someone else's comment
        ((0, Reaction.DISLIKE), "is_disliked", 999, status.HTTP_200_OK),
        ((333, Reaction.LIKE), None, 999, status.HTTP_200_OK),  # someone else's like on another person's comment
        ((333, Reaction.DISLIKE), None, 999, status.HTTP_200_OK),
        (None, None, None, status.HTTP_200_OK),  # anonymous
    ],
)
def test_get_comment_with_reaction(
    client,
    comment,
    reaction_data,
    expected_reaction,
    comment_user_id,
    comment_reaction,
    response_status,
):
    comment.user_id = comment_user_id

    if reaction_data:
        user_id, reaction_type = reaction_data
        comment_reaction(user_id, reaction_type)

    response_comment = client.get(f'{url}/{comment.uuid}')

    assert response_comment.status_code == response_status

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
