from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import events as events_module
from app.core.database import Base
from app.core.events import EventBus
from app.models.config_version import ConfigVersion
from app.models.project import Project
from app.models.run import Run
from app.models.run_attempt import RunAttempt
from app.services import orchestrator, settings_service


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


def _modal_yaml() -> str:
    return yaml.safe_dump(
        {
            "execution": {
                "environment": "modal",
                "modal_gpu_type": "l40s",
                "device": "cuda",
                "data_policy": "sanitized_cloud",
                "max_estimated_cost_usd": 2.0,
                "max_run_minutes": 30,
            }
        }
    )


async def _seed_project_and_config(
    *,
    factory: async_sessionmaker[Any],
    project_dir: Path,
    project_id: str = "p1",
    config_version_id: str = "cv1",
) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
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
                yaml_blob=_modal_yaml(),
                yaml_hash="hash",
                source_tag="user",
                created_at="2026-05-19T11:00:00+00:00",
            )
        )
        await session.commit()


async def _seed_fallback_pending_run(
    *,
    factory: async_sessionmaker[Any],
    run_id: str,
    updated_at_iso: str,
    open_attempt: bool = True,
    attempt_id: str = "a0",
    project_id: str = "p1",
    config_version_id: str = "cv1",
) -> None:
    async with factory() as session:
        session.add(
            Run(
                id=run_id,
                project_id=project_id,
                config_version_id=config_version_id,
                status="fallback_pending",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=updated_at_iso,
                updated_at=updated_at_iso,
            )
        )
        session.add(
            RunAttempt(
                id=attempt_id,
                run_id=run_id,
                attempt_index=0,
                gpu_type="l40s",
                device="cuda",
                started_at=updated_at_iso,
                ended_at=None if open_attempt else updated_at_iso,
                exit_reason=None if open_attempt else "oom",
                created_at=updated_at_iso,
            )
        )
        await session.commit()


async def test_sweep_marks_stale_fallback_pending_runs_failed(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    captured_events: list[dict[str, Any]],
) -> None:
    await _seed_project_and_config(
        factory=patched_session_factory, project_dir=tmp_path / "p1"
    )
    stale_iso = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    await _seed_fallback_pending_run(
        factory=patched_session_factory, run_id="r1", updated_at_iso=stale_iso
    )

    await orchestrator._sweep_abandoned_fallback_runs()

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "failed"
        assert run.failure_reason == "oom_fallback_abandoned"
        assert run.completed_at is not None

        attempt_row = await session.execute(
            select(RunAttempt).where(RunAttempt.id == "a0")
        )
        attempt = attempt_row.scalar_one()
        assert attempt.ended_at is not None
        assert attempt.exit_reason == "oom_fallback_abandoned"

    failed_events = [e for e in captured_events if e.get("event") == "run_failed"]
    assert len(failed_events) == 1
    assert failed_events[0]["payload"]["failureReason"] == "oom_fallback_abandoned"


async def test_sweep_leaves_recent_fallback_pending_runs_alone(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    captured_events: list[dict[str, Any]],
) -> None:
    await _seed_project_and_config(
        factory=patched_session_factory, project_dir=tmp_path / "p1"
    )
    recent_iso = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    await _seed_fallback_pending_run(
        factory=patched_session_factory, run_id="r1", updated_at_iso=recent_iso
    )

    await orchestrator._sweep_abandoned_fallback_runs()

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "fallback_pending"
    assert [e for e in captured_events if e.get("event") == "run_failed"] == []


async def test_sweep_leaves_non_pending_runs_alone(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    captured_events: list[dict[str, Any]],
) -> None:
    await _seed_project_and_config(
        factory=patched_session_factory, project_dir=tmp_path / "p1"
    )
    stale_iso = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
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
                created_at=stale_iso,
                updated_at=stale_iso,
            )
        )
        await session.commit()

    await orchestrator._sweep_abandoned_fallback_runs()

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "running"
    assert [e for e in captured_events if e.get("event") == "run_failed"] == []


async def test_sweep_handles_missing_attempt_gracefully(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    captured_events: list[dict[str, Any]],
) -> None:
    await _seed_project_and_config(
        factory=patched_session_factory, project_dir=tmp_path / "p1"
    )
    stale_iso = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
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
                created_at=stale_iso,
                updated_at=stale_iso,
            )
        )
        await session.commit()

    await orchestrator._sweep_abandoned_fallback_runs()

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "failed"
        assert run.failure_reason == "oom_fallback_abandoned"

    failed_events = [e for e in captured_events if e.get("event") == "run_failed"]
    assert len(failed_events) == 1


async def test_sweep_respects_configured_ttl(
    patched_session_factory: async_sessionmaker[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "oom_fallback_recovery_ttl_hours", 1.0)
    await _seed_project_and_config(
        factory=patched_session_factory, project_dir=tmp_path / "p1"
    )
    two_hours_ago = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    await _seed_fallback_pending_run(
        factory=patched_session_factory,
        run_id="r1",
        updated_at_iso=two_hours_ago,
    )

    await orchestrator._sweep_abandoned_fallback_runs()

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.status == "failed"
        assert run.failure_reason == "oom_fallback_abandoned"
