from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.cli import voice_smoke
from app.services import settings_service


@pytest.fixture(autouse=True)
def reset_settings_overrides() -> Iterator[None]:
    settings_service._overrides.clear()
    yield
    settings_service._overrides.clear()


@pytest.fixture
def populated_credentials() -> None:
    settings_service._overrides["deepgram_api_key"] = "dg-test"
    settings_service._overrides["cartesia_api_key"] = "ct-test"
    settings_service._overrides["openai_api_key"] = "oa-test"


@pytest.fixture
def isolate_settings_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear any AppConfig fallbacks for the three voice keys.

    The smoke checker reads from `AppConfig` when the override store is empty;
    if a developer machine has these keys in `.env` the "missing creds" test
    would otherwise pass them as set. Forcing None here keeps the test
    deterministic regardless of local environment.
    """
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "deepgram_api_key", None)
    monkeypatch.setattr(cfg_module.settings, "cartesia_api_key", None)
    monkeypatch.setattr(cfg_module.settings, "openai_api_key", None)


def _install_fake_pipecat_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the exact set of pipecat submodules `_import_pipecat_modules` touches."""
    fake_modules: dict[str, Any] = {
        "pipecat": MagicMock(),
        "pipecat.audio": MagicMock(),
        "pipecat.audio.vad": MagicMock(),
        "pipecat.audio.vad.silero": MagicMock(SileroVADAnalyzer=MagicMock()),
        "pipecat.frames": MagicMock(),
        "pipecat.frames.frames": MagicMock(
            EndFrame=MagicMock(),
            ErrorFrame=MagicMock(),
            InputAudioRawFrame=MagicMock(),
            InterimTranscriptionFrame=MagicMock(),
            OutputAudioRawFrame=MagicMock(),
            TranscriptionFrame=MagicMock(),
        ),
        "pipecat.pipeline": MagicMock(),
        "pipecat.pipeline.pipeline": MagicMock(Pipeline=MagicMock()),
        "pipecat.pipeline.runner": MagicMock(PipelineRunner=MagicMock()),
        "pipecat.pipeline.task": MagicMock(PipelineTask=MagicMock()),
        "pipecat.processors": MagicMock(),
        "pipecat.processors.aggregators": MagicMock(),
        "pipecat.processors.aggregators.llm_context": MagicMock(
            LLMContext=MagicMock(),
        ),
        "pipecat.processors.aggregators.llm_response_universal": MagicMock(
            LLMContextAggregatorPair=MagicMock(),
        ),
        "pipecat.serializers": MagicMock(),
        "pipecat.serializers.base_serializer": MagicMock(FrameSerializer=MagicMock()),
        "pipecat.services": MagicMock(),
        "pipecat.services.cartesia": MagicMock(),
        "pipecat.services.cartesia.tts": MagicMock(CartesiaTTSService=MagicMock()),
        "pipecat.services.deepgram": MagicMock(),
        "pipecat.services.deepgram.stt": MagicMock(DeepgramSTTService=MagicMock()),
        "pipecat.services.openai": MagicMock(),
        "pipecat.services.openai.llm": MagicMock(OpenAILLMService=MagicMock()),
        "pipecat.transports": MagicMock(),
        "pipecat.transports.websocket": MagicMock(),
        "pipecat.transports.websocket.fastapi": MagicMock(
            FastAPIWebsocketParams=MagicMock(),
            FastAPIWebsocketTransport=MagicMock(),
        ),
    }
    for name, module in fake_modules.items():
        monkeypatch.setitem(sys.modules, name, module)


async def test_voice_smoke_succeeds_when_creds_and_pipecat_present(
    populated_credentials: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_pipecat_modules(monkeypatch)

    exit_code = await voice_smoke.run(args=MagicMock())

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "deepgram_api_key: set" in captured.out
    assert "cartesia_api_key: set" in captured.out
    assert "openai_api_key: set" in captured.out
    assert "pipecat-ai modules importable" in captured.out
    assert "success: voice stack ready" in captured.out


async def test_voice_smoke_fails_when_creds_missing_and_pipecat_blocked(
    isolate_settings_keys: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setitem(sys.modules, "pipecat", None)

    exit_code = await voice_smoke.run(args=MagicMock())

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "deepgram_api_key: missing" in captured.err
    assert "cartesia_api_key: missing" in captured.err
    assert "openai_api_key: missing" in captured.err
    assert "pipecat-ai not installed" in captured.err
    assert "deepgram_api_key" in captured.err
    assert "pipecat-ai" in captured.err


async def test_voice_smoke_fails_when_only_pipecat_missing(
    populated_credentials: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setitem(sys.modules, "pipecat", None)

    exit_code = await voice_smoke.run(args=MagicMock())

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "deepgram_api_key: set" in captured.out
    assert "cartesia_api_key: set" in captured.out
    assert "openai_api_key: set" in captured.out
    assert "pipecat-ai not installed" in captured.err
    assert 'pip install -e ".[voice]"' in captured.err
