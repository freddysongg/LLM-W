from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
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
from app.models.notification import Notification
from app.models.project import Project
from app.models.run import Run
from app.models.run_attempt import RunAttempt
from app.schemas.run import RunCreate
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
def silenced_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the global event bus for a fresh one so publishes don't fan out
    to unrelated subscribers — the notification producers are what we assert."""
    bus = EventBus()
    monkeypatch.setattr(orchestrator, "event_bus", bus)
    monkeypatch.setattr(events_module, "event_bus", bus)


async def _seed_project_and_config(
    *,
    factory: async_sessionmaker[Any],
    project_dir: Path,
    yaml_blob: str,
) -> None:
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"prompt":"x","response":"y"}\n')
    async with factory() as session:
        session.add(
            Project(
                id="p1",
                name=project_dir.name,
                directory_path=str(project_dir),
                created_at="2026-05-19T11:00:00+00:00",
                updated_at="2026-05-19T11:00:00+00:00",
            )
        )
        session.add(
            ConfigVersion(
                id="cv1",
                project_id="p1",
                version_number=1,
                yaml_blob=yaml_blob,
                yaml_hash="hash",
                source_tag="user",
                created_at="2026-05-19T11:00:00+00:00",
            )
        )
        await session.commit()


def _modal_yaml() -> str:
    return yaml.safe_dump(
        {
            "execution": {
                "environment": "modal",
                "modal_gpu_type": "a10",
                "device": "cuda",
                "data_policy": "sanitized_cloud",
                "max_estimated_cost_usd": 2.0,
                "max_run_minutes": 30,
            }
        }
    )


async def _read_notifications(*, factory: async_sessionmaker[Any]) -> list[Notification]:
    async with factory() as session:
        result = await session.execute(select(Notification))
        return list(result.scalars().all())


async def test_create_run_writes_run_created_notification(
    patched_session_factory: async_sessionmaker[Any],
    silenced_event_bus: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_run must persist a `run_created` notification next to the row insert."""
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    await _seed_project_and_config(
        factory=patched_session_factory,
        project_dir=project_dir,
        yaml_blob=_modal_yaml(),
    )

    async def _stub_dispatch(**_: object) -> None:
        return None

    monkeypatch.setattr(orchestrator, "dispatch_training", _stub_dispatch)

    async with patched_session_factory() as session:
        created = await orchestrator.create_run(
            session=session,
            project_id="p1",
            payload=RunCreate(config_version_id="cv1"),
        )

    notifications = await _read_notifications(factory=patched_session_factory)
    created_rows = [n for n in notifications if n.type == "run_created"]
    assert len(created_rows) == 1
    assert created_rows[0].title == f"Run {created.id[:6]} created"
    assert created_rows[0].subtitle is None


async def test_update_run_status_first_start_writes_run_started_notification(
    patched_session_factory: async_sessionmaker[Any],
    silenced_event_bus: None,
) -> None:
    """The first write to Run.started_at must fire a run_started notification."""
    started_iso = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="pending",
                created_at=started_iso,
                updated_at=started_iso,
            )
        )
        await session.commit()

    await orchestrator._update_run_status(run_id="r1", status="running", started_at=started_iso)

    notifications = await _read_notifications(factory=patched_session_factory)
    started_rows = [n for n in notifications if n.type == "run_started"]
    assert len(started_rows) == 1
    assert started_rows[0].title == "Run r1 started"


async def test_update_run_status_second_stage_does_not_re_emit_run_started(
    patched_session_factory: async_sessionmaker[Any],
    silenced_event_bus: None,
) -> None:
    """A later stage_enter must not duplicate the run_started notification."""
    first_iso = "2026-05-19T12:00:00+00:00"
    second_iso = "2026-05-19T12:05:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="pending",
                created_at=first_iso,
                updated_at=first_iso,
            )
        )
        await session.commit()

    await orchestrator._update_run_status(run_id="r1", status="running", started_at=first_iso)
    await orchestrator._update_run_status(run_id="r1", status="running", started_at=second_iso)

    notifications = await _read_notifications(factory=patched_session_factory)
    started_rows = [n for n in notifications if n.type == "run_started"]
    assert len(started_rows) == 1


