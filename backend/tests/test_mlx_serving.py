from __future__ import annotations

import asyncio
import json
import socket
import sys
import types
from pathlib import Path
from typing import Any

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.config_version import ConfigVersion
from app.models.project import Project
from app.models.run import Run


@pytest.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def reset_serving_registry() -> None:
    from app.services.cloud import mlx_serving_registry

    await mlx_serving_registry.shutdown_all()
    yield
    await mlx_serving_registry.shutdown_all()


def _make_yaml_config(*, serving_model_id: str | None = None) -> str:
    model: dict[str, Any] = {
        "source": "huggingface",
        "model_id": "Qwen/Qwen2.5-1.5B-Instruct",
        "family": "causal_lm",
    }
    if serving_model_id is not None:
        model["serving_model_id"] = serving_model_id
    return yaml.safe_dump(
        {
            "project": {"name": "p", "mode": "single_user_local"},
            "model": model,
            "dataset": {
                "source": "huggingface",
                "dataset_id": "x",
            },
            "preprocessing": {},
            "training": {},
            "optimization": {},
            "adapters": {},
            "quantization": {},
            "observability": {},
            "ai_assistant": {},
            "execution": {},
            "checkpoint_retention": {},
            "introspection": {},
        }
    )


def test_mlx_serving_module_does_not_import_mlx_lm_eagerly() -> None:
    """The module must import cleanly without `mlx_lm` installed.

    Mirrors `test_training_dispatcher_does_not_import_modal_eagerly` — the lazy
    import contract is enforced by keeping `mlx_lm` references inside function
    bodies so base/local installs don't fail at module import.
    """
    import app.services.cloud.mlx_serving as ms

    assert "mlx_lm" not in ms.__dict__
    assert "mlx_lm" not in sys.modules or sys.modules["mlx_lm"] is not None


def test_mlx_serving_config_defaults_bind_to_loopback() -> None:
    from app.services.cloud.mlx_serving import MLXServingConfig

    cfg = MLXServingConfig(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    )
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 0
    assert cfg.adapter_path is None
    assert cfg.trust_remote_code is False
    assert cfg.log_level == "info"
    assert cfg.startup_timeout_seconds == 120


def test_mlx_serving_config_rejects_non_loopback_host() -> None:
    """Binding to 0.0.0.0 is forbidden — local serving is loopback-only."""
    from app.services.cloud.mlx_serving import MLXServingConfig

    with pytest.raises(ValueError, match="loopback"):
        MLXServingConfig(
            project_id="p1",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
            host="0.0.0.0",
        )


async def test_adapter_start_rejects_non_darwin_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.cloud import mlx_serving
    from app.services.cloud.mlx_serving import (
        MLXServingAdapter,
        MLXServingConfig,
        UnsupportedServingPlatformError,
    )

    monkeypatch.setattr(mlx_serving, "_current_system", lambda: "Linux")
    monkeypatch.setattr(mlx_serving, "_current_machine", lambda: "x86_64")

    adapter = MLXServingAdapter(
        config=MLXServingConfig(
            project_id="p1",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        )
    )

    with pytest.raises(UnsupportedServingPlatformError, match="arm64"):
        await adapter.start()


