from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]
REPO_ROOT = BASE_DIR.parent
DEFAULT_ENV = "local"
ENV_FILE_MAP = {
    "local": ".env",
    "test": ".env.test",
    "prod": ".env.prod",
}

app_env = os.getenv("APP_ENV", DEFAULT_ENV).lower()
raw_env_file = os.getenv("ENV_FILE", "").strip()
if raw_env_file:
    env_path = Path(raw_env_file)
    if not env_path.is_absolute():
        env_path = BASE_DIR / env_path
else:
    env_path = BASE_DIR / ENV_FILE_MAP.get(app_env, ".env")

if not env_path.exists():
    env_path = BASE_DIR / ".env"


class Settings(BaseSettings):
    APP_ENV: str = app_env
    DATABASE_URL: str = "postgresql+psycopg://fantasy:fantasy@localhost:5432/fantasy"
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ADMIN_TOKEN: str = "dev-admin"
    DUCKDB_PATH: str = str(BASE_DIR / "data" / "fantasy.duckdb")
    PARQUET_DIR: str = str(
        REPO_ROOT
        / "gronestats"
        / "data"
        / "Liga 1 Peru"
        / "2025"
        / "parquets"
        / "normalized"
    )
    SEASON_YEAR: int = 2026
    SEASON_NAME: str = "2026 Apertura"
    CORS_ORIGINS: str = "http://localhost:3000"
    CORS_ORIGIN_REGEX: str = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        for key in ("DUCKDB_PATH", "PARQUET_DIR"):
            raw = getattr(self, key, None)
            if not raw:
                continue
            path = Path(str(raw))
            if not path.is_absolute():
                setattr(self, key, str((BASE_DIR / path).resolve()))


@lru_cache
def get_settings() -> Settings:
    return Settings()
