import os
from functools import lru_cache

from pydantic import ConfigDict, PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    DB_DSN: PostgresDsn = 'postgresql://postgres@localhost:5432/postgres'
    ROOT_PATH: str = '/' + os.getenv("APP_NAME", "")
    COMMENT_CREATE_FREQUENCY_IN_MINUTES: int = 1
    ACCEPTABLE_SIMILARITY: float = 0.4
    CORS_ALLOW_ORIGINS: list[str] = ['*']
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ['*']
    CORS_ALLOW_HEADERS: list[str] = ['*']

    model_config = ConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
