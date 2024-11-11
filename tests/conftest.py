import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from rating_api.models.db import *
from rating_api.routes import app
from rating_api.settings import Settings
from rating_api.utils.utils import random_string, random_mark


@pytest.fixture
def client(mocker):
    user_mock = mocker.patch('auth_lib.fastapi.UnionAuth.__call__')
    user_mock.return_value = {
        "session_scopes": [{"id": 0, "name": "string", "comment": "string"}],
        "user_scopes": [{"id": 0, "name": "string", "comment": "string"}],
        "indirect_groups": [{"id": 0, "name": "string", "parent_id": 0}],
        "groups": [{"id": 0, "name": "string", "parent_id": 0}],
        "id": 0,
        "email": "string",
    }
    client = TestClient(app)
    return client


@pytest.fixture
def dbsession() -> Session:
    settings = Settings()
    engine = create_engine(str(settings.DB_DSN), pool_pre_ping=True)
    TestingSessionLocal = sessionmaker(bind=engine)
    yield TestingSessionLocal()


@pytest.fixture
def lecturer(dbsession):
    """
    Вызов фабрики создает препода и возвращает его
    ```
    def test(lecturer):
        lecturer1 = lecturer()
        lecturer2 = lecturer()
    ```
    """
    lecturers = []

    def _lecturer(first_name: str | None = None, last_name: str | None = None, middle_name: str | None = None):
        nonlocal lecturers
        first_name = f"test_fname{random_string()}" if first_name is None else first_name
        last_name = f"test_lname{random_string()}" if last_name is None else last_name
        middle_name = f"test_mname{random_string()}" if middle_name is None else middle_name
        __lecturer = Lecturer(
            first_name=first_name, last_name=last_name, middle_name=middle_name, timetable_id=len(lecturers)
        )
        dbsession.add(__lecturer)
        dbsession.commit()
        lecturers.append(__lecturer)
        return __lecturer

    yield _lecturer
    dbsession.expire_all()
    dbsession.commit()
    for row in lecturers:
        dbsession.delete(row)
    dbsession.commit()


@pytest.fixture
def comment(dbsession, lecturer):
    """ "
    Вызов фабрики создает комментарий к преподавателю и возвращает его
    ```
    def test(comment):
        comment1 = comment()
        comment2 = comment()
    ```
    """
    comments = []

    def _comment(
        lecturer_id: int | None = None,
        user_id: int | None = None,
        review_status: ReviewStatus = ReviewStatus.APPROVED,
        subject: str | None = None,
    ):
        nonlocal comments
        text = random_string()
        subject = random_string() if subject is None else subject
        mark_kindness = random_mark()
        mark_freebie = random_mark()
        mark_clarity = random_mark()
        if lecturer_id is None:
            lecturer = lecturer()
            lecturer_id = lecturer.id
        __comment = Comment(
            subject=subject,
            text=text,
            mark_kindness=mark_kindness,
            mark_clarity=mark_clarity,
            mark_freebie=mark_freebie,
            lecturer_id=lecturer_id,
            user_id=user_id,
            review_status=review_status,
        )
        dbsession.add(__comment)
        dbsession.commit()
        comments.append(__comment)
        return __comment

    yield _comment
    dbsession.expire_all()
    dbsession.commit()
    for row in comments:
        dbsession.delete(row)
    dbsession.commit()
