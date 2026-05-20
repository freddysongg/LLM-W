from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.run import Run
from app.models.run_attempt import RunAttempt
from app.schemas.workbench_config import ExecutionConfig
from app.services import orchestrator


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


def _modal_execution() -> ExecutionConfig:
    return ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "modal_gpu_type": "a10",
            "device": "cuda",
            "data_policy": "sanitized_cloud",
            "max_estimated_cost_usd": 2.0,
            "max_run_minutes": 30,
        }
    )


def _local_execution() -> ExecutionConfig:
    return ExecutionConfig.model_validate(
        {
            "environment": "local",
            "device": "cuda",
            "max_estimated_cost_usd": 2.0,
            "max_run_minutes": 30,
        }
    )


async def _seed_run_with_failed_then_open_attempt(
    *, factory: async_sessionmaker[Any], run_id: str, prior_cost_usd: float
) -> None:
    now = datetime.now(UTC).isoformat()
    started = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    async with factory() as session:
        session.add(
            Run(
                id=run_id,
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="a10",
                environment="modal",
                device="cuda",
                created_at=started,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id=f"{run_id}-a0",
                run_id=run_id,
                attempt_index=0,
                gpu_type="a10",
                device="cuda",
                started_at=started,
                ended_at=started,
                exit_reason="oom",
                cost_estimate_usd=prior_cost_usd,
                created_at=started,
            )
        )
        session.add(
            RunAttempt(
                id=f"{run_id}-a1",
                run_id=run_id,
                attempt_index=1,
                gpu_type="a10",
                device="cuda",
                started_at=started,
                ended_at=None,
                exit_reason=None,
                cost_estimate_usd=None,
                created_at=started,
            )
        )
        await session.commit()


async def test_sum_attempt_costs_returns_zero_for_missing_run(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    assert await orchestrator._sum_attempt_costs(run_id="missing") == 0.0


async def test_sum_attempt_costs_skips_null_costs(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    await _seed_run_with_failed_then_open_attempt(
        factory=patched_session_factory, run_id="r1", prior_cost_usd=1.5
    )
    # Prior attempt: 1.5, current open attempt: None → only 1.5 is summed.
    assert await orchestrator._sum_attempt_costs(run_id="r1") == 1.5


async def test_close_current_attempt_writes_cost_for_open_attempt(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    await _seed_run_with_failed_then_open_attempt(
        factory=patched_session_factory, run_id="r1", prior_cost_usd=1.5
    )

    await orchestrator._close_current_attempt(
        run_id="r1", execution=_modal_execution(), exit_reason="completed"
    )

    async with patched_session_factory() as session:
        attempt = await session.get(RunAttempt, "r1-a1")
        assert attempt is not None
        assert attempt.ended_at is not None
        assert attempt.exit_reason == "completed"
        assert attempt.cost_estimate_usd is not None
        assert attempt.cost_estimate_usd > 0.0


async def test_close_current_attempt_is_idempotent_when_already_closed(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    await _seed_run_with_failed_then_open_attempt(
        factory=patched_session_factory, run_id="r1", prior_cost_usd=1.5
    )
    # First close fixes a value.
    await orchestrator._close_current_attempt(
        run_id="r1", execution=_modal_execution(), exit_reason="completed"
    )
    async with patched_session_factory() as session:
        attempt_first = await session.get(RunAttempt, "r1-a1")
        first_cost = attempt_first.cost_estimate_usd

    # Second call must not re-close (no overwrite).
    await orchestrator._close_current_attempt(
        run_id="r1", execution=_modal_execution(), exit_reason="cancelled"
    )
    async with patched_session_factory() as session:
        attempt_second = await session.get(RunAttempt, "r1-a1")
        assert attempt_second.exit_reason == "completed"
        assert attempt_second.cost_estimate_usd == first_cost


async def test_rollup_includes_prior_failed_attempt_cost(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    """Run.cost_usd must reflect the sum of every attempt, not just the last one."""
    await _seed_run_with_failed_then_open_attempt(
        factory=patched_session_factory, run_id="r1", prior_cost_usd=2.5
    )

    await orchestrator._close_current_attempt(
        run_id="r1", execution=_modal_execution(), exit_reason="completed"
    )
    total = await orchestrator._sum_attempt_costs(run_id="r1")

    # The current attempt's wall-clock × a10 rate adds some positive amount;
    # the assertion below pins only the lower bound from the prior attempt
    # so we don't couple the test to clock-skew between sed `started_at` and
    # `now`.
    assert total > 2.5


async def test_close_current_attempt_records_zero_cost_for_local_run(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    """Local runs have no GPU rate; attempt cost stays at zero regardless of wall-clock."""
    await _seed_run_with_failed_then_open_attempt(
        factory=patched_session_factory, run_id="r1", prior_cost_usd=0.0
    )

    await orchestrator._close_current_attempt(
        run_id="r1", execution=_local_execution(), exit_reason="completed"
    )

    async with patched_session_factory() as session:
        attempt = await session.get(RunAttempt, "r1-a1")
        assert attempt.cost_estimate_usd == 0.0


async def test_sum_attempt_wall_clock_s_returns_zero_for_missing_run(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    assert await orchestrator._sum_attempt_wall_clock_s(run_id="missing") == 0.0


async def test_sum_attempt_wall_clock_s_skips_open_attempts(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    """An open attempt (ended_at IS NULL) must not contribute mid-flight wall-clock.

    The seed creates one closed attempt (5-minute window) and one still-open one.
    The rollup must return only the closed attempt's duration.
    """
    await _seed_run_with_failed_then_open_attempt(
        factory=patched_session_factory, run_id="r1", prior_cost_usd=0.0
    )

    total = await orchestrator._sum_attempt_wall_clock_s(run_id="r1")
    # The seed's closed attempt has started_at == ended_at → 0.0 seconds.
    # The open attempt is skipped. Total must be exactly 0.0.
    assert total == 0.0


async def test_sum_attempt_wall_clock_s_sums_closed_attempts(
    patched_session_factory: async_sessionmaker[Any],
) -> None:
    """Two closed attempts: 30s + 90s = 120s."""
    started_zero = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC).isoformat()
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="completed",
                modal_gpu_type="a10",
                environment="modal",
                device="cuda",
                created_at=started_zero,
                updated_at=started_zero,
            )
        )
        session.add(
            RunAttempt(
                id="r1-a0",
                run_id="r1",
                attempt_index=0,
                gpu_type="a10",
                device="cuda",
                started_at=started_zero,
                ended_at=(datetime.fromisoformat(started_zero) + timedelta(seconds=30)).isoformat(),
                exit_reason="oom",
                cost_estimate_usd=0.0,
                created_at=started_zero,
            )
        )
        session.add(
            RunAttempt(
                id="r1-a1",
                run_id="r1",
                attempt_index=1,
                gpu_type="a10",
                device="cuda",
                started_at=(
                    datetime.fromisoformat(started_zero) + timedelta(seconds=60)
                ).isoformat(),
                ended_at=(
                    datetime.fromisoformat(started_zero) + timedelta(seconds=150)
                ).isoformat(),
                exit_reason="completed",
                cost_estimate_usd=0.0,
                created_at=started_zero,
            )
        )
        await session.commit()

    total = await orchestrator._sum_attempt_wall_clock_s(run_id="r1")
    assert total == 120.0
