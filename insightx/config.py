"""Load non-secret application settings from the environment."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_env: str
    log_level: str


def load_settings(env_file: Path | None = None) -> Settings:
    """Read .env; process variables take priority. Validate known settings."""
    path = PROJECT_ROOT / ".env" if env_file is None else env_file
    values = {**dotenv_values(path, interpolate=False), **os.environ}
    app_env = (values.get("APP_ENV") or "").strip().lower()
    log_level = (values.get("LOG_LEVEL") or "").strip().upper()
    if app_env not in {"development", "test", "production"}:
        raise ValueError("Set APP_ENV to development, test, or production.")
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("Set LOG_LEVEL to DEBUG, INFO, WARNING, ERROR, or CRITICAL.")
    return Settings(app_env=app_env, log_level=log_level)
