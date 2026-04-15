from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.schemas.settings import AITestResponse, ModalTestResponse, SettingsResponse, SettingsUpdate

_SETTINGS_FILE: Path = settings.data_dir / "settings.json"

# Runtime overrides applied on top of pydantic-settings defaults
_overrides: dict[str, Any] = {}

# Migration map for settings.json files written before the camelCase→snake_case fix.
_CAMEL_TO_SNAKE: dict[str, str] = {
    "aiProvider": "ai_provider",
    "aiApiKey": "ai_api_key",
    "aiModelId": "ai_model_id",
    "aiBaseUrl": "ai_base_url",
    "defaultProjectsDir": "default_projects_dir",
    "storageWarningThresholdGb": "storage_warning_threshold_gb",
    "watchdogStaleTimeoutSeconds": "watchdog_stale_timeout_seconds",
    "watchdogHeartbeatIntervalSeconds": "watchdog_heartbeat_interval_seconds",
}


def _load_persisted_overrides() -> None:
    if _SETTINGS_FILE.exists():
        try:
            with _SETTINGS_FILE.open() as f:
                raw: dict[str, Any] = json.load(f)
            # Migrate any camelCase keys written by the old frontend.
            migrated = {_CAMEL_TO_SNAKE.get(k, k): v for k, v in raw.items()}
            _overrides.update(migrated)
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
        is_modal_token_set=bool(
            _overrides.get("modal_token_id") and _overrides.get("modal_token_secret")
        ),
    )


def get_raw_api_key() -> str | None:
    """Return the plaintext API key from overrides or app defaults."""
    return _overrides.get("ai_api_key") or settings.ai_api_key


def get_modal_credentials() -> tuple[str, str] | None:
    """Return the Modal (token_id, token_secret) pair, or None if not configured."""
    token_id = _overrides.get("modal_token_id")
    token_secret = _overrides.get("modal_token_secret")
    if token_id and token_secret:
        return (str(token_id), str(token_secret))
    return None


def update_settings(*, payload: SettingsUpdate) -> SettingsResponse:
    if payload.ai_provider is not None:
        _overrides["ai_provider"] = payload.ai_provider
        # Clear stored base URL when switching away from openai_compatible so
        # the "openai" provider never accidentally inherits a custom base URL.
        if payload.ai_provider != "openai_compatible" and payload.ai_base_url is None:
            _overrides.pop("ai_base_url", None)
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
    if payload.modal_token_id is not None:
        _overrides["modal_token_id"] = payload.modal_token_id
    if payload.modal_token_secret is not None:
        _overrides["modal_token_secret"] = payload.modal_token_secret

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

            anthropic_client = anthropic.Anthropic(api_key=api_key)
            anthropic_client.messages.create(
                model=model_id,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        elif provider in ("openai", "openai_compatible"):
            import openai

            base_url = (
                "https://api.openai.com/v1"
                if provider == "openai"
                else current.ai_base_url
            )
            openai_client = openai.OpenAI(api_key=api_key, base_url=base_url)
            openai_client.chat.completions.create(
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


async def test_modal_connection() -> ModalTestResponse:
    credentials = get_modal_credentials()

    if not credentials:
        return ModalTestResponse(success=False, message="No Modal token configured")

    try:
        import modal

        token_id, token_secret = credentials
        client = modal.Client.from_credentials(token_id, token_secret)
        client.hello()
    except Exception as exc:
        return ModalTestResponse(success=False, message=str(exc))

    return ModalTestResponse(success=True, message="Modal connection successful")
