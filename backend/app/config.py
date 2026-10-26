"""Application settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:change-me-locally@db:5432/app"
    upload_dir: str = "/app/data/uploads"
    cors_origins: str = "http://localhost:5173"
    coaching_debug_token: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    garmin_token_key: str = ""
    session_secret: str = "local-development-only-change-me"
    session_https_only: bool = False
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
