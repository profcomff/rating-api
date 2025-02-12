import asyncio
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi_sqlalchemy import DBSessionMiddleware

# from auth_lib.fastapi import UnionAuth

from rating_api import __version__, LOGGING_MARKETING_URL
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

async def send_log(log_data):
    """Отправляем лог на внешний сервис асинхронно"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(LOGGING_MARKETING_URL, json=log_data)
        except Exception as log_error:
            print(f"Ошибка при отправке логов: {log_error}")

async def get_request_body(request: Request) -> tuple[Request, str]:
    """Читает тело запроса и возвращает новый request и тело в виде JSON-строки."""
    body = await request.body()
    json_body = body.decode("utf-8") if body else "{}"

    async def new_stream():
        yield body

    return Request(request.scope, receive=new_stream()), json_body

async def log_request(request: Request, status_code: int, json_body: str):
    """Формирует лог и отправляет его в асинхронную задачу."""
    log_data = {
        "user_id": -2,  # UnionAuth()(request).get('id')
        "action": request.method,
        "additional_data": f"status_code: {status_code}, auth_user_id: {2323423}, request: {json_body}",
        "path_from": app.root_path,
        "path_to": request.url.path,
    }
    asyncio.create_task(send_log(log_data))

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

    await log_request(request, status_code, json_body)  # Логируем запрос

    return response
