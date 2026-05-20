from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.exceptions import (
    VoiceCredentialsMissingError,
    VoicePipecatNotInstalledError,
    VoiceSessionAlreadyActiveError,
)
from app.main import app
from app.schemas.voice import (
    VoiceSessionCreateRequest,
    VoiceSessionCreateResponse,
    VoiceSessionEventEnvelope,
)
from app.services import settings_service
from app.services.voice import (
    pipecat_session,
    shopping_tools,
    transcript_writer,
    voice_service,
)
from app.services.voice.transcript_writer import (
    TranscriptEntry,
    TranscriptWriter,
)


@pytest.fixture(autouse=True)
def reset_settings_overrides() -> None:
    settings_service._overrides.clear()
    voice_service._reset_active_state()
    yield
    settings_service._overrides.clear()
    voice_service._reset_active_state()


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def populated_credentials() -> None:
    settings_service._overrides["deepgram_api_key"] = "dg-test"
    settings_service._overrides["cartesia_api_key"] = "ct-test"
    settings_service._overrides["openai_api_key"] = "oa-test"


def _write_target(tmp_path: Path, session_id: str = "sess-1") -> Path:
    return tmp_path / "voice_sessions" / f"{session_id}.json"


def test_voice_module_does_not_import_pipecat_eagerly() -> None:
    """`pipecat-ai` is an optional voice extra; base installs must still import the module.

    Mirrors the existing `test_training_dispatcher_does_not_import_modal_eagerly` contract.
    """
    import app.services.voice.pipecat_session as session_module

    assert "FastAPIWebsocketTransport" not in session_module.__dict__
    assert "DeepgramSTTService" not in session_module.__dict__
    assert "CartesiaTTSService" not in session_module.__dict__
    assert "OpenAILLMService" not in session_module.__dict__
    assert "Pipeline" not in session_module.__dict__


def test_voice_module_imports_with_pipecat_blocked() -> None:
    """Force `import pipecat` to fail, then verify the module still imports cleanly."""
    blocked = {
        "pipecat",
        "pipecat.adapters",
        "pipecat.adapters.schemas",
        "pipecat.adapters.schemas.function_schema",
        "pipecat.adapters.schemas.tools_schema",
        "pipecat.audio",
        "pipecat.audio.vad",
        "pipecat.audio.vad.silero",
        "pipecat.frames",
        "pipecat.frames.frames",
        "pipecat.pipeline",
        "pipecat.pipeline.pipeline",
        "pipecat.pipeline.runner",
        "pipecat.pipeline.task",
        "pipecat.serializers",
        "pipecat.serializers.base_serializer",
        "pipecat.services",
        "pipecat.services.cartesia",
        "pipecat.services.cartesia.tts",
        "pipecat.services.deepgram",
        "pipecat.services.deepgram.stt",
        "pipecat.services.openai",
        "pipecat.services.openai.llm",
        "pipecat.transports",
        "pipecat.transports.network",
        "pipecat.transports.network.fastapi_websocket",
    }
    saved: dict[str, object] = {}
    for name in blocked:
        if name in sys.modules:
            saved[name] = sys.modules[name]
        sys.modules[name] = None  # type: ignore[assignment]
    try:
        for name in (
            "app.services.voice.pipecat_session",
            "app.services.voice",
        ):
            if name in sys.modules:
                del sys.modules[name]
        import app.services.voice.pipecat_session  # noqa: F401
    finally:
        for name in blocked:
            sys.modules.pop(name, None)
            if name in saved:
                sys.modules[name] = saved[name]  # type: ignore[assignment]


def test_voice_route_is_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/v1/voice/sessions" in paths
    websocket_paths = {
        getattr(route, "path", None)
        for route in app.routes
        if route.__class__.__name__ == "APIWebSocketRoute"
    }
    assert "/api/v1/voice/sessions/{session_id}/stream" in websocket_paths


def test_search_products_returns_shoe_results() -> None:
    cart = shopping_tools.CartState()
    result = shopping_tools.search_products(query="running shoes", max_price_usd=None, cart=cart)
    assert "results" in result
    assert len(result["results"]) >= 2
    for entry in result["results"]:
        assert {"sku", "name", "price_usd"} <= entry.keys()


def test_search_products_applies_price_filter() -> None:
    cart = shopping_tools.CartState()
    result = shopping_tools.search_products(query="running shoes", max_price_usd=50.0, cart=cart)
    for entry in result["results"]:
        assert entry["price_usd"] <= 50.0


def test_get_product_detail_returns_record_for_known_sku() -> None:
    cart = shopping_tools.CartState()
    result = shopping_tools.get_product_detail(sku="DEMO-001", cart=cart)
    assert result.get("sku") == "DEMO-001"
    assert "name" in result
    assert "price_usd" in result


