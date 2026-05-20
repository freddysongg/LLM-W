from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import events as events_module
from app.core.database import Base
from app.core.events import EventBus
from app.core.exceptions import RunNotFoundError, RunStateError
from app.models.config_version import ConfigVersion
from app.models.project import Project
from app.models.run import Run
from app.models.run_attempt import RunAttempt
from app.schemas.run import RunCreate
from app.schemas.workbench_config import ExecutionConfig
from app.services import orchestrator, settings_service
from app.services.training_dispatcher import UnsupportedEnvironmentError


@pytest.fixture(autouse=True)
def reset_overrides() -> None:
    settings_service._overrides.clear()
    yield
    settings_service._overrides.clear()


@pytest.fixture
async def patched_session_factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[async_sessionmaker[Any]]:
    db_path = tmp_path / "workbench.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(orchestrator, "async_session_factory", factory)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def captured_events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the global event_bus with a capturing instance for the test.

    The orchestrator publishes to project-scoped topics like `project.{id}.ws`,
    so we wrap publish() to record every payload regardless of which topic it
    targets — capturing on a single subscriber would miss events emitted before
    the subscriber was registered or for project ids the test doesn't know.
    """
    bus = EventBus()
    collected: list[dict[str, Any]] = []
    original_publish = bus.publish

    async def patched_publish(*, event_type: str, payload: dict[str, Any]) -> None:
        collected.append(payload)
        await original_publish(event_type=event_type, payload=payload)

    bus.publish = patched_publish  # type: ignore[method-assign]
    monkeypatch.setattr(orchestrator, "event_bus", bus)
    monkeypatch.setattr(events_module, "event_bus", bus)
    return collected


async def _setup_project_and_config(
    *,
    factory: async_sessionmaker[Any],
    project_dir: Path,
    yaml_blob: str,
    project_id: str = "p1",
    config_version_id: str = "cv1",
) -> None:
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"prompt":"x","response":"y"}\n')
    async with factory() as session:
        session.add(
            Project(
                id=project_id,
                name=project_dir.name,
                directory_path=str(project_dir),
                created_at="2026-05-19T11:00:00+00:00",
                updated_at="2026-05-19T11:00:00+00:00",
            )
        )
        session.add(
            ConfigVersion(
                id=config_version_id,
                project_id=project_id,
                version_number=1,
                yaml_blob=yaml_blob,
                yaml_hash="hash",
                source_tag="user",
                created_at="2026-05-19T11:00:00+00:00",
            )
        )
        await session.commit()


def _yaml_for_modal_run(
    *,
    gpu_type: str = "l40s",
    strategy: str = "ask",
    chain: list[str] | None = None,
    max_run_minutes: int = 30,
) -> str:
    execution: dict[str, Any] = {
        "environment": "modal",
        "modal_gpu_type": gpu_type,
        "device": "cuda",
        "data_policy": "sanitized_cloud",
        "max_estimated_cost_usd": 2.0,
        "max_run_minutes": max_run_minutes,
        "modal_oom_fallback": {
            "chain": chain if chain is not None else ["l40s", "a100-40gb", "a100-80gb"],
            "strategy": strategy,
        },
    }
    return yaml.safe_dump({"execution": execution})


async def test_create_run_creates_attempt_zero(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    await _setup_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=_yaml_for_modal_run(),
    )

    # Stub dispatch_training so create_run's async task doesn't actually launch.
    async def _stub_dispatch(**_: object) -> None:
        return None

    monkeypatch.setattr(orchestrator, "dispatch_training", _stub_dispatch)

    async with patched_session_factory() as session:
        created = await orchestrator.create_run(
            session=session,
            project_id="p1",
            payload=RunCreate(config_version_id="cv1"),
        )
        run_id = created.id

    async with patched_session_factory() as session:
        result = await session.execute(select(RunAttempt).where(RunAttempt.run_id == run_id))
        attempts = list(result.scalars().all())

    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt.attempt_index == 0
    assert attempt.gpu_type == "l40s"
    assert attempt.device == "cuda"
    assert attempt.ended_at is None


async def test_handle_oom_emits_fallback_proposed_event(
    patched_session_factory: async_sessionmaker[Any],
    captured_events: list[dict[str, Any]],
) -> None:
    execution = ExecutionConfig.model_validate(
        yaml.safe_load(_yaml_for_modal_run(gpu_type="l40s"))["execution"]
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=now,
                created_at=now,
            )
        )
        await session.commit()

    handled = await orchestrator._handle_trainer_oom(
        run_id="r1",
        project_id="p1",
        execution=execution,
        exit_code=1,
        stderr_tail="RuntimeError: CUDA out of memory",
        exception_type_name=None,
    )
    assert handled is True

    proposed = [
        e for e in captured_events if e.get("event") == "fallback_proposed"
    ]
    assert len(proposed) == 1
    payload = proposed[0]["payload"]
    assert payload["from_gpu"] == "l40s"
    assert payload["preserved_volume"] is True
    candidate_types = [c["gpu_type"] for c in payload["candidates"]]
    # The chain is [l40s, a100-40gb, a100-80gb]; l40s is the failed one so it's
    # excluded. Worst-case at 30min for a100-80gb = 30*60*(3.8412/3600)=$1.92, OK.
    assert "l40s" not in candidate_types
    assert "a100-40gb" in candidate_types
    assert "a100-80gb" in candidate_types

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "fallback_pending"
        attempt = (
            await session.execute(select(RunAttempt).where(RunAttempt.run_id == "r1"))
        ).scalar_one()
        assert attempt.ended_at is not None
        assert attempt.exit_reason == "oom"


async def test_accept_fallback_creates_attempt_n_plus_one(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    (project_dir / "configs").mkdir()
    await _setup_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=_yaml_for_modal_run(gpu_type="l40s"),
    )

    async def _stub_dispatch(**_: object) -> None:
        return None

    monkeypatch.setattr(orchestrator, "dispatch_training", _stub_dispatch)

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="fallback_pending",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=now,
                ended_at=now,
                exit_reason="oom",
                created_at=now,
            )
        )
        await session.commit()

    async with patched_session_factory() as session:
        updated = await orchestrator.accept_fallback(
            session=session, run_id="r1", project_id="p1", gpu_type="a100-40gb"
        )

    assert updated.status == "running"
    assert updated.modal_gpu_type == "a100-40gb"

    async with patched_session_factory() as session:
        attempts_result = await session.execute(
            select(RunAttempt).where(RunAttempt.run_id == "r1").order_by(RunAttempt.attempt_index)
        )
        attempts = list(attempts_result.scalars().all())
    assert len(attempts) == 2
    assert attempts[1].attempt_index == 1
    assert attempts[1].gpu_type == "a100-40gb"
    assert attempts[1].ended_at is None


async def test_accept_fallback_rejects_over_cap_gpu(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    # max_run_minutes=90; h100 over 90min = $5.19 → exceeds $5 cap.
    yaml_blob = _yaml_for_modal_run(gpu_type="l40s", max_run_minutes=90)
    await _setup_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=yaml_blob,
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="fallback_pending",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=now,
                ended_at=now,
                exit_reason="oom",
                created_at=now,
            )
        )
        await session.commit()

    async with patched_session_factory() as session:
        with pytest.raises(UnsupportedEnvironmentError, match="hard cap"):
            await orchestrator.accept_fallback(
                session=session, run_id="r1", project_id="p1", gpu_type="h100"
            )


async def test_cancel_fallback_marks_failed_with_user_cancelled_reason(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    captured_events: list[dict[str, Any]],
) -> None:
    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    await _setup_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=_yaml_for_modal_run(),
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="fallback_pending",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=now,
                ended_at=now,
                exit_reason="oom",
                created_at=now,
            )
        )
        await session.commit()

    async with patched_session_factory() as session:
        cancelled = await orchestrator.cancel_fallback(
            session=session, run_id="r1", project_id="p1"
        )

    assert cancelled.status == "failed"
    assert cancelled.failure_reason == "oom_user_cancelled"

    failed_events = [e for e in captured_events if e.get("event") == "run_failed"]
    assert len(failed_events) == 1
    assert failed_events[0]["payload"]["failureReason"] == "oom_user_cancelled"


async def test_chain_exhausted_after_all_candidates_oom(
    patched_session_factory: async_sessionmaker[Any],
    captured_events: list[dict[str, Any]],
) -> None:
    """When the current GPU is the final option in the chain, no candidates remain."""
    # Set the current GPU to the last entry; with the same chain, no fallback exists.
    execution = ExecutionConfig.model_validate(
        yaml.safe_load(
            _yaml_for_modal_run(
                gpu_type="a100-80gb",
                chain=["a100-80gb"],
            )
        )["execution"]
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="a100-80gb",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="a100-80gb",
                device="cuda",
                started_at=now,
                created_at=now,
            )
        )
        await session.commit()

    handled = await orchestrator._handle_trainer_oom(
        run_id="r1",
        project_id="p1",
        execution=execution,
        exit_code=1,
        stderr_tail="CUDA out of memory",
        exception_type_name=None,
    )
    assert handled is True

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "failed"
        assert run.failure_reason == "oom_chain_exhausted"


async def test_strategy_auto_picks_first_candidate(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    captured_events: list[dict[str, Any]],
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    yaml_blob = _yaml_for_modal_run(gpu_type="l40s", strategy="auto")
    await _setup_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=yaml_blob,
    )

    async def _stub_dispatch(**_: object) -> None:
        return None

    monkeypatch.setattr(orchestrator, "dispatch_training", _stub_dispatch)

    execution = ExecutionConfig.model_validate(yaml.safe_load(yaml_blob)["execution"])
    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=now,
                created_at=now,
            )
        )
        await session.commit()

    handled = await orchestrator._handle_trainer_oom(
        run_id="r1",
        project_id="p1",
        execution=execution,
        exit_code=1,
        stderr_tail="CUDA out of memory",
        exception_type_name=None,
    )
    assert handled is True

    proposed = [e for e in captured_events if e.get("event") == "fallback_proposed"]
    assert proposed == []

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "running"
        # First candidate after l40s is a100-40gb.
        assert run.modal_gpu_type == "a100-40gb"


async def test_strategy_disabled_fails_immediately(
    patched_session_factory: async_sessionmaker[Any],
    captured_events: list[dict[str, Any]],
) -> None:
    execution = ExecutionConfig.model_validate(
        yaml.safe_load(_yaml_for_modal_run(strategy="disabled"))["execution"]
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=now,
                created_at=now,
            )
        )
        await session.commit()

    handled = await orchestrator._handle_trainer_oom(
        run_id="r1",
        project_id="p1",
        execution=execution,
        exit_code=1,
        stderr_tail="CUDA out of memory",
        exception_type_name=None,
    )
    assert handled is True

    proposed = [e for e in captured_events if e.get("event") == "fallback_proposed"]
    assert proposed == []

    failed = [e for e in captured_events if e.get("event") == "run_failed"]
    assert len(failed) == 1
    assert failed[0]["runId"] == "r1"
    assert failed[0]["payload"]["failureReason"] == "oom"

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "failed"
        assert run.failure_reason == "oom"


async def test_strategy_disabled_publishes_rolled_up_attempt_cost(
    patched_session_factory: async_sessionmaker[Any],
    captured_events: list[dict[str, Any]],
) -> None:
    """Disabled-strategy OOM must report the cost of the failed Modal attempt, not zero."""
    execution = ExecutionConfig.model_validate(
        yaml.safe_load(_yaml_for_modal_run(strategy="disabled"))["execution"]
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=now,
                created_at=now,
            )
        )
        await session.commit()

    handled = await orchestrator._handle_trainer_oom(
        run_id="r1",
        project_id="p1",
        execution=execution,
        exit_code=1,
        stderr_tail="CUDA out of memory",
        exception_type_name=None,
    )
    assert handled is True

    failed = [e for e in captured_events if e.get("event") == "run_failed"]
    assert len(failed) == 1
    # _close_failed_attempt closes the Modal attempt with a positive cost based
    # on the l40s rate × elapsed time. That cost must surface in both the run
    # row and the WS envelope; the bug had it pinned at 0.
    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.cost_usd is not None
        assert run.cost_usd > 0.0
        assert failed[0]["payload"]["costUsd"] == run.cost_usd
        # Wall-clock rollup mirrors the cost rollup: the closed attempt's
        # duration must land in both the run row and the WS envelope, not 0.
        assert run.wall_clock_s is not None
        assert run.wall_clock_s > 0.0
        assert failed[0]["payload"]["wallClockS"] == run.wall_clock_s


async def test_local_oom_emits_system_event_but_does_not_trigger_fallback(
    patched_session_factory: async_sessionmaker[Any],
    captured_events: list[dict[str, Any]],
) -> None:
    """Local OOM is observation-only — no fallback chain on the host."""
    execution = ExecutionConfig.model_validate(
        {"environment": "local", "device": "cuda"}
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                environment="local",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type=None,
                device="cuda",
                started_at=now,
                created_at=now,
            )
        )
        await session.commit()

    handled = await orchestrator._handle_trainer_oom(
        run_id="r1",
        project_id="p1",
        execution=execution,
        exit_code=1,
        stderr_tail="CUDA out of memory",
        exception_type_name=None,
    )
    # Local returns False so the generic failure path takes over.
    assert handled is False

    oom_events = [e for e in captured_events if e.get("event") == "oom_detected"]
    assert len(oom_events) == 1
    assert oom_events[0]["payload"]["device"] == "cuda"


async def test_accept_fallback_rejects_when_not_pending(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    await _setup_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=_yaml_for_modal_run(),
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    async with patched_session_factory() as session:
        with pytest.raises(RunStateError):
            await orchestrator.accept_fallback(
                session=session, run_id="r1", project_id="p1", gpu_type="a100-40gb"
            )


async def test_accept_fallback_rejects_same_gpu_type(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    await _setup_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=_yaml_for_modal_run(gpu_type="l40s"),
    )

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="fallback_pending",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    async with patched_session_factory() as session:
        with pytest.raises(UnsupportedEnvironmentError, match="same as the GPU"):
            await orchestrator.accept_fallback(
                session=session, run_id="r1", project_id="p1", gpu_type="l40s"
            )


async def test_accept_fallback_dispatches_with_new_gpu_type_override(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The respawned trainer must run on the accepted GPU, not the YAML's."""
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    yaml_blob = _yaml_for_modal_run(gpu_type="l40s", strategy="ask")
    await _setup_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=yaml_blob,
    )

    captured_kwargs: list[dict[str, Any]] = []

    async def _capturing_dispatch(**kwargs: Any) -> None:
        captured_kwargs.append(kwargs)
        return None

    monkeypatch.setattr(orchestrator, "dispatch_training", _capturing_dispatch)

    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="fallback_pending",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=now,
                ended_at=now,
                exit_reason="oom",
                created_at=now,
            )
        )
        await session.commit()

    async with patched_session_factory() as session:
        await orchestrator.accept_fallback(
            session=session, run_id="r1", project_id="p1", gpu_type="a100-40gb"
        )

    spawned = orchestrator._active_tasks.get("r1")
    if spawned is not None:
        await asyncio.gather(spawned, return_exceptions=True)

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0].get("gpu_type_override") == "a100-40gb"


