from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.schemas.settings import AITestResponse, SettingsResponse, SettingsUpdate

_SETTINGS_FILE: Path = settings.data_dir / "settings.json"

# Runtime overrides applied on top of pydantic-settings defaults
_overrides: dict[str, Any] = {}


def _load_persisted_overrides() -> None:
    if _SETTINGS_FILE.exists():
        try:
            with _SETTINGS_FILE.open() as f:
                _overrides.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass


def _persist_overrides() -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _SETTINGS_FILE.open("w") as f:
        json.dump(_overrides, f, indent=2)


def get_settings() -> SettingsResponse:
    return SettingsResponse(
        ai_provider=_overrides.get("ai_provider", settings.ai_provider),
        ai_api_key_set=bool(
            _overrides.get("ai_api_key") or settings.ai_api_key
        ),
        ai_model_id=_overrides.get("ai_model_id", settings.ai_model_id),
        ai_base_url=_overrides.get("ai_base_url", settings.ai_base_url),
        default_projects_dir=str(
            _overrides.get("default_projects_dir", str(settings.projects_dir))
        ),
        storage_warning_threshold_gb=float(
            _overrides.get(
                "storage_warning_threshold_gb", settings.storage_warning_threshold_gb
            )
        ),
        watchdog_stale_timeout_seconds=int(
            _overrides.get(
                "watchdog_stale_timeout_seconds", settings.watchdog_stale_timeout_seconds
            )
        ),
        watchdog_heartbeat_interval_seconds=int(
            _overrides.get(
                "watchdog_heartbeat_interval_seconds",
                settings.watchdog_heartbeat_interval_seconds,
            )
        ),
    )


def update_settings(*, payload: SettingsUpdate) -> SettingsResponse:
    if payload.ai_provider is not None:
        _overrides["ai_provider"] = payload.ai_provider
    if payload.ai_api_key is not None:
        _overrides["ai_api_key"] = payload.ai_api_key
    if payload.ai_model_id is not None:
        _overrides["ai_model_id"] = payload.ai_model_id
    if payload.ai_base_url is not None:
        _overrides["ai_base_url"] = payload.ai_base_url
    if payload.default_projects_dir is not None:
        _overrides["default_projects_dir"] = payload.default_projects_dir
    if payload.storage_warning_threshold_gb is not None:
        _overrides["storage_warning_threshold_gb"] = payload.storage_warning_threshold_gb
    if payload.watchdog_stale_timeout_seconds is not None:
        _overrides["watchdog_stale_timeout_seconds"] = payload.watchdog_stale_timeout_seconds
    if payload.watchdog_heartbeat_interval_seconds is not None:
        _overrides["watchdog_heartbeat_interval_seconds"] = (
            payload.watchdog_heartbeat_interval_seconds
        )

    _persist_overrides()
    return get_settings()


async def test_ai_connection() -> AITestResponse:
    current = get_settings()
    provider = current.ai_provider
    model_id = current.ai_model_id
    api_key = _overrides.get("ai_api_key") or settings.ai_api_key

    if not api_key:
        return AITestResponse(
            success=False,
            message="No API key configured",
            provider=provider,
            model_id=model_id,
        )

    try:
        if provider == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model=model_id,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        elif provider == "openai_compatible":
            import openai

            base_url = current.ai_base_url
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            client.chat.completions.create(
                model=model_id,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        else:
            return AITestResponse(
                success=False,
                message=f"Unknown provider: {provider}",
                provider=provider,
                model_id=model_id,
            )
    except Exception as exc:
        return AITestResponse(
            success=False,
            message=str(exc),
            provider=provider,
            model_id=model_id,
        )

    return AITestResponse(
        success=True,
        message="Connection successful",
        provider=provider,
        model_id=model_id,
    )
