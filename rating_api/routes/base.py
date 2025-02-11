import asyncio
import time
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi_sqlalchemy import DBSessionMiddleware

# from auth_lib.fastapi import UnionAuth

from rating_api import __version__
from rating_api.routes.comment import comment
from rating_api.routes.lecturer import lecturer
from rating_api.settings import get_settings


settings = get_settings()
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

LOGGING_URL = (
    settings.ROOT_PATH if __version__ != 'dev' else 'http://localhost:8080/v1/action'
)  # Заменить на рабочие ссылки

async def send_log(log_data):
    """Отправляем лог на внешний сервис асинхронно"""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            await client.post(LOGGING_URL, json=log_data)
        except Exception as log_error:
            print(f"Ошибка при отправке логов: {log_error}")


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    try:
        response: Response = await call_next(request)  # Выполняем сам запрос
        status_code = response.status_code
    except Exception as e:
        status_code = 500  # Если произошла ошибка, ставим 500
        response = Response(content="Internal server error", status_code=500)  # Что делать с сообщением ошибки?

    log_data = {
        "user_id": 0,  # UnionAuth()(request).get('id')
        "action": "string",
        "additional_data": f"method: {request.method}, status_code: {status_code}",
        "path_from": "string",
        "path_to": app.root_path + request.url.path,
    }

    asyncio.create_task(send_log(log_data))

    return response
