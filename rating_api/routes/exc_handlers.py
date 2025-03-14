import starlette.requests
from starlette.responses import JSONResponse

from rating_api.exceptions import (
    AlreadyExists,
    CommentTooLong,
    ForbiddenAction,
    ForbiddenSymbol,
    ObjectNotFound,
    TooManyCommentRequests,
    TooManyCommentsToLecturer,
    UpdateError,
    WrongMark,
)
from rating_api.schemas.base import StatusResponseModel

from .base import app


@app.exception_handler(AlreadyExists)
async def already_exists_handler(req: starlette.requests.Request, exc: AlreadyExists):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=409
    )


@app.exception_handler(TooManyCommentRequests)
async def too_many_comment_handler(req: starlette.requests.Request, exc: AlreadyExists):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=429
    )


@app.exception_handler(TooManyCommentsToLecturer)
async def too_many_comment_handler(req: starlette.requests.Request, exc: AlreadyExists):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=429
    )


@app.exception_handler(ForbiddenAction)
async def forbidden_action_handler(req: starlette.requests.Request, exc: ForbiddenAction):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=403
    )


@app.exception_handler(WrongMark)
async def wrong_mark_handler(req: starlette.requests.Request, exc: WrongMark):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=400
    )


@app.exception_handler(CommentTooLong)
async def comment_too_long_handler(req: starlette.requests.Request, exc: CommentTooLong):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=400
    )


@app.exception_handler(ForbiddenSymbol)
async def forbidden_symbol_handler(req: starlette.requests.Request, exc: ForbiddenSymbol):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=400
    )


@app.exception_handler(UpdateError)
async def update_error_handler(req: starlette.requests.Request, exc: UpdateError):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=409
    )
