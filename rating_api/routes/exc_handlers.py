import starlette.requests
from starlette.responses import JSONResponse

from rating_api.schemas.base import StatusResponseModel
from rating_api.exceptions import (
    AlreadyExists,
    ObjectNotFound,
)

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