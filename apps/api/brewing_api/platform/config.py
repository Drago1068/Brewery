from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Brewing Platform API"
    environment: str = "development"
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    bootstrap_admin_username: str
    bootstrap_admin_password: str
    session_secret: str
    session_cookie_secure: bool = False
    session_ttl_hours: int = 12
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    public_origin: str = "http://localhost:18101"
    media_root: str = "/tmp/brewing-media"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("session_secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