async def test_fail_run_with_oom_reason_writes_run_failed_notification(
    patched_session_factory: async_sessionmaker[Any],
    silenced_event_bus: None,
) -> None:
    """_fail_run_with_oom_reason must persist a run_failed notification."""
    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="a10",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="r1-a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="a10",
                device="cuda",
                started_at=now,
                ended_at=now,
                exit_reason="oom",
                cost_estimate_usd=0.5,
                created_at=now,
            )
        )
        await session.commit()

    await orchestrator._fail_run_with_oom_reason(
        run_id="r1",
        project_id="p1",
        failure_reason="oom_chain_exhausted",
        publish_run_failed=True,
    )

    notifications = await _read_notifications(factory=patched_session_factory)
    failed_rows = [n for n in notifications if n.type == "run_failed"]
    assert len(failed_rows) == 1
    assert failed_rows[0].title == "Run r1 failed"
    assert failed_rows[0].subtitle == "oom_chain_exhausted"


async def test_fail_run_with_oom_reason_skips_notification_when_no_publish(
    patched_session_factory: async_sessionmaker[Any],
    silenced_event_bus: None,
) -> None:
    """publish_run_failed=False means no WS envelope and no notification."""
    now = "2026-05-19T12:00:00+00:00"
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="a10",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    await orchestrator._fail_run_with_oom_reason(
        run_id="r1",
        project_id="p1",
        failure_reason="oom",
        publish_run_failed=False,
    )

    notifications = await _read_notifications(factory=patched_session_factory)
    assert [n for n in notifications if n.type == "run_failed"] == []


async def test_generate_suggestions_writes_one_notification_per_suggestion(
    patched_session_factory: async_sessionmaker[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each AISuggestion row produced by generate_suggestions must produce a notification row."""
    from app.services import ai_recommender, suggestion_service
    from app.services.ai_recommender import AISuggestionCreate

    now = datetime.now(UTC).isoformat()
    async with patched_session_factory() as session:
        session.add(
            Project(
                id="p1",
                name="suggestion-project",
                directory_path="/tmp/p1",
                active_config_version_id="cv1",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            ConfigVersion(
                id="cv1",
                project_id="p1",
                version_number=1,
                yaml_blob="execution:\n  environment: local\n",
                yaml_hash="hash",
                source_tag="user",
                created_at=now,
            )
        )
        await session.commit()

    expected = [
        AISuggestionCreate(
            provider="openai",
            config_diff={"training.learning_rate": {"current": 1e-4, "suggested": 5e-5}},
            rationale="loss plateau",
            evidence=None,
            expected_effect="cut loss plateau",
            tradeoffs="slower convergence",
            confidence=0.8,
            risk_level="low",
        ),
        AISuggestionCreate(
            provider="openai",
            config_diff={"training.warmup_steps": {"current": 0, "suggested": 100}},
            rationale="cold start instability",
            evidence=None,
            expected_effect="smoother early loss",
            tradeoffs="more steps before useful training",
            confidence=0.6,
            risk_level="low",
        ),
    ]

    class _StubEngine:
        async def generate_recommendations(self, **_: object) -> list[AISuggestionCreate]:
            return expected

    monkeypatch.setattr(ai_recommender, "build_engine", lambda **_: _StubEngine())
    monkeypatch.setattr(suggestion_service, "build_engine", lambda **_: _StubEngine())
    monkeypatch.setattr(suggestion_service, "get_raw_api_key", lambda: "key")

    async with patched_session_factory() as session:
        await suggestion_service.generate_suggestions(session=session, project_id="p1")

    notifications = await _read_notifications(factory=patched_session_factory)
    ai_rows = [n for n in notifications if n.type == "ai_suggestion"]
    assert len(ai_rows) == 2
    assert {n.subtitle for n in ai_rows} == {"cut loss plateau", "smoother early loss"}
    assert all(n.title == "New AI suggestion" for n in ai_rows)
