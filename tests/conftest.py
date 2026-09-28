import importlib
import sys
import uuid
from functools import lru_cache
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from rating_api.models.db import *
from rating_api.routes import app
from rating_api.settings import Settings, get_settings


class PostgresConfig:
    """Дата-класс со значениями для контейнера с тестовой БД и alembic-миграции."""

    container_name: str = 'rating_test'
    username: str = 'postgres'
    host: str = 'localhost'
    image: str = 'postgres:15'
    external_port: int = 5433
    ham: str = 'trust'
    alembic_ini: str = Path(__file__).resolve().parent.parent / 'alembic.ini'

    @classmethod
    def get_url(cls):
        """Возвращает URI для подключения к БД."""
        return f'postgresql://{cls.username}@{cls.host}:{cls.external_port}/postgres'


@pytest.fixture(scope="session")
def session_mp():
    """Аналог monkeypatch, но с session-scope."""
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope='session')
def get_settings_mock(session_mp):
    """Переопределение get_settings в rating_api/settings.py и перезагрузка base.app."""

    @lru_cache
    def get_test_settings() -> Settings:
        settings = Settings()
        settings.DB_DSN = PostgresConfig.get_url()
        return settings

    get_settings.cache_clear()
    dsn_mock = session_mp.setattr('rating_api.settings.get_settings', get_test_settings)
    reloaded_module = sys.modules['rating_api.routes.base']
    importlib.reload(reloaded_module)
    importlib.reload(sys.modules['rating_api.routes.exc_handlers'])
    globals()['app'] = reloaded_module.app
    return dsn_mock


@pytest.fixture(scope="session")
def db_container(get_settings_mock):
    """Фикстура настройки БД для тестов в Docker-контейнере."""
    container = (
        PostgresContainer(
            image=PostgresConfig.image, username=PostgresConfig.username, dbname=PostgresConfig.container_name
        )
        .with_bind_ports(5432, PostgresConfig.external_port)
        .with_env("POSTGRES_HOST_AUTH_METHOD", PostgresConfig.ham)
    )
    container.start()
    cfg = AlembicConfig(str(PostgresConfig.alembic_ini.resolve()))
    cfg.set_main_option("script_location", "%(here)s/migrations")
    command.upgrade(cfg, "head")
    try:
        yield PostgresConfig.get_url()
    finally:
        container.stop()


@pytest.fixture()
def dbsession(db_container):
    """Фикстура настройки Session для работы с БД в тестах."""
    engine = create_engine(str(db_container), pool_pre_ping=True)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    yield session


@pytest.fixture
def authlib_user():
    """
    Данные о пользователе, возвращаемые сервисом auth.
    """
    return {
        "session_scopes": [{"id": 0, "name": "string", "comment": "string"}],
        "user_scopes": [{"id": 0, "name": "string", "comment": "string"}],
        "indirect_groups": [{"id": 0, "name": "string", "parent_id": 0}],
        "groups": [{"id": 0, "name": "string", "parent_id": 0}],
        "id": 0,
        "email": "string",
        "userdata": [
            {"category": "Личная информация", "param": "Полное имя", "value": "Тестовый Тест"},
        ],
    }


@pytest.fixture()
def authlib_mock(mocker):
    auth_mock = mocker.patch("auth_lib.fastapi.UnionAuth.__call__", autospec=True)
    return auth_mock


@pytest.fixture()
def user_mock(authlib_mock, authlib_user):
    authlib_mock.return_value = authlib_user
    return authlib_mock


@pytest.fixture
def client(mocker, user_mock):
    client = TestClient(app)
    return client


@pytest.fixture
def lecturer(dbsession):
    _lecturer = Lecturer(first_name="test_fname", last_name="test_lname", middle_name="test_mname", timetable_id=9900)
    dbsession.add(_lecturer)
    dbsession.commit()
    yield _lecturer
    dbsession.refresh(_lecturer)
    dbsession.delete(_lecturer)
    dbsession.commit()


