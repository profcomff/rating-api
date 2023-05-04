from sqlalchemy.orm import Session
from rating_api.models.db import LecturerComment as DbCommentLecturer


def get_general_rating(lecturer_id: int, dbsession: Session) -> int:
    rate = dbsession.query(DbCommentLecturer.rate_general).filter(DbCommentLecturer.lecturer_id == lecturer_id).all()
    return sum(rate)
