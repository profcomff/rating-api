from __future__ import annotations

import re

from sqlalchemy import not_
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Query, Session, as_declarative, declared_attr

from rating_api.exceptions import ObjectNotFound, UpdateError


@as_declarative()
class Base:
    """Base class for all database entities"""

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


class BaseDbModel(Base):
    __abstract__ = True

    @classmethod
    def create(cls, *, session: Session, **kwargs) -> BaseDbModel:
        obj = cls(**kwargs)
        session.add(obj)
        session.flush()
        return obj

    @classmethod
    def query(cls, *, with_deleted: bool = False, session: Session) -> Query:
        """Get all objects with soft deletes"""
        objs = session.query(cls)
        if not with_deleted and hasattr(cls, "is_deleted"):
            objs = objs.filter(not_(cls.is_deleted))
        return objs

    @classmethod
    def get(cls, id: int | str, *, with_deleted=False, session: Session) -> BaseDbModel:
        """Get object with soft deletes"""
        objs = session.query(cls)
        if not with_deleted and hasattr(cls, "is_deleted"):
            objs = objs.filter(not_(cls.is_deleted))
        try:
            if hasattr(cls, "uuid"):
                return objs.filter(cls.uuid == id).one()
            return objs.filter(cls.id == id).one()
        except NoResultFound:
            raise ObjectNotFound(cls, id)

    @classmethod
    def update(cls, id: int | str, *, session: Session, **kwargs) -> BaseDbModel:
        obj = cls.get(id, session=session)

        # Технические поля не проверяются при update комментария
        technical_fields = {'update_ts', 'review_status'}

        # Проверка на изменение полей
        changed_fields = False
        for field, new_value in kwargs.items():

            old_value = getattr(obj, field)
            if old_value != new_value and not field in technical_fields:
                changed_fields = True
                break

        if not changed_fields:
            raise UpdateError(msg=f"No changes detected in fields")
            # raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No changes detected in fields")

        for k, v in kwargs.items():
            setattr(obj, k, v)

        session.flush()
        return obj

    @classmethod
    def delete(cls, id: int | str, *, session: Session) -> None:
        """Soft delete object if possible, else hard delete"""
        obj = cls.get(id, session=session)
        if hasattr(obj, "is_deleted"):
            obj.is_deleted = True
        else:
            session.delete(obj)
        session.flush()
