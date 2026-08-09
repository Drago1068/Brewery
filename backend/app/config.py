from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    brewingos_env: str = "development"
    brewingos_secret_key: str = "change-me"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://brewingos:brewingos@localhost:5432/brewingos"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    storage_path: str = "./data/storage"
    log_path: str = "./data/logs"

    # Single-homebrewer default actor until full auth lands
    default_actor_id: str = "local-brewer"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
