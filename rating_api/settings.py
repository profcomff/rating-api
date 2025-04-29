import os
from functools import lru_cache

from pydantic import ConfigDict, PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    DB_DSN: PostgresDsn = 'postgresql://postgres@localhost:5432/postgres'
    ROOT_PATH: str = '/' + os.getenv("APP_NAME", "")
    SERVICE_ID: int = os.getenv("SERVICE_ID", -3)  # Указать какой id сервиса
    COMMENT_FREQUENCY_IN_MONTH: int = 10
    COMMENT_LECTURER_FREQUENCE_IN_MONTH: int = 6
    COMMENT_LIMIT: int = 20
    COMMENT_TO_LECTURER_LIMIT: int = 5
    MEAN_MARK_GENERAL_WEIGHT: float = 0.75
    CORS_ALLOW_ORIGINS: list[str] = ['*']
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ['*']
    CORS_ALLOW_HEADERS: list[str] = ['*']
    MAX_COMMENT_LENGTH: int = 3000

    # Environment setting
    APP_ENV: str = os.getenv("APP_ENV", "dev")  # Can be "dev", "test", or "prod"

    PROD_API_URL: str = "https://api.profcomff.com/"
    TEST_API_URL: str = "https://api.test.profcomff.com/"
    ACHIEVEMENT_GIVE_TOKEN: str = os.getenv("ACHIEVEMENT_API", "")

    '''Temp settings'''
    API_URL: str = "https://api.test.profcomff.com/"
    FIRST_COMMENT_ACHIEVEMENT_ID_TEST: int = 48
    FIRST_COMMENT_ACHIEVEMENT_ID_PROD: int = 12

    model_config = ConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