@pytest.fixture
def comment(dbsession, lecturer):
    _comment = Comment(
        uuid=uuid.uuid4(),
        user_id=0,
        create_ts="2025-04-25T19:38:56.408Z",
        subject="test_subject",
        text="test_comment",
        mark_kindness=1,
        mark_clarity=1,
        mark_freebie=1,
        lecturer_id=lecturer.id,
        review_status=ReviewStatus.APPROVED,
    )
    dbsession.add(_comment)
    dbsession.commit()
    yield _comment
    dbsession.refresh(_comment)
    dbsession.delete(_comment)
    dbsession.commit()


@pytest.fixture
def comment_reaction(dbsession, comment):
    created_reactions = []

    def _create_reaction(user_id: int, react: Reaction):
        reaction = CommentReaction(user_id=user_id, comment_uuid=comment.uuid, reaction=react)
        dbsession.add(reaction)
        dbsession.commit()
        created_reactions.append(reaction)

    yield _create_reaction

    for reaction in created_reactions:
        dbsession.delete(reaction)
    dbsession.commit()


@pytest.fixture
def unreviewed_comment(dbsession, lecturer):
    _comment = Comment(
        subject="test_subject",
        text="test_comment",
        mark_kindness=1,
        mark_clarity=1,
        mark_freebie=1,
        lecturer_id=lecturer.id,
        review_status=ReviewStatus.PENDING,
    )
    dbsession.add(_comment)
    dbsession.commit()
    yield _comment
    dbsession.refresh(_comment)
    dbsession.delete(_comment)
    dbsession.commit()


@pytest.fixture
def nonanonymous_comment(dbsession, lecturer):
    _comment = Comment(
        subject="subject",
        text="comment",
        mark_kindness=1,
        mark_clarity=1,
        mark_freebie=1,
        lecturer_id=lecturer.id,
        review_status=ReviewStatus.APPROVED,
        user_id=0,
    )
    dbsession.add(_comment)
    dbsession.commit()
    yield _comment
    dbsession.refresh(_comment)
    dbsession.delete(_comment)
    dbsession.commit()


@pytest.fixture
def lecturers(dbsession, lecturer_factory):
    """
    Создает 4 лекторов через фабрику (один с флагом is_deleted=True)
    """
    created_lecturers = lecturer_factory(4)

    deleted_lecturer = created_lecturers[3]
    deleted_lecturer.is_deleted = True
    dbsession.commit()

    yield created_lecturers

    lecturer_ids = [l.id for l in created_lecturers]
    
    dbsession.query(Comment).filter(Comment.lecturer_id.in_(lecturer_ids)).delete(
        synchronize_session=False
    )
    dbsession.query(LecturerUserComment).filter(
        LecturerUserComment.lecturer_id.in_(lecturer_ids)
    ).delete(synchronize_session=False)

    dbsession.query(Lecturer).filter(Lecturer.id.in_(lecturer_ids)).delete(
        synchronize_session=False
    )
    dbsession.commit()

