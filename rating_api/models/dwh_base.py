import re

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Query, Session, as_declarative, declared_attr

from rating_api.exceptions import ObjectNotFound, ValidObjectNotFound


as_declarative()


class DWHBase:
    """Base class for all dwh entities"""

    @declared_attr
    def __tablename__(cls) -> str:  # pylint: disable=no-self-argument
        """Generate database table name automatically.
        Convert CamelCase class name to snake_case db table name.
        """
        return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()

    def __repr__(self):
        attrs = []
        for c in self.__table__.columns:
            attrs.append(f"{c.name}={getattr(self, c.name)}")
        return "{}({})".format(c.__class__.__name__, ', '.join(attrs))


class DWHBaseDbModel(DWHBase):
    __abstract__ = True

    @classmethod
    def get(cls, id: int | str, *, session: Session) -> DWHBaseDbModel:
        """Get valid object"""

        objs = session.query(cls)
        try:
            if hasattr(cls, "valid_to_dt"):
                objs = objs.filter(cls.valid_to_dt.is_(None))
        except NoResultFound:
            raise ValidObjectNotFound(cls, id)
        try:
            if hasattr(cls, "api_id"):
                return objs.filter(cls.api_id == id).one()
        except NoResultFound:
            raise ObjectNotFound(cls, id)

    @classmethod
    def get_all(cls, *, session: Session) -> [DWHBaseDbModel]:
        "Get all valid objects"
        objs = session.query(cls)
        try:
            if hasattr(cls, "valid_to_dt"):
                objs = objs.filter(cls.valid_to_dt.is_(None))
        except NoResultFound:
            raise ValidObjectNotFound(cls, id)
