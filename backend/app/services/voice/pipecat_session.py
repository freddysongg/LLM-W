"""Pipecat pipeline construction and session lifecycle for the voice demo.

The single WebSocket multiplexes binary PCM audio (mic + TTS) and JSON control
frames (transcripts, tool calls, errors). This matches Pipecat's
`FastAPIWebsocketTransport` default frame serializer — see Q1 in
`.context/designs/pipecat-voice-demo.md` for the rationale on staying with one
channel rather than splitting WS-for-audio + SSE-for-control. If the transport
rejects mixed frame types at runtime the fallback is a separate SSE endpoint;
no fallback was needed for the unit tests here because we stub the transport.

`pipecat-ai` is an optional extra. Every `pipecat.*` import lives inside a
function body so this module is importable on base/local installs. See
`tests/test_voice_session.py::test_voice_module_imports_with_pipecat_blocked`
for the contract.
"""

from __future__ import annotations

import contextlib
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
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.pipeline.task import PipelineTask
        from pipecat.processors.aggregators.llm_context import (
            LLMContext,
            LLMContextAggregatorPair,
        )
        from pipecat.serializers.protobuf import ProtobufFrameSerializer
        from pipecat.services.cartesia.tts import CartesiaTTSService
        from pipecat.services.deepgram.stt import DeepgramSTTService
        from pipecat.services.openai.llm import OpenAILLMService
        from pipecat.transports.network.fastapi_websocket import (
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
        "ProtobufFrameSerializer": ProtobufFrameSerializer,
        "CartesiaTTSService": CartesiaTTSService,
        "DeepgramSTTService": DeepgramSTTService,
        "OpenAILLMService": OpenAILLMService,
        "FastAPIWebsocketParams": FastAPIWebsocketParams,
        "FastAPIWebsocketTransport": FastAPIWebsocketTransport,
    }


def _build_transport(
    *,
    websocket: WebSocket,
    modules: dict[str, Any],
) -> Any:
    transport_params = modules["FastAPIWebsocketParams"](
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,
        vad_analyzer=modules["SileroVADAnalyzer"](),
        serializer=modules["ProtobufFrameSerializer"](),
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
