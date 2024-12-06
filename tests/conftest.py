import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rating_api.models.db import *
from rating_api.routes import app
from rating_api.settings import Settings


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
    session = TestingSessionLocal()
    yield session


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


@pytest.fixture(scope='function')
def lecturers(dbsession):
    """
    Creates 4 lecturers(one with flag is_deleted=True)
    """
    lecturers_data = [
        ("test_fname1", "test_lname1", "test_mname1", 9900),
        ("test_fname2", "test_lname2", "test_mname2", 9901),
        ("Bibka", "Bobka", "Bobkovich", 9902),
    ]

    lecturers = [
        Lecturer(first_name=fname, last_name=lname, middle_name=mname, timetable_id=timetable_id)
        for fname, lname, mname, timetable_id in lecturers_data
    ]
    lecturers.append(
        Lecturer(first_name='test_fname3', last_name='test_lname3', middle_name='test_mname3', timetable_id=3)
    )
    lecturers[-1].is_deleted = True
    for lecturer in lecturers:
        dbsession.add(lecturer)
    dbsession.commit()
    yield lecturers
    for lecturer in lecturers:
        dbsession.refresh(lecturer)
        for row in lecturer.comments:
            dbsession.delete(row)
        lecturer_user_comments = dbsession.query(LecturerUserComment).filter(
            LecturerUserComment.lecturer_id == lecturer.id
        )
        for row in lecturer_user_comments:
            dbsession.delete(row)
        dbsession.delete(lecturer)
    dbsession.commit()


@pytest.fixture
def lecturers_with_comments(dbsession, lecturers):
    """
    Creates 4 lecturers(one with flag is_deleted=True)
      with 6 comments to non-deleted lecturers 4 approved and one dismissed and one pending.
        Two of them have alike names.
        Two of them have a different user_id.
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
        (lecturers[2].id, 9992, 'test_subject12', ReviewStatus.APPROVED, 0, 0, 0),
    ]

    comments = [
        Comment(
            subject=subject,
            text="test_comment",
            mark_kindness=mark_kindness,
            mark_clarity=mark_clarity,
            mark_freebie=mark_freebie,
            lecturer_id=lecturer_id,
            user_id=user_id,
            review_status=review_status,
        )
        for lecturer_id, user_id, subject, review_status, mark_kindness, mark_clarity, mark_freebie in comments_data
    ]

    dbsession.add_all(comments)
    dbsession.commit()
    yield lecturers, comments
    for comment in comments:
        dbsession.refresh(comment)
        dbsession.delete(comment)
    dbsession.commit()
