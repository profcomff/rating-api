import datetime
from typing import Type


class RatingAPIError(Exception):
    eng: str
    ru: str

    def __init__(self, eng: str, ru: str) -> None:
        self.eng = eng
        self.ru = ru
        super().__init__(eng)


class ObjectNotFound(RatingAPIError):
    def __init__(self, obj: type, obj_id_or_name: int | str):
        super().__init__(
            f"Object {obj.__name__} {obj_id_or_name=} not found",
            f"Объект {obj.__name__}  с идентификатором {obj_id_or_name} не найден",
        )


class AlreadyExists(RatingAPIError):
    def __init__(self, obj: type, obj_id_or_name: int | str):
        super().__init__(
            f"Object {obj.__name__}, {obj_id_or_name=} already exists",
            f"Объект {obj.__name__} с идентификатором {obj_id_or_name=} уже существует",
        )


class TooManyCommentRequests(RatingAPIError):
    delay_time: datetime.timedelta

    def __init__(self, dtime: datetime.timedelta):
        self.delay_time = dtime
        super().__init__(
            f'Too many comment requests. Delay: {dtime}',
            f'Слишком много попыток оставить комментарий. Задержка: {dtime}',
        )


class ForbiddenAction(RatingAPIError):
    def __init__(self, type: Type):
        super().__init__(f"Forbidden action with {type.__name__}", f"Запрещенное действие с объектом {type.__name__}")
