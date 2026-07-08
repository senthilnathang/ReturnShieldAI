from dataclasses import dataclass
from pathlib import Path
import os


_BASE_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = (_BASE_DIR / "backend" / "returnshield.db").resolve()


def _resolve_database_url(value: str) -> str:
    if not value.startswith("sqlite:///"):
        return value

    raw_path = value[len("sqlite:///"):]
    if raw_path.startswith("/"):
        return value

    normalized = raw_path.lstrip("./")
    if normalized in {"", "returnshield.db"}:
        db_path = _DEFAULT_DB_PATH
    else:
        db_path = (_BASE_DIR / normalized).resolve()
    return f"sqlite:///{db_path}"


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "ReturnShield AI")
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = _resolve_database_url(
        os.getenv(
            "DATABASE_URL",
            "sqlite:///./returnshield.db",
        )
    )
    cors_origin_regex: str = os.getenv(
        "CORS_ORIGIN_REGEX",
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    )


settings = Settings()
