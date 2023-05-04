from pydantic import BaseModel
import datetime


class Base(BaseModel):
    def __repr__(self) -> str:
        attrs = []
        for k, v in self.__class__.schema().items():
            attrs.append(f"{k}={v}")
        return "{}({})".format(self.__class__.__name__, ', '.join(attrs))

    class Config:
        orm_mode = True


class StatusResponseModel(Base):
    status: str
    message: str


class CommentLecturer(Base):
    id: int
    lecturer_id: int
    text: str
    rate_general: int
    rate_kindness: int
    rate_free: int
    rate_understand: int
    author_name: str
    create_ts: datetime.datetime
    update_ts: datetime.datetime
    approve_author_id: int | None
    approve_time: datetime.datetime | None

