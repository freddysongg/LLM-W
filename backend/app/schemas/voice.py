from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VoiceSessionStatus = Literal["pending", "active", "completed", "failed"]
VoiceTerminationReason = Literal[
    "session_end",
    "client_disconnect",
    "pipeline_error",
    "session_timeout",
]
VoiceEventType = Literal[
    "transcript",
    "tool_call",
    "tool_result",
    "agent_text",
    "error",
    "session_end",
]


class VoiceSessionCreateRequest(BaseModel):
    """Body of POST /api/v1/voice/sessions. Tunable knobs for the demo session."""

    system_prompt: str = Field(min_length=1, max_length=4000)
    cartesia_voice_id: str = Field(min_length=1)
    openai_model_id: str = "gpt-4o-mini"

    model_config = {"extra": "forbid"}


class VoiceSessionCreateResponse(BaseModel):
    """Response of POST /api/v1/voice/sessions."""

    session_id: str
    websocket_path: str
    artifact_path: str
    status: VoiceSessionStatus = "pending"

    model_config = {"extra": "forbid"}


class VoiceSessionEventEnvelope(BaseModel):
    """Typed envelope for non-audio control frames sent to the client over the WebSocket.

    Audio frames are raw PCM and not wrapped in JSON.
    """

    type: VoiceEventType
    payload: dict[str, object]

    model_config = {"extra": "forbid"}
