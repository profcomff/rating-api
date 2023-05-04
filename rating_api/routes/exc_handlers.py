import starlette.requests
from starlette.responses import JSONResponse

from rating_api.exceptions import ForbiddenAction, ObjectNotFound

from .base import app

from rating_api.routes.models.base import StatusResponseModel


@app.exception_handler(ObjectNotFound)
async def not_found_handler(req: starlette.requests.Request, exc: ObjectNotFound):
    return JSONResponse(content=StatusResponseModel(status="Error", message=f"{exc}").dict(), status_code=404)


@app.exception_handler(ForbiddenAction)
async def not_found_handler(req: starlette.requests.Request, exc: ForbiddenAction):
    return JSONResponse(content=StatusResponseModel(status="Error", message=f"{exc}").dict(), status_code=403)
