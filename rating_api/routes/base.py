from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_sqlalchemy import DBSessionMiddleware
from logger_middleware import LoggerMiddleware

from rating_api import __version__
from rating_api.routes.comment import comment
from rating_api.routes.lecturer import lecturer
from rating_api.settings import Settings, get_settings


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

if __version__ != 'dev':
    app.add_middleware(LoggerMiddleware, service_id=settings.SERVICE_ID)
