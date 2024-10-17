import starlette.requests
from starlette.responses import JSONResponse

from rating_api.exceptions import AlreadyExists, ForbiddenAction, ObjectNotFound, TooManyCommentRequests
from rating_api.schemas.base import StatusResponseModel

from .base import app


@app.exception_handler(ObjectNotFound)
async def not_found_handler(req: starlette.requests.Request, exc: ObjectNotFound):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=404
    )


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


@app.exception_handler(ForbiddenAction)
async def forbidden_action_handler(req: starlette.requests.Request, exc: AlreadyExists):
    return JSONResponse(
        content=StatusResponseModel(status="Error", message=exc.eng, ru=exc.ru).model_dump(), status_code=403
    )