async def test_adapter_start_rejects_intel_mac(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.cloud import mlx_serving
    from app.services.cloud.mlx_serving import (
        MLXServingAdapter,
        MLXServingConfig,
        UnsupportedServingPlatformError,
    )

    monkeypatch.setattr(mlx_serving, "_current_system", lambda: "Darwin")
    monkeypatch.setattr(mlx_serving, "_current_machine", lambda: "x86_64")

    adapter = MLXServingAdapter(
        config=MLXServingConfig(
            project_id="p1",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        )
    )

    with pytest.raises(UnsupportedServingPlatformError):
        await adapter.start()


async def test_adapter_start_raises_when_mlx_lm_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.cloud import mlx_serving
    from app.services.cloud.mlx_serving import (
        MLXNotInstalledError,
        MLXServingAdapter,
        MLXServingConfig,
    )

    monkeypatch.setattr(mlx_serving, "_current_system", lambda: "Darwin")
    monkeypatch.setattr(mlx_serving, "_current_machine", lambda: "arm64")

    def _fail_import() -> object:
        raise ImportError("No module named 'mlx_lm'")

    monkeypatch.setattr(mlx_serving, "_import_mlx_lm", _fail_import)

    adapter = MLXServingAdapter(
        config=MLXServingConfig(
            project_id="p1",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        )
    )

    with pytest.raises(MLXNotInstalledError):
        await adapter.start()


async def test_adapter_start_rejects_any_adapter_against_non_mlx_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mlx_lm.server cannot host a HuggingFace base regardless of adapter shape.

    The registry converts peft → MLX format upstream, but the adapter itself
    still refuses an adapter_path against a non-MLX serving_model_id because
    the converted weights would never match the model architecture loaded by
    mlx_lm.server.
    """
    from app.services.cloud import mlx_serving
    from app.services.cloud.mlx_serving import (
        AdapterConversionUnsupportedError,
        MLXServingAdapter,
        MLXServingConfig,
    )

    monkeypatch.setattr(mlx_serving, "_current_system", lambda: "Darwin")
    monkeypatch.setattr(mlx_serving, "_current_machine", lambda: "arm64")
    monkeypatch.setattr(mlx_serving, "_import_mlx_lm", lambda: types.ModuleType("mlx_lm"))

    adapter = MLXServingAdapter(
        config=MLXServingConfig(
            project_id="p1",
            serving_model_id="Qwen/Qwen2.5-1.5B-Instruct",
            adapter_path=Path("/tmp/run-checkpoint"),
        )
    )

    with pytest.raises(AdapterConversionUnsupportedError):
        await adapter.start()


def test_build_argv_includes_adapter_path_when_set() -> None:
    from app.services.cloud.mlx_serving import MLXServingConfig, build_server_argv

    cfg = MLXServingConfig(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=Path("/tmp/adapters/r1"),
        trust_remote_code=True,
    )
    argv = build_server_argv(config=cfg, port=12345)

    assert argv[0] == sys.executable
    assert "-m" in argv
    assert "mlx_lm.server" in argv
    assert "--model" in argv
    assert "mlx-community/Qwen2.5-1.5B-Instruct-4bit" in argv
    assert "--port" in argv
    assert "12345" in argv
    assert "--host" in argv
    assert "127.0.0.1" in argv
    assert "--adapter-path" in argv
    assert "/tmp/adapters/r1" in argv
    assert "--trust-remote-code" in argv


def test_build_argv_omits_adapter_when_unset() -> None:
    from app.services.cloud.mlx_serving import MLXServingConfig, build_server_argv

    cfg = MLXServingConfig(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    )
    argv = build_server_argv(config=cfg, port=10001)
    assert "--adapter-path" not in argv
    assert "--trust-remote-code" not in argv


def test_reserve_free_port_returns_available_port() -> None:
    from app.services.cloud.mlx_serving import reserve_free_port

    port = reserve_free_port(host="127.0.0.1")
    assert 1024 <= port <= 65535
    # Verify we can re-bind because reserve_free_port closed its probe.
    second = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    second.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        second.bind(("127.0.0.1", port))
    finally:
        second.close()


async def test_adapter_lifecycle_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """start spawns a subprocess, waits for /v1/models 200, then cancel terminates it."""
    from app.services.cloud import mlx_serving
    from app.services.cloud.mlx_serving import MLXServingAdapter, MLXServingConfig

    monkeypatch.setattr(mlx_serving, "_current_system", lambda: "Darwin")
    monkeypatch.setattr(mlx_serving, "_current_machine", lambda: "arm64")
    monkeypatch.setattr(mlx_serving, "_import_mlx_lm", lambda: types.ModuleType("mlx_lm"))
    monkeypatch.setattr(mlx_serving, "reserve_free_port", lambda *, host: 18080)

    fake_proc = _FakeSubprocess()

    async def _fake_spawn(*, argv: list[str], env: dict[str, str]) -> _FakeSubprocess:
        fake_proc.argv = argv
        return fake_proc

    monkeypatch.setattr(mlx_serving, "_spawn_subprocess", _fake_spawn)

    health_probe_calls: list[str] = []

    async def _fake_probe(*, base_url: str, timeout_s: float) -> bool:
        health_probe_calls.append(base_url)
        return True

    monkeypatch.setattr(mlx_serving, "_probe_models_endpoint", _fake_probe)

    adapter = MLXServingAdapter(
        config=MLXServingConfig(
            project_id="p1",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
            startup_timeout_seconds=2,
        )
    )

    await adapter.start()
    assert adapter.base_url == "http://127.0.0.1:18080"
    assert health_probe_calls == ["http://127.0.0.1:18080"]
    assert await adapter.is_alive() is True

    ready_event = await adapter.read_event()
    assert ready_event is not None
    assert ready_event["type"] == "serving_ready"
    assert ready_event["port"] == 18080

    await adapter.cancel()
    assert fake_proc.terminated is True
    assert await adapter.is_alive() is False


async def test_adapter_start_times_out_when_health_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.cloud import mlx_serving
    from app.services.cloud.mlx_serving import (
        MLXServerStartupTimeoutError,
        MLXServingAdapter,
        MLXServingConfig,
    )

    monkeypatch.setattr(mlx_serving, "_current_system", lambda: "Darwin")
    monkeypatch.setattr(mlx_serving, "_current_machine", lambda: "arm64")
    monkeypatch.setattr(mlx_serving, "_import_mlx_lm", lambda: types.ModuleType("mlx_lm"))
    monkeypatch.setattr(mlx_serving, "reserve_free_port", lambda *, host: 18081)

    fake_proc = _FakeSubprocess()

    async def _fake_spawn(*, argv: list[str], env: dict[str, str]) -> _FakeSubprocess:
        return fake_proc

    monkeypatch.setattr(mlx_serving, "_spawn_subprocess", _fake_spawn)

    async def _fake_probe(*, base_url: str, timeout_s: float) -> bool:
        return False

    monkeypatch.setattr(mlx_serving, "_probe_models_endpoint", _fake_probe)

    adapter = MLXServingAdapter(
        config=MLXServingConfig(
            project_id="p1",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
            startup_timeout_seconds=1,
        )
    )

    with pytest.raises(MLXServerStartupTimeoutError):
        await adapter.start()
    assert fake_proc.terminated is True


async def test_adapter_start_propagates_port_already_in_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.cloud import mlx_serving
    from app.services.cloud.mlx_serving import (
        MLXServingAdapter,
        MLXServingConfig,
        ServingStartupError,
    )

    monkeypatch.setattr(mlx_serving, "_current_system", lambda: "Darwin")
    monkeypatch.setattr(mlx_serving, "_current_machine", lambda: "arm64")
    monkeypatch.setattr(mlx_serving, "_import_mlx_lm", lambda: types.ModuleType("mlx_lm"))

    def _reserve_fails(*, host: str) -> int:
        raise OSError(48, "Address already in use")

    monkeypatch.setattr(mlx_serving, "reserve_free_port", _reserve_fails)

    adapter = MLXServingAdapter(
        config=MLXServingConfig(
            project_id="p1",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        )
    )

    with pytest.raises(ServingStartupError, match="port"):
        await adapter.start()


async def test_registry_starts_and_returns_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.cloud import mlx_serving_registry

    _patch_for_happy_path(monkeypatch)

    status = await mlx_serving_registry.start_serving(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=None,
        trust_remote_code=False,
    )
    assert status.state == "running"
    assert status.base_url == "http://127.0.0.1:18080"
    assert status.project_id == "p1"

    fetched = mlx_serving_registry.get_status(project_id="p1")
    assert fetched.state == "running"
    assert fetched.model_id == "mlx-community/Qwen2.5-1.5B-Instruct-4bit"

    await mlx_serving_registry.stop_serving(project_id="p1")
    after_stop = mlx_serving_registry.get_status(project_id="p1")
    assert after_stop.state == "stopped"


async def test_registry_get_status_evicts_dead_entry_and_reports_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subprocess that exits without going through stop_serving must surface as failed."""
    from app.services.cloud import mlx_serving_registry

    _patch_for_happy_path(monkeypatch)

    await mlx_serving_registry.start_serving(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=None,
        trust_remote_code=False,
    )

    entry = mlx_serving_registry._active["p1"]
    # Simulate the subprocess dying on its own (not via stop_serving).
    entry.adapter._state.proc._returncode = 137

    status = mlx_serving_registry.get_status(project_id="p1")
    assert status.state == "failed"
    assert status.last_error is not None
    assert "137" in status.last_error or "exited" in status.last_error

    # Stale entry must be removed so a subsequent start can claim capacity.
    assert "p1" not in mlx_serving_registry._active

    # Idempotent: a second get_status returns the stopped state cleanly.
    again = mlx_serving_registry.get_status(project_id="p1")
    assert again.state == "stopped"


async def test_registry_rejects_capacity_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.cloud import mlx_serving_registry
    from app.services.cloud.mlx_serving_registry import (
        ServingCapacityExceededError,
    )

    _patch_for_happy_path(monkeypatch)

    await mlx_serving_registry.start_serving(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=None,
        trust_remote_code=False,
    )

    with pytest.raises(ServingCapacityExceededError):
        await mlx_serving_registry.start_serving(
            project_id="p2",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
            adapter_path=None,
            trust_remote_code=False,
        )


async def test_registry_start_evicts_dead_entry_from_other_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead serve in project A must not block a new serve in project B.

    Without the start-time eviction, `_active` would still contain project A's
    stale entry — `len(_active) >= _MAX_CONCURRENT_SERVES` would be true and
    the new serve would be rejected even though project A's subprocess is gone.
    """
    from app.services.cloud import mlx_serving_registry

    _patch_for_happy_path(monkeypatch)

    await mlx_serving_registry.start_serving(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=None,
        trust_remote_code=False,
    )

    # Simulate p1's subprocess dying without going through stop_serving.
    mlx_serving_registry._active["p1"].adapter._state.proc._returncode = 137

    # New serve from p2 must succeed — the start sweep evicts the dead p1 entry
    # before the capacity check sees the count.
    status = await mlx_serving_registry.start_serving(
        project_id="p2",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=None,
        trust_remote_code=False,
    )
    assert status.state == "running"
    assert status.project_id == "p2"
    assert "p1" not in mlx_serving_registry._active
    assert "p2" in mlx_serving_registry._active


async def test_registry_restarts_when_called_for_same_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.cloud import mlx_serving_registry

    _patch_for_happy_path(monkeypatch)

    first = await mlx_serving_registry.start_serving(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=None,
        trust_remote_code=False,
    )
    started_at_first = first.started_at

    await asyncio.sleep(0.001)

    second = await mlx_serving_registry.start_serving(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=None,
        trust_remote_code=False,
    )
    assert second.state == "running"
    assert second.started_at >= started_at_first


async def test_post_serve_requires_serving_model_id(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_for_happy_path(monkeypatch)

    project_id = await _seed_project(db_session, serving_model_id=None)

    resp = await client.post(f"/api/v1/projects/{project_id}/serve", json={})
    body = resp.json()
    assert resp.status_code == 422, body
    assert body["error"]["code"] == "MODEL_NOT_CONFIGURED_FOR_SERVING"


async def test_post_serve_starts_from_explicit_model_id(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_for_happy_path(monkeypatch)

    project_id = await _seed_project(db_session, serving_model_id=None)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/serve",
        json={"serving_model_id": "mlx-community/Qwen2.5-1.5B-Instruct-4bit"},
    )
    body = resp.json()
    assert resp.status_code == 200, body
    assert body["status"]["state"] == "running"
    assert body["status"]["base_url"] == "http://127.0.0.1:18080"


async def test_post_serve_uses_config_serving_model_id_fallback(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_for_happy_path(monkeypatch)

    project_id = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    )
    resp = await client.post(f"/api/v1/projects/{project_id}/serve", json={})
    body = resp.json()
    assert resp.status_code == 200, body
    assert body["status"]["model_id"] == "mlx-community/Qwen2.5-1.5B-Instruct-4bit"


async def test_get_serve_returns_stopped_initially(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    project_id = await _seed_project(db_session, serving_model_id=None)
    resp = await client.get(f"/api/v1/projects/{project_id}/serve")
    body = resp.json()
    assert resp.status_code == 200, body
    assert body["state"] == "stopped"
    assert body["base_url"] is None


async def test_delete_serve_stops_running_server(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_for_happy_path(monkeypatch)

    project_id = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    )

    start_resp = await client.post(f"/api/v1/projects/{project_id}/serve", json={})
    assert start_resp.status_code == 200

    delete_resp = await client.delete(f"/api/v1/projects/{project_id}/serve")
    assert delete_resp.status_code == 204

    after = await client.get(f"/api/v1/projects/{project_id}/serve")
    assert after.json()["state"] == "stopped"


async def test_post_serve_returns_409_when_capacity_exceeded(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_for_happy_path(monkeypatch)

    project_p1 = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        name="p1",
    )
    project_p2 = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        name="p2",
    )

    first = await client.post(f"/api/v1/projects/{project_p1}/serve", json={})
    assert first.status_code == 200

    second = await client.post(f"/api/v1/projects/{project_p2}/serve", json={})
    body = second.json()
    assert second.status_code == 409, body
    assert body["error"]["code"] == "SERVING_CAPACITY_EXCEEDED"


async def test_post_serve_with_nonexistent_project_returns_404(
    client: AsyncClient,
) -> None:
    resp = await client.post("/api/v1/projects/missing-project/serve", json={})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


async def test_registry_converts_peft_adapter_when_base_is_mlx(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A peft adapter dir is rewritten into MLX layout before the supervisor starts."""
    from app.services.cloud import mlx_serving, mlx_serving_registry

    _patch_for_happy_path(monkeypatch)

    spawned_argv: list[list[str]] = []

    async def _capture_spawn(*, argv: list[str], env: dict[str, str]) -> _FakeSubprocess:
        spawned_argv.append(argv)
        return _FakeSubprocess()

    monkeypatch.setattr(mlx_serving, "_spawn_subprocess", _capture_spawn)

    peft_adapter = _write_synthetic_peft_adapter(directory=tmp_path / "checkpoint-final")

    await mlx_serving_registry.start_serving(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=peft_adapter,
        trust_remote_code=False,
    )

    converted_dir = peft_adapter.parent / "mlx-adapters" / peft_adapter.name
    assert (converted_dir / "adapters.safetensors").is_file()
    assert (converted_dir / "adapter_config.json").is_file()

    argv = spawned_argv[0]
    adapter_index = argv.index("--adapter-path")
    assert argv[adapter_index + 1] == str(converted_dir)


async def test_registry_rejects_peft_adapter_against_non_mlx_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """peft adapter + HF base must fail before any subprocess spawn attempt."""
    from app.services.cloud import mlx_serving, mlx_serving_registry
    from app.services.cloud.mlx_serving import AdapterConversionUnsupportedError

    _patch_for_happy_path(monkeypatch)

    async def _explode_spawn(*, argv: list[str], env: dict[str, str]) -> _FakeSubprocess:
        raise AssertionError("subprocess must not spawn when conversion is rejected")

    monkeypatch.setattr(mlx_serving, "_spawn_subprocess", _explode_spawn)

    peft_adapter = _write_synthetic_peft_adapter(directory=tmp_path / "checkpoint-final")

    with pytest.raises(AdapterConversionUnsupportedError, match="MLX-format base"):
        await mlx_serving_registry.start_serving(
            project_id="p1",
            serving_model_id="Qwen/Qwen2.5-1.5B-Instruct",
            adapter_path=peft_adapter,
            trust_remote_code=False,
        )


async def test_registry_surfaces_converter_rejection_as_unsupported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A QLoRA adapter dir must surface as ADAPTER_CONVERSION_UNSUPPORTED with reason."""
    from app.services.cloud import mlx_serving, mlx_serving_registry
    from app.services.cloud.mlx_serving import AdapterConversionUnsupportedError

    _patch_for_happy_path(monkeypatch)

    async def _explode_spawn(*, argv: list[str], env: dict[str, str]) -> _FakeSubprocess:
        raise AssertionError("subprocess must not spawn when conversion is rejected")

    monkeypatch.setattr(mlx_serving, "_spawn_subprocess", _explode_spawn)

    qlora_adapter = _write_synthetic_peft_adapter(
        directory=tmp_path / "qlora",
        config_overrides={"quantization_config": {"bnb_4bit_quant_type": "nf4"}},
    )

    with pytest.raises(AdapterConversionUnsupportedError) as exc_info:
        await mlx_serving_registry.start_serving(
            project_id="p1",
            serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
            adapter_path=qlora_adapter,
            trust_remote_code=False,
        )

    assert exc_info.value.reason is not None
    assert "QLoRA" in exc_info.value.reason


async def test_registry_passes_non_peft_adapter_path_through_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A directory that lacks the peft files is forwarded as-is to mlx_lm.server."""
    from app.services.cloud import mlx_serving, mlx_serving_registry

    _patch_for_happy_path(monkeypatch)

    captured_argv: list[list[str]] = []

    async def _capture_spawn(*, argv: list[str], env: dict[str, str]) -> _FakeSubprocess:
        captured_argv.append(argv)
        return _FakeSubprocess()

    monkeypatch.setattr(mlx_serving, "_spawn_subprocess", _capture_spawn)

    already_mlx = tmp_path / "mlx-adapter"
    already_mlx.mkdir()
    (already_mlx / "adapters.safetensors").write_bytes(b"")

    await mlx_serving_registry.start_serving(
        project_id="p1",
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        adapter_path=already_mlx,
        trust_remote_code=False,
    )

    argv = captured_argv[0]
    adapter_index = argv.index("--adapter-path")
    assert argv[adapter_index + 1] == str(already_mlx)
    assert not (already_mlx.parent / "mlx-adapters").exists()


async def test_post_serve_returns_404_when_run_id_unknown(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_for_happy_path(monkeypatch)
    project_id = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    )

    resp = await client.post(
        f"/api/v1/projects/{project_id}/serve",
        json={"run_id": "run-does-not-exist"},
    )
    body = resp.json()
    assert resp.status_code == 404, body
    assert body["error"]["code"] == "RUN_NOT_FOUND"
    assert body["error"]["details"]["run_id"] == "run-does-not-exist"


async def test_post_serve_returns_404_when_run_id_belongs_to_other_project(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run_id from sibling project must not load that project's checkpoint
    under the requesting project's serving config — the lookup is filtered by
    project_id so the cross-project leak surfaces as the same 404 the route
    returns for a truly-unknown run.
    """
    _patch_for_happy_path(monkeypatch)
    project_a = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        name="project-a",
    )
    project_b = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        name="project-b",
    )
    run_in_b = await _seed_run(
        db_session, project_id=project_b, last_checkpoint_path="/tmp/checkpoint-b"
    )

    resp = await client.post(
        f"/api/v1/projects/{project_a}/serve",
        json={"run_id": run_in_b},
    )
    body = resp.json()
    assert resp.status_code == 404, body
    assert body["error"]["code"] == "RUN_NOT_FOUND"
    assert body["error"]["details"]["run_id"] == run_in_b


async def test_post_serve_returns_422_when_run_has_no_checkpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_for_happy_path(monkeypatch)
    project_id = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    )
    run_id = await _seed_run(
        db_session, project_id=project_id, last_checkpoint_path=None
    )

    resp = await client.post(
        f"/api/v1/projects/{project_id}/serve",
        json={"run_id": run_id},
    )
    body = resp.json()
    assert resp.status_code == 422, body
    assert body["error"]["code"] == "NO_CHECKPOINT_FOR_SERVING"
    assert body["error"]["details"]["run_id"] == run_id


async def test_post_serve_passes_run_checkpoint_path_to_registry(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When run_id resolves to a checkpoint path, the registry sees that path."""
    from app.services.cloud import mlx_serving, mlx_serving_registry

    _patch_for_happy_path(monkeypatch)

    received_paths: list[Path | None] = []
    real_start_serving = mlx_serving_registry.start_serving

    async def _capture_start(**kwargs: Any) -> Any:
        received_paths.append(kwargs.get("adapter_path"))
        return await real_start_serving(**kwargs)

    monkeypatch.setattr(mlx_serving_registry, "start_serving", _capture_start)
    # Avoid touching disk inside the registry's conversion check.
    monkeypatch.setattr(mlx_serving, "_spawn_subprocess", _fake_spawn_noop)

    checkpoint_dir = tmp_path / "checkpoints" / "step-100"
    checkpoint_dir.mkdir(parents=True)
    project_id = await _seed_project(
        db_session,
        serving_model_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    )
    run_id = await _seed_run(
        db_session,
        project_id=project_id,
        last_checkpoint_path=str(checkpoint_dir),
    )

    resp = await client.post(
        f"/api/v1/projects/{project_id}/serve",
        json={"run_id": run_id},
    )
    assert resp.status_code == 200, resp.json()
    assert received_paths == [checkpoint_dir]


async def _fake_spawn_noop(*, argv: list[str], env: dict[str, str]) -> _FakeSubprocess:
    return _FakeSubprocess()


def _write_synthetic_peft_adapter(
    *,
    directory: Path,
    config_overrides: dict[str, Any] | None = None,
) -> Path:
    """Materialize a minimal peft LoRA adapter directory for registry tests."""
    import numpy as np
    from safetensors.numpy import save_file

    directory.mkdir(parents=True, exist_ok=True)
    config: dict[str, Any] = {
        "peft_type": "LORA",
        "task_type": "CAUSAL_LM",
        "r": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "target_modules": ["q_proj"],
        "bias": "none",
        "base_model_name_or_path": "Qwen/Qwen2.5-1.5B",
    }
    if config_overrides:
        config.update(config_overrides)
    (directory / "adapter_config.json").write_text(
        json.dumps(config, sort_keys=True), encoding="utf-8"
    )
    save_file(
        {
            "base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight": np.zeros(
                (8, 4), dtype=np.float32
            ),
            "base_model.model.model.layers.0.self_attn.q_proj.lora_B.weight": np.zeros(
                (4, 8), dtype=np.float32
            ),
        },
        str(directory / "adapter_model.safetensors"),
    )
    return directory


def _patch_for_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wires the fake subprocess + successful health probe used in lifecycle tests."""
    from app.services.cloud import mlx_serving

    monkeypatch.setattr(mlx_serving, "_current_system", lambda: "Darwin")
    monkeypatch.setattr(mlx_serving, "_current_machine", lambda: "arm64")
    monkeypatch.setattr(mlx_serving, "_import_mlx_lm", lambda: types.ModuleType("mlx_lm"))
    monkeypatch.setattr(mlx_serving, "reserve_free_port", lambda *, host: 18080)

    async def _fake_spawn(*, argv: list[str], env: dict[str, str]) -> _FakeSubprocess:
        return _FakeSubprocess()

    monkeypatch.setattr(mlx_serving, "_spawn_subprocess", _fake_spawn)

    async def _fake_probe(*, base_url: str, timeout_s: float) -> bool:
        return True

    monkeypatch.setattr(mlx_serving, "_probe_models_endpoint", _fake_probe)


async def _seed_project(
    session: AsyncSession,
    *,
    serving_model_id: str | None,
    name: str = "p1",
) -> str:
    import uuid

    project_id = str(uuid.uuid4())
    config_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name=name,
        directory_path="/tmp/fake",
        active_config_version_id=config_id,
        created_at="2026-05-19T11:00:00+00:00",
        updated_at="2026-05-19T11:00:00+00:00",
    )
    config = ConfigVersion(
        id=config_id,
        project_id=project_id,
        version_number=1,
        yaml_blob=_make_yaml_config(serving_model_id=serving_model_id),
        yaml_hash="hash",
        source_tag="user",
        created_at="2026-05-19T11:00:00+00:00",
    )
    session.add(project)
    session.add(config)
    await session.commit()
    return project_id


async def _seed_run(
    session: AsyncSession,
    *,
    project_id: str,
    last_checkpoint_path: str | None,
) -> str:
    import uuid

    result = await session.execute(
        ConfigVersion.__table__.select().where(
            ConfigVersion.project_id == project_id
        )
    )
    config_row = result.first()
    assert config_row is not None
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id=project_id,
        config_version_id=config_row.id,
        status="completed",
        current_step=100,
        progress_pct=1.0,
        last_checkpoint_path=last_checkpoint_path,
        run_type="training",
        created_at="2026-05-19T11:00:00+00:00",
        updated_at="2026-05-19T11:00:00+00:00",
    )
    session.add(run)
    await session.commit()
    return run_id


class _FakeSubprocess:
    """Stand-in for asyncio.subprocess.Process with controllable lifecycle."""

    def __init__(self) -> None:
        self.terminated: bool = False
        self.killed: bool = False
        self.argv: list[str] | None = None
        self._returncode: int | None = None
        self.pid: int = 4242
        self.stdout = _FakeStream()
        self.stderr = _FakeStream()

    @property
    def returncode(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = 0

    def kill(self) -> None:
        self.killed = True
        self._returncode = -9

    async def wait(self) -> int:
        if self._returncode is None:
            self._returncode = 0
        return self._returncode


class _FakeStream:
    async def readline(self) -> bytes:
        return b""