async def test_accept_fallback_rejects_cross_project_access(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
) -> None:
    """A run from project A must not be mutable via project B's URL."""
    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="real-project",
                config_version_id="cv1",
                status="fallback_pending",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    async with patched_session_factory() as session:
        with pytest.raises(RunNotFoundError):
            await orchestrator.accept_fallback(
                session=session,
                run_id="r1",
                project_id="other-project",
                gpu_type="a100-40gb",
            )


async def test_cancel_fallback_rejects_cross_project_access(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="real-project",
                config_version_id="cv1",
                status="fallback_pending",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    async with patched_session_factory() as session:
        with pytest.raises(RunNotFoundError):
            await orchestrator.cancel_fallback(
                session=session, run_id="r1", project_id="other-project"
            )


async def test_evict_completed_trainer_task_preserves_newer_registered_task() -> None:
    """The done callback for an old task must not evict the newer fallback task."""

    async def _noop() -> None:
        return None

    task_a = asyncio.create_task(_noop(), name="trainer-a")
    task_b = asyncio.create_task(_noop(), name="trainer-b")
    await asyncio.gather(task_a, task_b)

    orchestrator._active_tasks["r1"] = task_b
    try:
        orchestrator._evict_completed_trainer_task(run_id="r1", completed=task_a)
        assert orchestrator._active_tasks.get("r1") is task_b

        orchestrator._evict_completed_trainer_task(run_id="r1", completed=task_b)
        assert "r1" not in orchestrator._active_tasks
    finally:
        orchestrator._active_tasks.pop("r1", None)