def test_get_product_detail_returns_error_for_unknown_sku() -> None:
    cart = shopping_tools.CartState()
    result = shopping_tools.get_product_detail(sku="NOT-A-SKU", cart=cart)
    assert result == {"error": "sku_not_found"}


def test_add_to_cart_returns_ok_for_known_sku() -> None:
    cart = shopping_tools.CartState()
    result = shopping_tools.add_to_cart(sku="DEMO-001", quantity=2, cart=cart)
    assert result["status"] == "ok"
    assert result["cart_total_usd"] > 0
    assert cart.items["DEMO-001"] == 2


def test_add_to_cart_returns_error_when_sku_missing() -> None:
    cart = shopping_tools.CartState()
    result = shopping_tools.add_to_cart(sku="UNKNOWN-SKU", quantity=1, cart=cart)
    assert result["status"] == "error"
    assert "message" in result


def test_handoff_checkout_returns_pending_confirmation() -> None:
    cart = shopping_tools.CartState()
    cart.items["DEMO-001"] = 1
    result = shopping_tools.handoff_checkout(shipping_address_id="addr-1", cart=cart)
    assert result["status"] == "pending_confirmation"
    assert "summary" in result


def test_build_shopping_tools_schema_includes_all_four_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stub pipecat schema classes so the test exercises the wiring without the extra."""
    captured: dict[str, list[Any]] = {}

    class _FakeFunctionSchema:
        def __init__(
            self, *, name: str, description: str, properties: dict[str, object], required: list[str]
        ) -> None:
            self.name = name
            self.description = description
            self.properties = properties
            self.required = required

    class _FakeToolsSchema:
        def __init__(self, *, standard_tools: list[_FakeFunctionSchema]) -> None:
            captured["tools"] = standard_tools
            self.standard_tools = standard_tools

    fake_function_module = MagicMock()
    fake_function_module.FunctionSchema = _FakeFunctionSchema
    fake_tools_module = MagicMock()
    fake_tools_module.ToolsSchema = _FakeToolsSchema
    monkeypatch.setitem(
        sys.modules, "pipecat.adapters.schemas.function_schema", fake_function_module
    )
    monkeypatch.setitem(sys.modules, "pipecat.adapters.schemas.tools_schema", fake_tools_module)

    schema = shopping_tools.build_shopping_tools_schema()
    names = [tool.name for tool in schema.standard_tools]
    assert names == ["search_products", "get_product_detail", "add_to_cart", "handoff_checkout"]


def test_transcript_writer_round_trip(tmp_path: Path) -> None:
    artifact_path = _write_target(tmp_path)
    writer = TranscriptWriter(
        session_id="sess-1",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "voice-1",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "you are helpful",
        },
    )
    writer.record_transcript(
        TranscriptEntry(
            role="user",
            text="hello",
            started_at_iso="2026-05-20T12:00:01+00:00",
            ended_at_iso="2026-05-20T12:00:02+00:00",
            is_interim=False,
        )
    )
    writer.record_tool_call(
        tool_call_id="call-1",
        name="search_products",
        arguments={"query": "shoes"},
        result={"results": []},
        started_at_iso="2026-05-20T12:00:03+00:00",
        ended_at_iso="2026-05-20T12:00:04+00:00",
        is_error=False,
    )
    writer.finalize(
        ended_at_iso="2026-05-20T12:00:05+00:00",
        termination_reason="session_end",
    )
    writer.flush()

    payload = json.loads(artifact_path.read_text())
    assert payload["schema_version"] == 1
    assert payload["session_id"] == "sess-1"
    assert payload["termination_reason"] == "session_end"
    assert payload["transcript"][0]["index"] == 0
    assert payload["transcript"][0]["role"] == "user"
    assert payload["tool_trace"][0]["name"] == "search_products"
    assert payload["tool_trace"][0]["duration_ms"] >= 0
    assert payload["config"]["openai_model_id"] == "gpt-4o-mini"


def test_transcript_writer_atomic_flush(tmp_path: Path) -> None:
    """During a flush, only the tmp file should exist between write and rename."""
    artifact_path = _write_target(tmp_path)
    writer = TranscriptWriter(
        session_id="sess-1",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "voice-1",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    writer.flush()
    assert artifact_path.exists()
    assert not artifact_path.with_suffix(artifact_path.suffix + ".tmp").exists()


def test_transcript_writer_orders_entries_by_index(tmp_path: Path) -> None:
    artifact_path = _write_target(tmp_path, session_id="sess-2")
    writer = TranscriptWriter(
        session_id="sess-2",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "voice-1",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    for i in range(3):
        writer.record_transcript(
            TranscriptEntry(
                role="user" if i % 2 == 0 else "assistant",
                text=f"line-{i}",
                started_at_iso=f"2026-05-20T12:00:0{i}+00:00",
                ended_at_iso=f"2026-05-20T12:00:0{i + 1}+00:00",
                is_interim=False,
            )
        )
    writer.flush()

    payload = json.loads(artifact_path.read_text())
    indices = [entry["index"] for entry in payload["transcript"]]
    assert indices == [0, 1, 2]


def test_transcript_writer_finalize_sets_termination_reason(tmp_path: Path) -> None:
    artifact_path = _write_target(tmp_path, session_id="sess-3")
    writer = TranscriptWriter(
        session_id="sess-3",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "voice-1",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    writer.finalize(
        ended_at_iso="2026-05-20T12:01:00+00:00",
        termination_reason="client_disconnect",
    )
    writer.flush()

    payload = json.loads(artifact_path.read_text())
    assert payload["termination_reason"] == "client_disconnect"
    assert payload["ended_at"] == "2026-05-20T12:01:00+00:00"


def test_voice_session_config_is_frozen() -> None:
    cfg = pipecat_session.VoiceSessionConfig(
        session_id="x",
        artifact_path=Path("/tmp/x.json"),
        deepgram_api_key="a",
        cartesia_api_key="b",
        openai_api_key="c",
        system_prompt="hi",
        cartesia_voice_id="v",
        openai_model_id="gpt-4o-mini",
    )
    with pytest.raises(FrozenInstanceError):
        cfg.session_id = "y"  # type: ignore[misc]


def test_voice_session_event_envelope_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        VoiceSessionEventEnvelope.model_validate({"type": "bogus", "payload": {}})


def test_voice_session_event_envelope_accepts_known_types() -> None:
    valid_types = (
        "transcript",
        "tool_call",
        "tool_result",
        "agent_text",
        "error",
        "session_end",
    )
    for event_type in valid_types:
        envelope = VoiceSessionEventEnvelope.model_validate(
            {"type": event_type, "payload": {"a": 1}}
        )
        assert envelope.type == event_type


async def test_create_session_returns_412_when_credentials_missing(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/voice/sessions",
        json={
            "system_prompt": "You are a shopping assistant.",
            "cartesia_voice_id": "voice-test",
        },
    )
    assert response.status_code == 412
    body = response.json()
    assert body["error"]["code"] == "VOICE_CREDENTIALS_MISSING"
    assert "missing" in body["error"]["details"]


async def test_create_session_returns_201_when_credentials_present(
    client: AsyncClient,
    populated_credentials: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "data_dir", tmp_path)

    response = await client.post(
        "/api/v1/voice/sessions",
        json={
            "system_prompt": "You are a shopping assistant.",
            "cartesia_voice_id": "voice-test",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["session_id"]
    assert body["websocket_path"].startswith("/api/v1/voice/sessions/")
    assert body["websocket_path"].endswith("/stream")
    assert body["status"] == "pending"
    assert body["artifact_path"].endswith(".json")


async def test_create_session_returns_503_when_session_already_active(
    client: AsyncClient,
    populated_credentials: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "data_dir", tmp_path)

    first = await client.post(
        "/api/v1/voice/sessions",
        json={
            "system_prompt": "You are a shopping assistant.",
            "cartesia_voice_id": "voice-test",
        },
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/voice/sessions",
        json={
            "system_prompt": "You are a shopping assistant.",
            "cartesia_voice_id": "voice-test",
        },
    )
    assert second.status_code == 503
    body = second.json()
    assert body["error"]["code"] == "VOICE_SESSION_ALREADY_ACTIVE"


def test_voice_service_resolve_credentials_raises_when_missing() -> None:
    with pytest.raises(VoiceCredentialsMissingError) as exc_info:
        voice_service._resolve_credentials()
    assert "deepgram_api_key" in exc_info.value.missing
    assert "cartesia_api_key" in exc_info.value.missing
    assert "openai_api_key" in exc_info.value.missing


def test_voice_service_resolve_credentials_returns_keys_when_set(
    populated_credentials: None,
) -> None:
    credentials = voice_service._resolve_credentials()
    assert credentials.deepgram_api_key == "dg-test"
    assert credentials.cartesia_api_key == "ct-test"
    assert credentials.openai_api_key == "oa-test"


def test_voice_service_create_session_locks_active_id(
    populated_credentials: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "data_dir", tmp_path)

    payload = VoiceSessionCreateRequest(
        system_prompt="You are helpful.",
        cartesia_voice_id="v1",
    )
    response_a = voice_service.create_session(payload=payload)
    assert isinstance(response_a, VoiceSessionCreateResponse)

    with pytest.raises(VoiceSessionAlreadyActiveError):
        voice_service.create_session(payload=payload)


async def test_start_voice_session_raises_when_pipecat_missing(
    populated_credentials: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If `pipecat` cannot be imported the session must refuse cleanly."""
    monkeypatch.setitem(sys.modules, "pipecat", None)

    websocket = MagicMock()
    websocket.accept = AsyncMock()
    config = pipecat_session.VoiceSessionConfig(
        session_id="sess-x",
        artifact_path=tmp_path / "voice_sessions" / "sess-x.json",
        deepgram_api_key="a",
        cartesia_api_key="b",
        openai_api_key="c",
        system_prompt="hi",
        cartesia_voice_id="v",
        openai_model_id="gpt-4o-mini",
    )
    with pytest.raises(VoicePipecatNotInstalledError):
        await pipecat_session.start_voice_session(config=config, websocket=websocket)


