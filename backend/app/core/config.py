from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "ReturnShieldAI"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # PostgreSQL
    postgres_user: str = "returnshield"
    postgres_password: str = "returnshield_secret"
    postgres_db: str = "returnshield"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return os.getenv(
            "DATABASE_URL",
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}",
        )

    @property
    def database_url_sync(self) -> str:
        return os.getenv(
            "DATABASE_URL_SYNC",
            f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}",
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return os.getenv("REDIS_URL", f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}")

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def cors_origin_regex(self) -> str | None:
        return None

    # Import
    import_chunk_size: int = 10_000
    max_import_workers: int = 4

    # Scoring
    scoring_timeout_seconds: int = 30
    default_risk_threshold_low: int = 40
    default_risk_threshold_high: int = 70

    # Logging
    log_level: str = "INFO"
    log_format: str = "json" if os.getenv("APP_ENV") == "production" else "console"

    # Paths
    data_dir: Path = Path(__file__).parent.parent.parent.parent / "data"

    model_config = {"env_file": ".env.production", "extra": "ignore"}


settings = Settings()
