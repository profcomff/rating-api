from rating_api.routes.models.lecturer import LecturerCommentPost, LecturerCommentPatch


def check_rating(comment: LecturerCommentPost | LecturerCommentPatch) -> bool:
    return (abs(comment.rate_general) > 2 or abs(comment.rate_kindness) > 5 or abs(comment.rate_understand) > 5 or abs(
        comment.rate_free) > 5)
