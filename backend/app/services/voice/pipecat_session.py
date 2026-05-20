"""Pipecat pipeline construction and session lifecycle for the voice demo.

The single WebSocket multiplexes binary PCM audio (mic + TTS) and JSON control
frames (transcripts, tool calls, errors). The wire format is the raw shape the
frontend already produces — 16 kHz PCM16 mono uplink, 24 kHz PCM16 mono
downlink, JSON envelopes for control. `_build_raw_pcm_json_serializer` glues
that to Pipecat's `FrameSerializer` contract; we do not use
`ProtobufFrameSerializer` because the browser client speaks raw PCM, not the
Pipecat protobuf schema.

`pipecat-ai` is an optional extra. Every `pipecat.*` import lives inside a
function body so this module is importable on base/local installs. See
`tests/test_voice_session.py::test_voice_module_imports_with_pipecat_blocked`
for the contract.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from app.core.exceptions import VoicePipecatNotInstalledError
from app.services.voice.shopping_tools import (
    CartState,
    build_shopping_tools_schema,
    register_shopping_handlers,
)
from app.services.voice.transcript_writer import TranscriptWriter

_AUDIO_IN_SAMPLE_RATE = 16_000
_AUDIO_OUT_SAMPLE_RATE = 24_000
_CONTROL_TYPE_SESSION_END = "session_end"

if TYPE_CHECKING:
    from fastapi import WebSocket


@dataclass(frozen=True)
class VoiceSessionConfig:
    """Static config baked at session creation. No mutation after construction."""

    session_id: str
    artifact_path: Path
    deepgram_api_key: str
    cartesia_api_key: str
    openai_api_key: str
    system_prompt: str
    cartesia_voice_id: str
    openai_model_id: str


class VoiceSessionHandle(Protocol):
    """Public contract the route handler holds against a running session."""

    session_id: str

    async def run_until_disconnect(self) -> None: ...

    async def shutdown(self, *, termination_reason: str) -> None: ...


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_config_snapshot(*, config: VoiceSessionConfig) -> dict[str, str]:
    return {
        "openai_model_id": config.openai_model_id,
        "cartesia_voice_id": config.cartesia_voice_id,
        "stt_provider": "deepgram",
        "tts_provider": "cartesia",
        "system_prompt": config.system_prompt,
    }


class _VoiceSessionHandleImpl:
    """Concrete handle wrapping a Pipecat runner, task, and the transcript writer."""

    def __init__(
        self,
        *,
        session_id: str,
        writer: TranscriptWriter,
        runner: Any,
        task: Any,
    ) -> None:
        self._session_id = session_id
        self._writer = writer
        self._runner = runner
        self._task = task
        self._is_finalized = False

    @property
    def session_id(self) -> str:
        return self._session_id

    async def run_until_disconnect(self) -> None:
        await self._runner.run(self._task)

    async def shutdown(self, *, termination_reason: str) -> None:
        if self._is_finalized:
            return
        self._is_finalized = True
        cancel_callable = getattr(self._task, "cancel", None)
        if cancel_callable is not None:
            outcome = cancel_callable()
            if hasattr(outcome, "__await__"):
                with contextlib.suppress(Exception):
                    await outcome
        self._writer.finalize(
            ended_at_iso=_now_iso(),
            termination_reason=termination_reason,
        )
        self._writer.flush()


def _import_pipecat_modules() -> dict[str, Any]:
    """Import every pipecat symbol we need behind a single try/except.

    A bare `import pipecat` would not catch the case where the package exists
    but one of the submodules is missing, so each named symbol is imported
    explicitly and the whole bundle returns as a dict.
    """
    try:
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.frames.frames import (
            EndFrame,
            ErrorFrame,
            InputAudioRawFrame,
            InterimTranscriptionFrame,
            OutputAudioRawFrame,
            TranscriptionFrame,
        )
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.pipeline.task import PipelineTask
        from pipecat.processors.aggregators.llm_context import LLMContext
        from pipecat.processors.aggregators.llm_response_universal import (
            LLMContextAggregatorPair,
        )
        from pipecat.serializers.base_serializer import FrameSerializer
        from pipecat.services.cartesia.tts import CartesiaTTSService
        from pipecat.services.deepgram.stt import DeepgramSTTService
        from pipecat.services.openai.llm import OpenAILLMService
        from pipecat.transports.websocket.fastapi import (
            FastAPIWebsocketParams,
            FastAPIWebsocketTransport,
        )
    except ImportError as exc:
        raise VoicePipecatNotInstalledError() from exc

    return {
        "SileroVADAnalyzer": SileroVADAnalyzer,
        "Pipeline": Pipeline,
        "PipelineRunner": PipelineRunner,
        "PipelineTask": PipelineTask,
        "LLMContext": LLMContext,
        "LLMContextAggregatorPair": LLMContextAggregatorPair,
        "FrameSerializer": FrameSerializer,
        "CartesiaTTSService": CartesiaTTSService,
        "DeepgramSTTService": DeepgramSTTService,
        "OpenAILLMService": OpenAILLMService,
        "FastAPIWebsocketParams": FastAPIWebsocketParams,
        "FastAPIWebsocketTransport": FastAPIWebsocketTransport,
        "EndFrame": EndFrame,
        "ErrorFrame": ErrorFrame,
        "InputAudioRawFrame": InputAudioRawFrame,
        "InterimTranscriptionFrame": InterimTranscriptionFrame,
        "OutputAudioRawFrame": OutputAudioRawFrame,
        "TranscriptionFrame": TranscriptionFrame,
    }


def _build_raw_pcm_json_serializer(*, modules: dict[str, Any]) -> Any:
    """Build the wire serializer that matches the browser client's wire format.

    Outgoing: `OutputAudioRawFrame` → raw PCM16 bytes; transcript / error frames
    → JSON envelopes with `type` + `payload`. Incoming: bytes → InputAudioRawFrame
    at the uplink sample rate, JSON text → `EndFrame` for `session_end` envelopes.
    Other frames are dropped so the transport stays silent on unrelated traffic.
    """
    frame_serializer_cls = modules["FrameSerializer"]
    output_audio_cls = modules["OutputAudioRawFrame"]
    input_audio_cls = modules["InputAudioRawFrame"]
    transcription_cls = modules["TranscriptionFrame"]
    interim_transcription_cls = modules["InterimTranscriptionFrame"]
    error_cls = modules["ErrorFrame"]
    end_cls = modules["EndFrame"]

    def _transcript_payload(frame: Any, *, is_interim: bool) -> dict[str, Any]:
        timestamp = getattr(frame, "timestamp", "") or ""
        return {
            "role": "user",
            "text": getattr(frame, "text", "") or "",
            "started_at": timestamp,
            "ended_at": None if is_interim else timestamp,
            "is_interim": is_interim,
        }

    class RawPcmJsonSerializer(frame_serializer_cls):
        async def serialize(self, frame: Any) -> str | bytes | None:
            if isinstance(frame, output_audio_cls):
                audio = getattr(frame, "audio", b"")
                return audio if audio else None
            if isinstance(frame, interim_transcription_cls):
                return json.dumps(
                    {
                        "type": "transcript",
                        "payload": _transcript_payload(frame, is_interim=True),
                    }
                )
            if isinstance(frame, transcription_cls):
                return json.dumps(
                    {
                        "type": "transcript",
                        "payload": _transcript_payload(frame, is_interim=False),
                    }
                )
            if isinstance(frame, error_cls):
                message = getattr(frame, "error", "") or "Pipeline error"
                return json.dumps({"type": "error", "payload": {"message": message}})
            return None

        async def deserialize(self, data: str | bytes) -> Any | None:
            if isinstance(data, (bytes, bytearray)):
                if not data:
                    return None
                return input_audio_cls(
                    audio=bytes(data),
                    sample_rate=_AUDIO_IN_SAMPLE_RATE,
                    num_channels=1,
                )
            try:
                envelope = json.loads(data)
            except (ValueError, TypeError):
                return None
            if not isinstance(envelope, dict):
                return None
            if envelope.get("type") == _CONTROL_TYPE_SESSION_END:
                return end_cls()
            return None

    return RawPcmJsonSerializer()


def _build_transport(
    *,
    websocket: WebSocket,
    modules: dict[str, Any],
) -> Any:
    transport_params = modules["FastAPIWebsocketParams"](
        audio_in_enabled=True,
        audio_in_sample_rate=_AUDIO_IN_SAMPLE_RATE,
        audio_out_enabled=True,
        audio_out_sample_rate=_AUDIO_OUT_SAMPLE_RATE,
        add_wav_header=False,
        vad_analyzer=modules["SileroVADAnalyzer"](),
        serializer=_build_raw_pcm_json_serializer(modules=modules),
    )
    return modules["FastAPIWebsocketTransport"](
        websocket=websocket,
        params=transport_params,
    )


def _build_pipeline(
    *,
    transport: Any,
    config: VoiceSessionConfig,
    modules: dict[str, Any],
) -> tuple[Any, Any]:
    stt = modules["DeepgramSTTService"](api_key=config.deepgram_api_key)
    tts = modules["CartesiaTTSService"](
        api_key=config.cartesia_api_key,
        voice_id=config.cartesia_voice_id,
    )
    llm = modules["OpenAILLMService"](
        api_key=config.openai_api_key,
        model=config.openai_model_id,
    )
    tools_schema = build_shopping_tools_schema()
    context = modules["LLMContext"](
        tools=tools_schema,
        messages=[{"role": "system", "content": config.system_prompt}],
    )
    aggregator_pair = modules["LLMContextAggregatorPair"](context)
    user_aggregator = aggregator_pair.user()
    assistant_aggregator = aggregator_pair.assistant()
    pipeline = modules["Pipeline"](
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    return pipeline, llm


async def start_voice_session(
    *,
    config: VoiceSessionConfig,
    websocket: WebSocket,
) -> VoiceSessionHandle:
    """Wire transport + Pipecat services + tool handlers and return a handle.

    The handle's `run_until_disconnect` drives the Pipecat runner; `shutdown`
    cancels the task, finalizes the transcript writer, and flushes the JSON
    artifact. Side effects: creates the writer's parent directory on first
    flush, registers four tool handlers on the LLM service.
    """
    modules = _import_pipecat_modules()
    writer = TranscriptWriter(
        session_id=config.session_id,
        artifact_path=config.artifact_path,
        started_at_iso=_now_iso(),
        config_snapshot=_build_config_snapshot(config=config),
    )
    cart = CartState()
    transport = _build_transport(websocket=websocket, modules=modules)
    pipeline, llm = _build_pipeline(transport=transport, config=config, modules=modules)
    register_shopping_handlers(llm=llm, writer=writer, cart=cart)
    task = modules["PipelineTask"](pipeline)
    runner = modules["PipelineRunner"]()
    return _VoiceSessionHandleImpl(
        session_id=config.session_id,
        writer=writer,
        runner=runner,
        task=task,
    )
