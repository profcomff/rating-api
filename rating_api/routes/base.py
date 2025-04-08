from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi_sqlalchemy import DBSessionMiddleware

from rating_api import __version__
from rating_api.routes.comment import comment
from rating_api.routes.lecturer import lecturer
from rating_api.routes.like import like
from rating_api.settings import Settings, get_settings
from rating_api.utils.logging_utils import get_request_body, log_request


settings: Settings = get_settings()
app = FastAPI(
    title='Рейтинг преподавателей',
    description='Хранение и работа с рейтингом преподавателей и отзывами на них.',
    version=__version__,
    # Отключаем нелокальную документацию
    root_path=settings.ROOT_PATH if __version__ != 'dev' else '/',
    docs_url=None if __version__ != 'dev' else '/docs',
    redoc_url=None,
)

app.add_middleware(
    DBSessionMiddleware,
    db_url=str(settings.DB_DSN),
    engine_args={"pool_pre_ping": True, "isolation_level": "AUTOCOMMIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

app.include_router(lecturer)
app.include_router(comment)
app.include_router(like)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Основной middleware, который логирует запрос и восстанавливает тело."""
    try:
        request, json_body = await get_request_body(request)  # Получаем тело и восстанавливаем request
        response: Response = await call_next(request)
        status_code = response.status_code
    except Exception:
        status_code = 500
        response = Response(content="Internal server error", status_code=500)
    if __version__ != "dev":  # Локально не отправляем логи в маркетинг
        await log_request(request, status_code, json_body)  # Логируем запрос

    return response
