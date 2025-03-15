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



class ObjectFound(RatingAPIError):
    def __init__(self, obj: type, obj_id_or_name: int | str):
        super().__init__(
            f"Object {obj.__name__} {obj_id_or_name=} not found",
            f"Объект {obj.__name__}  с идентификатором {obj_id_or_name} не найден",
        )



class ObjectNotFound2(RatingAPIError):
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
    frequency: int
    limit: int

    def __init__(self, frequency: int, limit: int):
        self.frequency = frequency
        self.limit = limit
        super().__init__(
            f'Too many comment requests. Allowed: {limit} comments per {frequency} months.',
            f'Слишком много попыток оставить комментарий. Разрешено: {limit} комментариев за {frequency} месяцев.',
        )


class TooManyCommentsToLecturer(RatingAPIError):
    frequency: int
    limit: int

    def __init__(self, frequency: int, limit: int):
        self.frequency = frequency
        self.limit = limit
        super().__init__(
            f"Too many comments to lecturer. Allowed: {limit} comments per {frequency} months.",
            f"Превышен лимит комментариев лектору. Разрешено: {limit} комментариев за {frequency} месяцев.",
        )


class ForbiddenAction(RatingAPIError):
    def __init__(self, type: Type):
        super().__init__(f"Forbidden action with {type.__name__}", f"Запрещенное действие с объектом {type.__name__}")


class WrongMark(RatingAPIError):
    def __init__(self):
        super().__init__(
            f"Ratings can only take values: -2, -1, 0, 1, 2", f"Оценки могут принимать только значения: -2, -1, 0, 1, 2"
        )


class CommentTooLong(RatingAPIError):
    def __init__(self, num_symbols: int):
        super().__init__(
            f"The comment is too long. Maximum of {num_symbols} is allowed",
            f"Комментарий слишком длинный. Разрешено максимум {num_symbols}",
        )


class ForbiddenSymbol(RatingAPIError):
    def __init__(self):
        super().__init__(
            f"The comment contains forbidden symbols. Letters of English and Russian languages, numbers and punctuation marks are allowed",
            f"Комментарий содержит запрещенный символ. Разрешены буквы английского и русского языков, цифры и знаки препинания",
        )


class UpdateError(RatingAPIError):
    def __init__(self, msg: str):
        super().__init__(
            f"{msg} Conflict with update a resource that already exists or has conflicting information.",
            f"{msg} Конфликт с обновлением ресурса, который уже существует или имеет противоречивую информацию.",
        )
