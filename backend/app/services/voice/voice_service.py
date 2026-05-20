"""Single-session orchestration around Pipecat for the voice demo.

The service owns three pieces of state:
- A "currently active session id" lock (only one demo session at a time, A2).
- A `dict[session_id, VoiceSessionConfig]` of pending sessions awaiting WS.
- A `dict[session_id, VoiceSessionHandle]` of active sessions after WS connect.

Credentials are resolved from `settings_service` (which already merges
overrides + `AppConfig`), mirroring the Modal pattern. Missing credentials
short-circuit before any Pipecat import attempt.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.exceptions import (
    VoiceCredentialsMissingError,
    VoiceSessionAlreadyActiveError,
    VoiceSessionNotFoundError,
)
from app.schemas.voice import (
    VoiceSessionCreateRequest,
    VoiceSessionCreateResponse,
)
from app.services import settings_service
from app.services.voice.pipecat_session import (
    VoiceSessionConfig,
    VoiceSessionHandle,
    start_voice_session,
)

if TYPE_CHECKING:
    from fastapi import WebSocket


@dataclass(frozen=True)
class _VoiceCredentials:
    """Resolved provider keys for one session."""

    deepgram_api_key: str
    cartesia_api_key: str
    openai_api_key: str


_active_session_id: str | None = None
_pending_configs: dict[str, VoiceSessionConfig] = {}
_pending_created_at: dict[str, float] = {}
_active_handles: dict[str, VoiceSessionHandle] = {}

# Time a pending session can hold the active-session lock before being treated
# as abandoned. Clients that crash, lose network, or close the tab between
# `POST /voice/sessions` and the WS upgrade would otherwise leave the lock held
# until process restart.
_PENDING_SESSION_TTL_SECONDS: float = 60.0


def _reset_active_state() -> None:
    """Clear in-memory voice state. Called from tests and from app startup recovery."""
    global _active_session_id
    _active_session_id = None
    _pending_configs.clear()
    _pending_created_at.clear()
    _active_handles.clear()


def _evict_if_pending_expired() -> None:
    """Drop the active-session lock if it is held by an abandoned pending session.

    Pending = client received a session id but never opened the WS within the
    TTL. Active handles are not subject to this check; once Pipecat boots, the
    WS lifecycle owns release.
    """
    global _active_session_id
    if _active_session_id is None:
        return
    if _active_session_id in _active_handles:
        return
    created_at = _pending_created_at.get(_active_session_id)
    if created_at is None:
        return
    if time.monotonic() - created_at < _PENDING_SESSION_TTL_SECONDS:
        return
    _pending_configs.pop(_active_session_id, None)
    _pending_created_at.pop(_active_session_id, None)
    _active_session_id = None


def _resolve_credentials() -> _VoiceCredentials:
    overrides = settings_service._overrides
    deepgram = overrides.get("deepgram_api_key") or settings.deepgram_api_key
    cartesia = overrides.get("cartesia_api_key") or settings.cartesia_api_key
    openai = overrides.get("openai_api_key") or settings.openai_api_key
    missing: list[str] = []
    if not deepgram:
        missing.append("deepgram_api_key")
    if not cartesia:
        missing.append("cartesia_api_key")
    if not openai:
        missing.append("openai_api_key")
    if missing:
        raise VoiceCredentialsMissingError(missing=missing)
    return _VoiceCredentials(
        deepgram_api_key=str(deepgram),
        cartesia_api_key=str(cartesia),
        openai_api_key=str(openai),
    )


def _artifact_path_for(*, session_id: str) -> Path:
    return settings.data_dir / "voice_sessions" / f"{session_id}.json"


def create_session(*, payload: VoiceSessionCreateRequest) -> VoiceSessionCreateResponse:
    """Reserve a session id + artifact path. Refuses if a session is already active."""
    global _active_session_id
    _evict_if_pending_expired()
    if _active_session_id is not None:
        raise VoiceSessionAlreadyActiveError(active_session_id=_active_session_id)
    credentials = _resolve_credentials()
    session_id = uuid.uuid4().hex
    artifact_path = _artifact_path_for(session_id=session_id)
    config = VoiceSessionConfig(
        session_id=session_id,
        artifact_path=artifact_path,
        deepgram_api_key=credentials.deepgram_api_key,
        cartesia_api_key=credentials.cartesia_api_key,
        openai_api_key=credentials.openai_api_key,
        system_prompt=payload.system_prompt,
        cartesia_voice_id=payload.cartesia_voice_id,
        openai_model_id=payload.openai_model_id,
    )
    _pending_configs[session_id] = config
    _pending_created_at[session_id] = time.monotonic()
    _active_session_id = session_id
    return VoiceSessionCreateResponse(
        session_id=session_id,
        websocket_path=f"/api/v1/voice/sessions/{session_id}/stream",
        artifact_path=str(artifact_path),
        status="pending",
    )


def get_active_session_id() -> str | None:
    return _active_session_id


def _set_active_handle(*, session_id: str, handle: VoiceSessionHandle) -> None:
    _active_handles[session_id] = handle


def release_active_session(*, session_id: str) -> None:
    """Release the active-session lock and drop any in-memory state for `session_id`."""
    global _active_session_id
    _pending_configs.pop(session_id, None)
    _pending_created_at.pop(session_id, None)
    _active_handles.pop(session_id, None)
    if _active_session_id == session_id:
        _active_session_id = None


async def _start_pipecat_session(
    *,
    config: VoiceSessionConfig,
    websocket: WebSocket,
) -> VoiceSessionHandle:
    """Indirection so tests can monkeypatch the Pipecat boot path."""
    return await start_voice_session(config=config, websocket=websocket)


async def run_session(*, session_id: str, websocket: WebSocket) -> None:
    """Boot the Pipecat pipeline for `session_id` and run until disconnect.

    The route handler accepts the WebSocket before calling this; this function
    is purely about wiring + lifecycle. Callers are responsible for catching
    `WebSocketDisconnect` and calling `finalize_session` with the matching
    reason so the JSON artifact is always written.
    """
    config = _pending_configs.pop(session_id, None)
    _pending_created_at.pop(session_id, None)
    if config is None:
        existing = _active_handles.get(session_id)
        if existing is not None:
            await existing.run_until_disconnect()
            return
        raise VoiceSessionNotFoundError(session_id)
    handle = await _start_pipecat_session(config=config, websocket=websocket)
    _set_active_handle(session_id=session_id, handle=handle)
    await handle.run_until_disconnect()


async def finalize_session(*, session_id: str, reason: str) -> None:
    """Shut down a session's handle and release the active-session lock."""
    handle = _active_handles.get(session_id)
    if handle is not None:
        await handle.shutdown(termination_reason=reason)
    release_active_session(session_id=session_id)
