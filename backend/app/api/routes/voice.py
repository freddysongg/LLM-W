"""HTTP + WebSocket routes for the Pipecat-powered voice demo.

`POST /api/v1/voice/sessions` reserves session state and returns the URL the
client must connect to. The WebSocket endpoint at
`/api/v1/voice/sessions/{session_id}/stream` accepts the connection, boots the
Pipecat pipeline, and runs until the client disconnects. On disconnect the
service finalizes the transcript and writes the JSON artifact to
`data/voice_sessions/<session_id>.json`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.exceptions import (
    VoiceCredentialsMissingError,
    VoicePipecatNotInstalledError,
    VoiceSessionAlreadyActiveError,
    VoiceSessionNotFoundError,
)
from app.schemas.voice import (
    VoiceSessionCreateRequest,
    VoiceSessionCreateResponse,
)
from app.services.voice import voice_service

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.post("/sessions", response_model=VoiceSessionCreateResponse, status_code=201)
async def create_voice_session(
    payload: VoiceSessionCreateRequest,
) -> VoiceSessionCreateResponse:
    try:
        return voice_service.create_session(payload=payload)
    except VoiceCredentialsMissingError as exc:
        raise HTTPException(
            status_code=412,
            detail={
                "code": "VOICE_CREDENTIALS_MISSING",
                "message": str(exc),
                "details": {"missing": exc.missing},
            },
        ) from exc
    except VoiceSessionAlreadyActiveError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "VOICE_SESSION_ALREADY_ACTIVE",
                "message": str(exc),
                "details": {"active_session_id": exc.active_session_id},
            },
        ) from exc


@router.websocket("/sessions/{session_id}/stream")
async def stream_voice_session(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    termination_reason = "client_disconnect"
    try:
        await voice_service.run_session(session_id=session_id, websocket=websocket)
        termination_reason = "session_end"
    except WebSocketDisconnect:
        termination_reason = "client_disconnect"
    except VoiceSessionNotFoundError:
        await websocket.close(code=4404)
        return
    except VoicePipecatNotInstalledError:
        await websocket.close(code=4503)
        await voice_service.finalize_session(
            session_id=session_id,
            reason="pipeline_error",
        )
        return
    except Exception:
        termination_reason = "pipeline_error"
        raise
    finally:
        await voice_service.finalize_session(
            session_id=session_id,
            reason=termination_reason,
        )
