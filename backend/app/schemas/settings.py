from __future__ import annotations

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    ai_provider: str
    ai_api_key_set: bool
    ai_model_id: str
    ai_base_url: str | None
    default_projects_dir: str
    storage_warning_threshold_gb: float
    watchdog_stale_timeout_seconds: int
    watchdog_heartbeat_interval_seconds: int


class SettingsUpdate(BaseModel):
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_model_id: str | None = None
    ai_base_url: str | None = None
    default_projects_dir: str | None = None
    storage_warning_threshold_gb: float | None = None
    watchdog_stale_timeout_seconds: int | None = None
    watchdog_heartbeat_interval_seconds: int | None = None


class AITestResponse(BaseModel):
    success: bool
    message: str
    provider: str
    model_id: str
