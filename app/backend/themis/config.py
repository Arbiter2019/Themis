from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[3]
APP_DIR = ROOT_DIR / "app"
ENV_DIR = APP_DIR / "env"
LOG_DIR = APP_DIR / "logs"


class Settings(BaseModel):
    app_name: str = Field(default="Themis", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    database_url: str = Field(
        default="mysql+pymysql://themis:themis_password@127.0.0.1:3306/themis?charset=utf8mb4",
        alias="DATABASE_URL",
    )
    dify_base_url: str = Field(default="http://127.0.0.1:5001/v1", alias="DIFY_BASE_URL")
    dify_timeout_seconds: int = Field(default=120, alias="DIFY_TIMEOUT_SECONDS")
    session_secret: str = Field(default="change-me", alias="SESSION_SECRET")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"], alias="CORS_ORIGINS")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def get_settings() -> Settings:
    config = _read_json(ENV_DIR / "config.json")
    example = _read_json(ENV_DIR / "config.example.json")
    merged = {**example, **config}
    return Settings.model_validate(merged)

