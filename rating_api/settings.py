import os
from functools import lru_cache

from pydantic import ConfigDict, PostgresDsn
from pydantic_settings import BaseSettings


LOGGING_MARKETING_URLS = {
    "dev": f"http://localhost:{os.getenv('MARKETING_PORT', 8000)}/v1/action",
    "test": "https://api.test.profcomff.com/marketing/v1/action",
    "prod": "https://api.profcomff.com/marketing/v1/action",
}


class Settings(BaseSettings):
    """Application settings"""

    DB_DSN: PostgresDsn = 'postgresql://postgres@localhost:5432/postgres'
    ROOT_PATH: str = '/' + os.getenv("APP_NAME", "")
    COMMENT_FREQUENCY_IN_MONTH: int = 10
    COMMENT_LECTURER_FREQUENCE_IN_MONTH: int = 6
    COMMENT_LIMIT: int = 20
    COMMENT_TO_LECTURER_LIMIT: int = 5
    CORS_ALLOW_ORIGINS: list[str] = ['*']
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ['*']
    CORS_ALLOW_HEADERS: list[str] = ['*']
    LOGGING_MARKETING_URL: str = LOGGING_MARKETING_URLS.get(
        os.getenv("APP_VERSION", "dev"), LOGGING_MARKETING_URLS["test"]
    )

    model_config = ConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
