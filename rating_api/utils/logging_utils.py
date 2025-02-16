import asyncio
import json
import logging

import httpx
from auth_lib.fastapi import UnionAuth
from fastapi import Request

from rating_api.settings import Settings, get_settings


settings: Settings = get_settings()

log = logging.getLogger(__name__)

RETRY_DELAYS = [2, 4, 8]  # Задержки перед повторными попытками (в секундах)


async def send_log(log_data):
    """Отправляем лог на внешний сервис асинхронно с обработкой ошибок и ретраями"""
    async with httpx.AsyncClient() as client:
        for attempt, sleep_time in enumerate(RETRY_DELAYS, start=1):
            try:
                response = await client.post(settings.LOGGING_MARKETING_URL, json=log_data)

                if response.status_code not in {408, 409, 429, 500, 502, 503, 504}:
                    log.info(f"Ответ записи логов от markting status_code: {response.status_code}")
                    break  # Успешно или ошибки, которые не стоит повторять (например, неправильные данные)

            except httpx.HTTPStatusError as e:
                log.warning(f"HTTP ошибка ({e.response.status_code}): {e.response.text}")

            except httpx.RequestError as e:
                log.warning(f"Ошибка сети: {e}")

            except Exception as e:
                log.warning(f"Неизвестная ошибка: {e}")

            await asyncio.sleep(sleep_time)  # Ожидание перед повторной попыткой

        else:
            log.warning("Не удалось отправить лог после нескольких попыток.")


async def get_request_body(request: Request) -> tuple[Request, str]:
    """Читает тело запроса и возвращает новый request и тело в виде JSON."""
    body = await request.body()
    json_body = json.loads(body) if body else {}  # В json(dict) from byte string

    async def new_stream():
        yield body

    return Request(request.scope, receive=new_stream()), json_body


async def get_user_id(request: Request):
    """Получает user_id из UnionAuth"""
    try:
        user_id = UnionAuth()(request).get('id')
    except Exception as e:
        user_id = "Not auth"  # Или лучше -1? чтобы типизация :int была?
        log.error(f"USER_AUTH: {e}")

    return user_id


async def log_request(request: Request, status_code: int, json_body: dict):
    """Формирует лог и отправляет его в асинхронную задачу."""

    additional_data = {
        "response_status_code": status_code,
        "auth_user_id": await get_user_id(request),
        "query": request.url.path + "?" + request.url.query,
        "request": json_body,
    }
    log_data = {
        "user_id": -2,
        "action": request.method,
        "additional_data": json.dumps(additional_data),
        "path_from": '',  # app.root_path
        "path_to": request.url.path,
    }
    asyncio.create_task(send_log(log_data))
