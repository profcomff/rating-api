import datetime

from models.db import LecturerRating
from models.dwh import DWHLecturer
from settings import get_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rating_api.exceptions import ObjectNotFound


settings = get_settings()

engine = create_engine(settings.DWH_DB_DSN)


def copy_from_dwh(api_session):
    with Session(engine) as dwh_session:
        lecturers = DWHLecturer.get_all(session=dwh_session)
        for lecturer in lecturers:
            fields = {
                "id": lecturer.api_id,
                "mark_weighted": lecturer.mark_weighted,
                "mark_kindness_weighted": lecturer.mark_kindness_weighted,
                "mark_clarity_weighted": lecturer.mark_clarity_weighted,
                "mark_freebie_weighted": lecturer.mark_freebie_weighted,
                "rank": lecturer.rank,
                "update_ts": datetime.datetime.now(datetime.timezone.utc),
            }

            if LecturerRating.get(fields["id"], session=api_session):
                LecturerRating.update(fields["id"], session=api_session, **fields)
