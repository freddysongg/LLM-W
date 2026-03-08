from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    app_name: str = "LLM Fine-Tuning Workbench"
    app_version: str = "1.0.0"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./data/workbench.db"
    projects_dir: Path = Path("./projects")
    data_dir: Path = Path("./data")

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    ai_api_key: str | None = None
    ai_provider: str = "anthropic"
    ai_model_id: str = "claude-sonnet-4-6"
    ai_base_url: str | None = None
    storage_warning_threshold_gb: float = 50.0
    watchdog_stale_timeout_seconds: int = 120
    watchdog_heartbeat_interval_seconds: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = AppConfig()