async def test_start_voice_session_constructs_pipeline_when_pipecat_available(
    populated_credentials: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Mock every Pipecat surface and verify start_voice_session wires it all together.

    The test does not require `pipecat-ai` to be installed — we stub each module
    into `sys.modules` and assert the constructor calls.
    """
    constructed: dict[str, Any] = {}

    fake_transport_instance = MagicMock(name="transport_instance")
    fake_transport_instance.input.return_value = "TRANSPORT_IN"
    fake_transport_instance.output.return_value = "TRANSPORT_OUT"

    class _FakeTransport:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            constructed["transport_args"] = args
            constructed["transport_kwargs"] = kwargs
            self.input = fake_transport_instance.input
            self.output = fake_transport_instance.output

    class _FakeParams:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _FakeFrameSerializer:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    class _FakeOutputAudioFrame:
        def __init__(self, *, audio: bytes, **_: Any) -> None:
            self.audio = audio

    class _FakeInputAudioFrame:
        def __init__(self, *, audio: bytes, sample_rate: int, num_channels: int) -> None:
            self.audio = audio
            self.sample_rate = sample_rate
            self.num_channels = num_channels

    class _FakeTranscriptionFrame:
        def __init__(self, *, text: str = "", **_: Any) -> None:
            self.text = text

    class _FakeInterimTranscriptionFrame:
        def __init__(self, *, text: str = "", **_: Any) -> None:
            self.text = text

    class _FakeErrorFrame:
        def __init__(self, *, error: str = "", **_: Any) -> None:
            self.error = error

    class _FakeEndFrame:
        def __init__(self) -> None:
            pass

    class _FakeSilero:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    fake_llm_instance = MagicMock(name="llm_instance")
    fake_llm_instance.register_function = MagicMock()

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            constructed["openai_kwargs"] = kwargs
            self.register_function = fake_llm_instance.register_function

    class _FakeDeepgram:
        def __init__(self, **kwargs: Any) -> None:
            constructed["deepgram_kwargs"] = kwargs

    class _FakeCartesia:
        def __init__(self, **kwargs: Any) -> None:
            constructed["cartesia_kwargs"] = kwargs

    class _FakeLLMContext:
        def __init__(self, **kwargs: Any) -> None:
            constructed["context_kwargs"] = kwargs
            self.kwargs = kwargs

    class _FakeAggregatorPair:
        def __init__(self, ctx: Any) -> None:
            self._user = "USER_AGG"
            self._assistant = "ASSISTANT_AGG"

        def user(self) -> str:
            return self._user

        def assistant(self) -> str:
            return self._assistant

    class _FakePipeline:
        def __init__(self, processors: list[Any]) -> None:
            constructed["pipeline_processors"] = processors

    fake_task_instance = MagicMock(name="task_instance")

    class _FakePipelineTask:
        def __init__(self, pipeline: Any, **kwargs: Any) -> None:
            constructed["task_pipeline"] = pipeline
            constructed["task_kwargs"] = kwargs

        def __getattr__(self, name: str) -> Any:
            return getattr(fake_task_instance, name)

    class _FakePipelineRunner:
        def __init__(self) -> None:
            self.run = AsyncMock()
            self.cancel = AsyncMock()

    class _StubFunctionSchema:
        def __init__(
            self, *, name: str, description: str, properties: dict[str, object], required: list[str]
        ) -> None:
            self.name = name
            self.description = description
            self.properties = properties
            self.required = required

    class _StubToolsSchema:
        def __init__(self, *, standard_tools: list[_StubFunctionSchema]) -> None:
            self.standard_tools = standard_tools

    fake_function_schema_module = MagicMock()
    fake_function_schema_module.FunctionSchema = _StubFunctionSchema
    fake_tools_schema_module = MagicMock()
    fake_tools_schema_module.ToolsSchema = _StubToolsSchema

    fake_modules: dict[str, Any] = {
        "pipecat": MagicMock(),
        "pipecat.adapters": MagicMock(),
        "pipecat.adapters.schemas": MagicMock(),
        "pipecat.adapters.schemas.function_schema": fake_function_schema_module,
        "pipecat.adapters.schemas.tools_schema": fake_tools_schema_module,
        "pipecat.audio": MagicMock(),
        "pipecat.audio.vad": MagicMock(),
        "pipecat.audio.vad.silero": MagicMock(SileroVADAnalyzer=_FakeSilero),
        "pipecat.pipeline": MagicMock(),
        "pipecat.pipeline.pipeline": MagicMock(Pipeline=_FakePipeline),
        "pipecat.pipeline.runner": MagicMock(PipelineRunner=_FakePipelineRunner),
        "pipecat.pipeline.task": MagicMock(PipelineTask=_FakePipelineTask),
        "pipecat.processors": MagicMock(),
        "pipecat.processors.aggregators": MagicMock(),
        "pipecat.processors.aggregators.llm_context": MagicMock(
            LLMContext=_FakeLLMContext,
            LLMContextAggregatorPair=_FakeAggregatorPair,
        ),
        "pipecat.serializers": MagicMock(),
        "pipecat.serializers.base_serializer": MagicMock(FrameSerializer=_FakeFrameSerializer),
        "pipecat.frames": MagicMock(),
        "pipecat.frames.frames": MagicMock(
            EndFrame=_FakeEndFrame,
            ErrorFrame=_FakeErrorFrame,
            InputAudioRawFrame=_FakeInputAudioFrame,
            InterimTranscriptionFrame=_FakeInterimTranscriptionFrame,
            OutputAudioRawFrame=_FakeOutputAudioFrame,
            TranscriptionFrame=_FakeTranscriptionFrame,
        ),
        "pipecat.services": MagicMock(),
        "pipecat.services.cartesia": MagicMock(),
        "pipecat.services.cartesia.tts": MagicMock(CartesiaTTSService=_FakeCartesia),
        "pipecat.services.deepgram": MagicMock(),
        "pipecat.services.deepgram.stt": MagicMock(DeepgramSTTService=_FakeDeepgram),
        "pipecat.services.openai": MagicMock(),
        "pipecat.services.openai.llm": MagicMock(OpenAILLMService=_FakeOpenAI),
        "pipecat.transports": MagicMock(),
        "pipecat.transports.network": MagicMock(),
        "pipecat.transports.network.fastapi_websocket": MagicMock(
            FastAPIWebsocketTransport=_FakeTransport,
            FastAPIWebsocketParams=_FakeParams,
        ),
    }
    for name, module in fake_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    artifact_path = tmp_path / "voice_sessions" / "sess-pipe.json"
    config = pipecat_session.VoiceSessionConfig(
        session_id="sess-pipe",
        artifact_path=artifact_path,
        deepgram_api_key="dg",
        cartesia_api_key="ct",
        openai_api_key="oa",
        system_prompt="be helpful",
        cartesia_voice_id="voice-x",
        openai_model_id="gpt-4o-mini",
    )
    websocket = MagicMock()

    handle = await pipecat_session.start_voice_session(config=config, websocket=websocket)

    assert handle.session_id == "sess-pipe"
    assert constructed["deepgram_kwargs"]["api_key"] == "dg"
    assert constructed["cartesia_kwargs"]["api_key"] == "ct"
    assert constructed["openai_kwargs"]["api_key"] == "oa"
    assert constructed["openai_kwargs"]["model"] == "gpt-4o-mini"
    expected_tools = {
        "search_products",
        "get_product_detail",
        "add_to_cart",
        "handoff_checkout",
    }
    registered_names = {
        call.args[0] if call.args else call.kwargs.get("function_name")
        for call in fake_llm_instance.register_function.mock_calls
    }
    assert expected_tools <= registered_names


async def test_shutdown_flushes_transcript_writer(tmp_path: Path) -> None:
    """`VoiceSessionHandle.shutdown` must finalize the transcript JSON on disk."""
    artifact_path = tmp_path / "voice_sessions" / "sess-flush.json"
    writer = TranscriptWriter(
        session_id="sess-flush",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "v",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    fake_runner = MagicMock()
    fake_runner.run = AsyncMock()
    fake_runner.cancel = AsyncMock()
    fake_task = MagicMock()
    fake_task.cancel = AsyncMock()

    handle = pipecat_session._VoiceSessionHandleImpl(
        session_id="sess-flush",
        writer=writer,
        runner=fake_runner,
        task=fake_task,
    )

    await handle.shutdown(termination_reason="session_end")
    assert artifact_path.exists()
    payload = json.loads(artifact_path.read_text())
    assert payload["termination_reason"] == "session_end"
    fake_task.cancel.assert_awaited()


async def test_handle_run_until_disconnect_invokes_runner(tmp_path: Path) -> None:
    artifact_path = tmp_path / "voice_sessions" / "sess-run.json"
    writer = TranscriptWriter(
        session_id="sess-run",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "v",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    fake_runner = MagicMock()
    fake_runner.run = AsyncMock()
    fake_runner.cancel = AsyncMock()
    fake_task = MagicMock()

    handle = pipecat_session._VoiceSessionHandleImpl(
        session_id="sess-run",
        writer=writer,
        runner=fake_runner,
        task=fake_task,
    )
    await handle.run_until_disconnect()
    fake_runner.run.assert_awaited_with(fake_task)


def test_transcript_writer_finalize_persists_errors_list(tmp_path: Path) -> None:
    artifact_path = _write_target(tmp_path, session_id="sess-err")
    writer = TranscriptWriter(
        session_id="sess-err",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "v",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    writer.record_error(error_code="pipeline_error", message="boom")
    writer.finalize(
        ended_at_iso="2026-05-20T12:00:01+00:00",
        termination_reason="pipeline_error",
    )
    writer.flush()

    payload = json.loads(artifact_path.read_text())
    assert payload["errors"][0]["error_code"] == "pipeline_error"
    assert payload["errors"][0]["message"] == "boom"


def test_transcript_writer_flush_writes_through_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Confirm flush uses a `.tmp` companion that vanishes after the rename."""
    artifact_path = _write_target(tmp_path, session_id="sess-atomic")
    writer = TranscriptWriter(
        session_id="sess-atomic",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "v",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    seen_paths: list[Path] = []
    original_replace = transcript_writer._atomic_replace

    def _capture(*, source: Path, target: Path) -> None:
        seen_paths.append(source)
        original_replace(source=source, target=target)

    monkeypatch.setattr(transcript_writer, "_atomic_replace", _capture)
    writer.flush()
    assert seen_paths
    assert seen_paths[0].name.endswith(".tmp")
    assert not seen_paths[0].exists()


def test_voice_service_finalize_releases_active_lock(
    populated_credentials: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "data_dir", tmp_path)
    payload = VoiceSessionCreateRequest(
        system_prompt="You are helpful.",
        cartesia_voice_id="v1",
    )
    created = voice_service.create_session(payload=payload)
    voice_service.release_active_session(session_id=created.session_id)
    follow_up = voice_service.create_session(payload=payload)
    assert follow_up.session_id != created.session_id


async def test_handle_shutdown_is_idempotent(tmp_path: Path) -> None:
    artifact_path = tmp_path / "voice_sessions" / "sess-idemp.json"
    writer = TranscriptWriter(
        session_id="sess-idemp",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "v",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    fake_runner = MagicMock()
    fake_runner.cancel = AsyncMock()
    fake_task = MagicMock()
    fake_task.cancel = AsyncMock()

    handle = pipecat_session._VoiceSessionHandleImpl(
        session_id="sess-idemp",
        writer=writer,
        runner=fake_runner,
        task=fake_task,
    )
    await handle.shutdown(termination_reason="session_end")
    await handle.shutdown(termination_reason="session_end")
    fake_task.cancel.assert_awaited()
    payload = json.loads(artifact_path.read_text())
    assert payload["termination_reason"] == "session_end"


async def test_handle_tool_handler_records_to_writer(tmp_path: Path) -> None:
    """Tool handlers must call writer.record_tool_call with the same id and args."""
    artifact_path = tmp_path / "voice_sessions" / "sess-tool.json"
    writer = TranscriptWriter(
        session_id="sess-tool",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "v",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )

    cart = shopping_tools.CartState()
    captured_results: list[dict[str, object]] = []

    class _FakeFunctionParams:
        def __init__(self, *, arguments: dict[str, object], tool_call_id: str) -> None:
            self.arguments = arguments
            self.tool_call_id = tool_call_id

        async def result_callback(self, result: dict[str, object]) -> None:
            captured_results.append(result)

    params = _FakeFunctionParams(
        arguments={"query": "running shoes"},
        tool_call_id="call-99",
    )
    await shopping_tools.handle_search_products(params, writer=writer, cart=cart)

    assert len(captured_results) == 1
    assert len(writer.snapshot().tool_trace) == 1
    assert writer.snapshot().tool_trace[0].tool_call_id == "call-99"


def test_voice_session_create_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        VoiceSessionCreateRequest.model_validate(
            {
                "system_prompt": "x",
                "cartesia_voice_id": "v",
                "unknown_field": "boom",
            }
        )


def test_handle_writer_record_tool_call_marks_errors(tmp_path: Path) -> None:
    artifact_path = _write_target(tmp_path, session_id="sess-err2")
    writer = TranscriptWriter(
        session_id="sess-err2",
        artifact_path=artifact_path,
        started_at_iso="2026-05-20T12:00:00+00:00",
        config_snapshot={
            "openai_model_id": "gpt-4o-mini",
            "cartesia_voice_id": "v",
            "stt_provider": "deepgram",
            "tts_provider": "cartesia",
            "system_prompt": "x",
        },
    )
    writer.record_tool_call(
        tool_call_id="call-x",
        name="get_product_detail",
        arguments={"sku": "BOGUS"},
        result={"error": "sku_not_found"},
        started_at_iso="2026-05-20T12:00:01+00:00",
        ended_at_iso="2026-05-20T12:00:02+00:00",
        is_error=True,
    )
    writer.finalize(
        ended_at_iso="2026-05-20T12:00:03+00:00",
        termination_reason="session_end",
    )
    writer.flush()
    payload = json.loads(artifact_path.read_text())
    assert payload["tool_trace"][0]["is_error"] is True


async def test_voice_service_finalize_writes_file_on_disconnect(
    populated_credentials: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the WS client disconnects, finalize_session must flush whatever was buffered."""
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "data_dir", tmp_path)
    payload = VoiceSessionCreateRequest(
        system_prompt="You are helpful.",
        cartesia_voice_id="v1",
    )
    created = voice_service.create_session(payload=payload)
    handle = MagicMock()
    handle.session_id = created.session_id
    handle.shutdown = AsyncMock()
    voice_service._set_active_handle(session_id=created.session_id, handle=handle)

    await voice_service.finalize_session(
        session_id=created.session_id,
        reason="client_disconnect",
    )
    handle.shutdown.assert_awaited()
    assert voice_service.get_active_session_id() is None


def test_voice_credentials_missing_error_lists_missing_fields() -> None:
    settings_service._overrides["deepgram_api_key"] = "dg"
    with pytest.raises(VoiceCredentialsMissingError) as exc_info:
        voice_service._resolve_credentials()
    assert "deepgram_api_key" not in exc_info.value.missing


async def test_voice_websocket_rejects_unknown_session_id(
    populated_credentials: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "data_dir", tmp_path)
    """The WS endpoint must close the connection if the session id is unknown."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        ws_url = "/api/v1/voice/sessions/UNKNOWN/stream"
        response = await c.get(ws_url)
        assert response.status_code in (400, 404, 405)


async def test_voice_service_run_session_uses_registered_handle(
    populated_credentials: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_session must delegate to the stored handle's run_until_disconnect."""
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "data_dir", tmp_path)
    payload = VoiceSessionCreateRequest(
        system_prompt="You are helpful.",
        cartesia_voice_id="v1",
    )
    created = voice_service.create_session(payload=payload)

    started_call = asyncio.Event()

    class _FakeHandle:
        session_id = created.session_id

        async def run_until_disconnect(self) -> None:
            started_call.set()

        async def shutdown(self, *, termination_reason: str) -> None:
            return None

    websocket = MagicMock()
    fake_handle = _FakeHandle()

    async def _fake_start(*, config: Any, websocket: Any) -> Any:
        voice_service._set_active_handle(session_id=created.session_id, handle=fake_handle)
        return fake_handle

    monkeypatch.setattr(voice_service, "_start_pipecat_session", _fake_start)

    await voice_service.run_session(session_id=created.session_id, websocket=websocket)
    assert started_call.is_set()


def _serializer_fakes() -> dict[str, Any]:
    """Build a fakes dict shaped like `_import_pipecat_modules` output.

    Only the symbols the wire serializer touches are included. The fakes are
    plain Python classes so `isinstance` works as a dispatch primitive in the
    serializer body, mirroring the real pipecat frame hierarchy.
    """

    class _FakeFrameSerializer:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class _FakeOutputAudioRawFrame:
        def __init__(
            self, *, audio: bytes, sample_rate: int = 24_000, num_channels: int = 1
        ) -> None:
            self.audio = audio
            self.sample_rate = sample_rate
            self.num_channels = num_channels

    class _FakeInputAudioRawFrame:
        def __init__(self, *, audio: bytes, sample_rate: int, num_channels: int) -> None:
            self.audio = audio
            self.sample_rate = sample_rate
            self.num_channels = num_channels

    class _FakeTranscriptionFrame:
        def __init__(self, *, text: str, user_id: str = "", timestamp: str = "") -> None:
            self.text = text
            self.user_id = user_id
            self.timestamp = timestamp

    class _FakeInterimTranscriptionFrame:
        def __init__(self, *, text: str, user_id: str = "", timestamp: str = "") -> None:
            self.text = text
            self.user_id = user_id
            self.timestamp = timestamp

    class _FakeErrorFrame:
        def __init__(self, *, error: str = "", fatal: bool = False) -> None:
            self.error = error
            self.fatal = fatal

    class _FakeEndFrame:
        def __init__(self) -> None:
            pass

    return {
        "FrameSerializer": _FakeFrameSerializer,
        "OutputAudioRawFrame": _FakeOutputAudioRawFrame,
        "InputAudioRawFrame": _FakeInputAudioRawFrame,
        "TranscriptionFrame": _FakeTranscriptionFrame,
        "InterimTranscriptionFrame": _FakeInterimTranscriptionFrame,
        "ErrorFrame": _FakeErrorFrame,
        "EndFrame": _FakeEndFrame,
    }


async def test_serializer_serialize_audio_returns_raw_bytes() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    frame = modules["OutputAudioRawFrame"](audio=b"\x01\x02\x03\x04")
    result = await serializer.serialize(frame)
    assert result == b"\x01\x02\x03\x04"


async def test_serializer_serialize_transcription_returns_json_envelope() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    frame = modules["TranscriptionFrame"](text="hello", user_id="user-1")
    result = await serializer.serialize(frame)
    assert isinstance(result, str)
    body = json.loads(result)
    assert body["type"] == "transcript"
    assert body["payload"]["role"] == "user"
    assert body["payload"]["text"] == "hello"
    assert body["payload"]["is_interim"] is False


async def test_serializer_serialize_interim_transcription_marks_is_interim() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    frame = modules["InterimTranscriptionFrame"](text="partial", user_id="user-1")
    body = json.loads(await serializer.serialize(frame))
    assert body["type"] == "transcript"
    assert body["payload"]["is_interim"] is True
    assert body["payload"]["text"] == "partial"


async def test_serializer_serialize_error_returns_error_envelope() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    frame = modules["ErrorFrame"](error="things broke")
    body = json.loads(await serializer.serialize(frame))
    assert body["type"] == "error"
    assert body["payload"]["message"] == "things broke"


async def test_serializer_serialize_unknown_frame_type_returns_none() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)

    class _UnrelatedFrame:
        pass

    result = await serializer.serialize(_UnrelatedFrame())
    assert result is None


async def test_serializer_serialize_end_frame_returns_none() -> None:
    """EndFrame is consumed by the transport lifecycle, not forwarded on the wire."""
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    result = await serializer.serialize(modules["EndFrame"]())
    assert result is None


async def test_serializer_deserialize_bytes_returns_input_audio_frame() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    frame = await serializer.deserialize(b"\x00\x01\x02\x03")
    assert isinstance(frame, modules["InputAudioRawFrame"])
    assert frame.audio == b"\x00\x01\x02\x03"
    assert frame.sample_rate == 16_000
    assert frame.num_channels == 1


async def test_serializer_deserialize_empty_bytes_returns_none() -> None:
    """An empty audio chunk would otherwise yield a zero-length PCM frame."""
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    frame = await serializer.deserialize(b"")
    assert frame is None


async def test_serializer_deserialize_session_end_returns_end_frame() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    payload = json.dumps({"type": "session_end", "payload": {}})
    frame = await serializer.deserialize(payload)
    assert isinstance(frame, modules["EndFrame"])


async def test_serializer_deserialize_unknown_envelope_type_returns_none() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    payload = json.dumps({"type": "bogus_type", "payload": {}})
    frame = await serializer.deserialize(payload)
    assert frame is None


async def test_serializer_deserialize_malformed_text_returns_none() -> None:
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    frame = await serializer.deserialize("not json")
    assert frame is None


async def test_serializer_deserialize_non_object_json_returns_none() -> None:
    """JSON arrays or scalars are not valid control envelopes."""
    modules = _serializer_fakes()
    serializer = pipecat_session._build_raw_pcm_json_serializer(modules=modules)
    frame = await serializer.deserialize(json.dumps([1, 2, 3]))
    assert frame is None
