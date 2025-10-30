from typing import Any

from rating_api.settings import get_settings
from sqlalchemy import ColumnExpressionArgument, UnaryExpression

settings = get_settings()


def calc_weighted_mark(
    lecturer_mark_general: float | ColumnExpressionArgument[float],
    lecturer_comments_num: int | ColumnExpressionArgument[int],
    mean_mark_general: float,
) -> float | UnaryExpression[Any]:
    total_weight = lecturer_comments_num + settings.MEAN_MARK_GENERAL_WEIGHT
    mark_weighted = (
        lecturer_mark_general * lecturer_comments_num
        + mean_mark_general * settings.MEAN_MARK_GENERAL_WEIGHT
    ) / total_weight
    return mark_weighted