@pytest.fixture
def lecturers_with_comments(dbsession, lecturers):
    """
    Creates 4 lecturers(one with flag is_deleted=True)
      with 6 comments to non-deleted lecturers 4 approved and one dismissed and one pending.
        Two of them have alike names.
        Two of them have a different user_id.
        One of them have a different subject.
    """
    comments_data = [
        (lecturers[0].id, 9990, 'test_subject', ReviewStatus.APPROVED, 1, 1, 1),
        (lecturers[0].id, None, 'test_subject1', ReviewStatus.APPROVED, 2, 2, 2),
        (lecturers[0].id, 9990, 'test_subject2', ReviewStatus.DISMISSED, -1, -1, -1),
        (lecturers[0].id, 9990, 'test_subject2', ReviewStatus.PENDING, -2, -2, -2),
        (lecturers[0].id, 9991, 'test_subject11', ReviewStatus.APPROVED, 1, 1, 1),
        (lecturers[0].id, 9992, 'test_subject12', ReviewStatus.APPROVED, 2, 2, 2),
        (lecturers[1].id, 9990, 'test_subject', ReviewStatus.APPROVED, 1, 1, 1),
        (lecturers[1].id, None, 'test_subject1', ReviewStatus.APPROVED, -1, -1, -1),
        (lecturers[1].id, 9990, 'test_subject2', ReviewStatus.DISMISSED, -2, -2, -2),
        (lecturers[1].id, 9990, 'test_subject2', ReviewStatus.PENDING, -2, -2, -2),
        (lecturers[1].id, 9991, 'test_subject11', ReviewStatus.APPROVED, 1, 1, 1),
        (lecturers[1].id, 9992, 'test_subject12', ReviewStatus.APPROVED, -1, -1, -1),
        (lecturers[2].id, 9990, 'test_subject', ReviewStatus.APPROVED, 1, 1, 1),
        (lecturers[2].id, None, 'test_subject1', ReviewStatus.APPROVED, 0, 0, 0),
        (lecturers[2].id, 9990, 'test_subject2', ReviewStatus.DISMISSED, 2, 2, 2),
        (lecturers[2].id, 9990, 'test_subject2', ReviewStatus.PENDING, -2, -2, -2),
        (lecturers[2].id, 9991, 'test_subject11', ReviewStatus.APPROVED, 1, 1, 1),
        (lecturers[2].id, 9992, 'test_subject13', ReviewStatus.APPROVED, 0, 0, 0),
    ]

    comments = []
    for lecturer_id, user_id, subject, review_status, mark_kindness, mark_clarity, mark_freebie in comments_data:
        comment = Comment(
            subject=subject,
            text="test_comment",
            mark_kindness=mark_kindness,
            mark_clarity=mark_clarity,
            mark_freebie=mark_freebie,
            lecturer_id=lecturer_id,
            user_id=user_id,
            review_status=review_status,
        )

        # Set approved_by to -1 for approved or dismissed comments
        if review_status in [ReviewStatus.APPROVED, ReviewStatus.DISMISSED]:
            comment.approved_by = -1

        comments.append(comment)

    dbsession.add_all(comments)
    dbsession.commit()
    yield lecturers, comments
    for comment in comments:
        dbsession.refresh(comment)
        dbsession.delete(comment)
    dbsession.commit()


@pytest.fixture
def lecturer_factory(dbsession):
    """
    Создает лекторов
    """
    created = []

    def create_lecturers(count: int=1) -> list[Lecturer]:
        lecturers = []
        for i in range(count):
            cur_id = len(created)+1  
            lecturer = Lecturer(
                first_name=f"fname_{cur_id}",
                last_name=f"lname_{cur_id}",
                middle_name=f"mname_{cur_id}",
                timetable_id=i+1,
            )
            lecturers.append(lecturer)
            created.append(lecturer)

        dbsession.add_all(lecturers)
        dbsession.commit()
        return lecturers

    yield create_lecturers

    for l in created:
        if dbsession.is_active and l in dbsession:
            dbsession.delete(l)
    try:
        dbsession.commit()
    except Exception:
        dbsession.rollback()


@pytest.fixture
def comment_factory(dbsession, authlib_user):
    """
    Создает комментарии
    """
    user_id = authlib_user.get("id")
    created_comment_uuids = []
    created_user_comment_ids = []

    def create_comments(lecturer_id: int, count: int):
        for _ in range(count):
            comment = Comment(
                user_id=user_id,
                lecturer_id=lecturer_id,
                subject="Subject",
                text="Text",
                mark_kindness=1,
                mark_freebie=0,
                mark_clarity=0,
                review_status=ReviewStatus.PENDING,
            )
            dbsession.add(comment)
            dbsession.flush()
            created_comment_uuids.append(comment.uuid)

            user_comment = LecturerUserComment(lecturer_id=lecturer_id, user_id=user_id)
            dbsession.add(user_comment)
            dbsession.flush()
            created_user_comment_ids.append(user_comment.id)

        dbsession.commit()

    yield create_comments

    if created_user_comment_ids:
        dbsession.query(LecturerUserComment).filter(LecturerUserComment.id.in_(created_user_comment_ids)).delete(
            synchronize_session=False
        )

    if created_comment_uuids:
        dbsession.query(Comment).filter(Comment.uuid.in_(created_comment_uuids)).delete(synchronize_session=False)

    dbsession.commit()