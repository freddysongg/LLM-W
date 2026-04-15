from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal, cast

import pytest
import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.events import event_bus
from app.models.eval_run import EvalRun
from app.models.rubric import Rubric as RubricModel
from app.models.rubric_version import RubricVersion
from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric
from app.services.eval.judge import JudgeError, JudgeProvider
from app.services.eval_runner import (
    _IN_FLIGHT_TASKS,
    EvalOrchestrationError,
    RubricVersionNotFoundError,
    _default_case_provider,
    create_eval_run_row,
    drain_in_flight_tasks,
    execute_eval_run,
    recover_stale_eval_runs,
)

_TRIGGER_NO_UPDATE = """
CREATE TRIGGER eval_calls_no_update
BEFORE UPDATE ON eval_calls
BEGIN
  SELECT RAISE(ABORT, 'eval_calls is append-only');
END
"""

_TRIGGER_NO_DELETE = """
CREATE TRIGGER eval_calls_no_delete
BEFORE DELETE ON eval_calls
BEGIN
  SELECT RAISE(ABORT, 'eval_calls is append-only');
END
"""

_JUDGE_MODEL = "gpt-4o-mini-2024-07-18"
_PROJECT_ID = "proj-runner"


def _rubric_payload(*, rubric_id: str) -> dict[str, Any]:
    pass_example = {
        "input": EvaluationCase(prompt="p", output="o").model_dump(),
        "verdict": "pass",
        "reasoning": "matches",
    }
    fail_example = {
        "input": EvaluationCase(prompt="p", output="o").model_dump(),
        "verdict": "fail",
        "reasoning": "mismatch",
    }
    return {
        "id": rubric_id,
        "version": "1.0.0",
        "description": "stub rubric for orchestrator tests",
        "scale": "binary",
        "criteria": [
            {"name": "claims_supported", "description": "claims supported", "points": 2},
        ],
        "few_shot_examples": [
            pass_example,
            pass_example,
            fail_example,
            fail_example,
            pass_example,
        ],
        "judge_model_pin": _JUDGE_MODEL,
        "research_basis": ["R1"],
    }


def _response_hash(*, reasoning: str, verdict: str, per_criterion: dict[str, bool]) -> str:
    payload = {"reasoning": reasoning, "verdict": verdict, "per_criterion": per_criterion}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _build_score(
    *,
    verdict: str = "pass",
    reasoning: str = "seeded reasoning",
    cost_usd: float = 0.01,
) -> Score:
    per_criterion = {"claims_supported": verdict == "pass"}
    return Score(
        reasoning=reasoning,
        verdict=cast(Literal["pass", "fail"], verdict),
        per_criterion=per_criterion,
        cost_usd=cost_usd,
        latency_ms=100,
        judge_model=_JUDGE_MODEL,
        rubric_version="1.0.0",
        response_hash=_response_hash(
            reasoning=reasoning, verdict=verdict, per_criterion=per_criterion
        ),
    )


class _ScriptedJudge(JudgeProvider):
    def __init__(self, *, scripted_scores: list[Score]) -> None:
        self._scores = list(scripted_scores)
        self.call_count = 0

    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        self.call_count += 1
        if not self._scores:
            raise JudgeError("scripted judge exhausted")
        return self._scores.pop(0)


class _AlwaysFailingJudge(JudgeProvider):
    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        raise JudgeError("simulated judge failure")


class _MultiRubricJudge(JudgeProvider):
    """Returns pass for the 'good' rubric, fails via JudgeError for the 'bad' rubric."""

    def __init__(self, *, bad_rubric_id: str) -> None:
        self._bad_rubric_id = bad_rubric_id
        self.successful_calls = 0

    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        if rubric.id == self._bad_rubric_id:
            raise JudgeError(f"scripted failure on rubric {rubric.id}")
        self.successful_calls += 1
        return _build_score(cost_usd=0.005)


@pytest.fixture
async def engine_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(_TRIGGER_NO_UPDATE))
        await conn.execute(text(_TRIGGER_NO_DELETE))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed_rubric_version(
    *,
    session: AsyncSession,
    rubric_id: str,
    rubric_row_id: str,
    rubric_version_id: str,
) -> None:
    rubric_row = RubricModel(
        id=rubric_row_id,
        name=rubric_id,
        description="stub rubric",
        research_basis=None,
        created_at="2026-04-14T00:00:00+00:00",
    )
    version_row = RubricVersion(
        id=rubric_version_id,
        rubric_id=rubric_row_id,
        version_number=1,
        yaml_blob=yaml.safe_dump(_rubric_payload(rubric_id=rubric_id)),
        content_hash="a" * 64,
        diff_from_prev=None,
        calibration_metrics=None,
        calibration_status="uncalibrated",
        judge_model_pin=_JUDGE_MODEL,
        created_at="2026-04-14T00:00:00+00:00",
    )
    session.add_all([rubric_row, version_row])
    await session.commit()


def _fixed_cases() -> Callable[[], Any]:
    async def _provider() -> list[EvaluationCase]:
        return [
            EvaluationCase(prompt="Q1", output="A1"),
            EvaluationCase(prompt="Q2", output="A2"),
        ]

    return _provider


def _single_case() -> Callable[[], Any]:
    async def _provider() -> list[EvaluationCase]:
        return [EvaluationCase(prompt="only", output="answer")]

    return _provider


class _EventSpy:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def handle(self, payload: dict[str, Any]) -> None:
        self.events.append(payload)


async def test_happy_path_writes_calls_and_emits_events(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine_factory() as session:
        await _seed_rubric_version(
            session=session,
            rubric_id="rubric_a",
            rubric_row_id="rubric-row-1",
            rubric_version_id="rv-a",
        )
        eval_run = await create_eval_run_row(
            session=session, training_run_id=None, max_cost_usd=None
        )
        eval_run_id = eval_run.id

    spy = _EventSpy()
    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)
    try:
        judge = _ScriptedJudge(
            scripted_scores=[
                _build_score(verdict="pass"),
                _build_score(verdict="fail"),
            ]
        )
        await execute_eval_run(
            session_factory=engine_factory,
            project_id=_PROJECT_ID,
            eval_run_id=eval_run_id,
            rubric_version_ids=["rv-a"],
            max_cost_usd=None,
            judge_factory=lambda _rubric: judge,
            case_provider=_fixed_cases(),
        )
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)

    assert judge.call_count == 2
    case_events = [e for e in spy.events if e["event"] == "case_completed"]
    run_events = [e for e in spy.events if e["event"] == "run_completed"]
    assert len(case_events) == 2
    assert len(run_events) == 1
    assert run_events[0]["payload"]["totals"]["cases"] == 2
    assert run_events[0]["payload"]["totals"]["pass"] == 1

    async with engine_factory() as session:
        run_row = await session.get(EvalRun, eval_run_id)
        assert run_row is not None
        assert run_row.status == "completed"
        assert run_row.pass_rate == 0.5

        calls_stmt = (
            await session.execute(
                text("SELECT COUNT(*) FROM eval_calls WHERE eval_run_id = :rid"),
                {"rid": eval_run_id},
            )
        ).scalar_one()
        assert calls_stmt == 2

        cases_stmt = (
            await session.execute(
                text("SELECT COUNT(*) FROM eval_cases WHERE eval_run_id = :rid"),
                {"rid": eval_run_id},
            )
        ).scalar_one()
        assert cases_stmt == 2


async def test_cost_ceiling_terminates_and_emits_warning(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine_factory() as session:
        await _seed_rubric_version(
            session=session,
            rubric_id="rubric_b",
            rubric_row_id="rubric-row-2",
            rubric_version_id="rv-b",
        )
        eval_run = await create_eval_run_row(
            session=session, training_run_id=None, max_cost_usd=0.015
        )
        eval_run_id = eval_run.id

    async def _many_cases() -> list[EvaluationCase]:
        return [EvaluationCase(prompt=f"Q{idx}", output=f"A{idx}") for idx in range(5)]

    spy = _EventSpy()
    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)
    try:
        judge = _ScriptedJudge(scripted_scores=[_build_score(cost_usd=0.01) for _ in range(5)])
        await execute_eval_run(
            session_factory=engine_factory,
            project_id=_PROJECT_ID,
            eval_run_id=eval_run_id,
            rubric_version_ids=["rv-b"],
            max_cost_usd=0.015,
            judge_factory=lambda _r: judge,
            case_provider=_many_cases,
        )
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)

    assert judge.call_count == 2
    warning_events = [e for e in spy.events if e["event"] == "cost_warning"]
    assert len(warning_events) == 1
    warning_payload = warning_events[0]["payload"]
    assert warning_payload["maxCostUsd"] == 0.015
    assert warning_payload["currentCostUsd"] >= 0.01

    async with engine_factory() as session:
        run_row = await session.get(EvalRun, eval_run_id)
        assert run_row is not None
        assert run_row.status == "cost_capped"
        assert run_row.total_cost_usd >= 0.015


async def test_judge_error_is_swallowed_and_run_continues(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine_factory() as session:
        await _seed_rubric_version(
            session=session,
            rubric_id="rubric_good",
            rubric_row_id="rubric-row-good",
            rubric_version_id="rv-good",
        )
        await _seed_rubric_version(
            session=session,
            rubric_id="rubric_bad",
            rubric_row_id="rubric-row-bad",
            rubric_version_id="rv-bad",
        )
        eval_run = await create_eval_run_row(
            session=session, training_run_id=None, max_cost_usd=None
        )
        eval_run_id = eval_run.id

    judge = _MultiRubricJudge(bad_rubric_id="rubric_bad")
    spy = _EventSpy()
    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)
    try:
        await execute_eval_run(
            session_factory=engine_factory,
            project_id=_PROJECT_ID,
            eval_run_id=eval_run_id,
            rubric_version_ids=["rv-good", "rv-bad"],
            max_cost_usd=None,
            judge_factory=lambda _r: judge,
            case_provider=_single_case(),
        )
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)

    assert judge.successful_calls == 1
    case_events = [e for e in spy.events if e["event"] == "case_completed"]
    case_failed_events = [e for e in spy.events if e["event"] == "case_failed"]
    run_events = [e for e in spy.events if e["event"] == "run_completed"]
    assert len(case_events) == 1
    assert len(case_failed_events) == 1
    assert len(run_events) == 1
    assert run_events[0]["payload"]["totals"]["cases"] == 1
    assert run_events[0]["payload"]["totals"]["failed_pairs"] == 1

    async with engine_factory() as session:
        run_row = await session.get(EvalRun, eval_run_id)
        assert run_row is not None
        assert run_row.status == "completed"
        error_call_rows = (
            await session.execute(
                text(
                    "SELECT tier, verdict FROM eval_calls "
                    "WHERE eval_run_id = :rid AND tier = 'error'"
                ),
                {"rid": eval_run_id},
            )
        ).all()
        assert len(error_call_rows) == 1
        assert error_call_rows[0].tier == "error"
        assert error_call_rows[0].verdict == "error"


async def test_missing_rubric_version_marks_run_failed(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine_factory() as session:
        eval_run = await create_eval_run_row(
            session=session, training_run_id=None, max_cost_usd=None
        )
        eval_run_id = eval_run.id

    spy = _EventSpy()
    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)
    try:
        await execute_eval_run(
            session_factory=engine_factory,
            project_id=_PROJECT_ID,
            eval_run_id=eval_run_id,
            rubric_version_ids=["rv-missing"],
            max_cost_usd=None,
            judge_factory=lambda _r: _AlwaysFailingJudge(),
            case_provider=_single_case(),
        )
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)

    run_events = [e for e in spy.events if e["event"] == "run_completed"]
    assert len(run_events) == 1
    assert run_events[0]["payload"]["status"] == "failed"

    async with engine_factory() as session:
        run_row = await session.get(EvalRun, eval_run_id)
        assert run_row is not None
        assert run_row.status == "failed"


async def test_concurrent_event_delivery_does_not_block(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regression test: verify orchestrator does not deadlock if a subscriber is slow."""

    async with engine_factory() as session:
        await _seed_rubric_version(
            session=session,
            rubric_id="rubric_c",
            rubric_row_id="rubric-row-3",
            rubric_version_id="rv-c",
        )
        eval_run = await create_eval_run_row(
            session=session, training_run_id=None, max_cost_usd=None
        )
        eval_run_id = eval_run.id

    slow_invocations: list[int] = []

    async def _slow_handler(_payload: dict[str, Any]) -> None:
        slow_invocations.append(1)
        await asyncio.sleep(0)

    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=_slow_handler)
    try:
        judge = _ScriptedJudge(scripted_scores=[_build_score()])
        await execute_eval_run(
            session_factory=engine_factory,
            project_id=_PROJECT_ID,
            eval_run_id=eval_run_id,
            rubric_version_ids=["rv-c"],
            max_cost_usd=None,
            judge_factory=lambda _r: judge,
            case_provider=_single_case(),
        )
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=_slow_handler)

    assert len(slow_invocations) >= 2


class _UnexpectedlyRaisingJudge(JudgeProvider):
    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        raise RuntimeError("unexpected failure outside JudgeError")


async def test_unexpected_exception_marks_run_failed(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine_factory() as session:
        await _seed_rubric_version(
            session=session,
            rubric_id="rubric_unexpected",
            rubric_row_id="rubric-row-unexpected",
            rubric_version_id="rv-unexpected",
        )
        eval_run = await create_eval_run_row(
            session=session, training_run_id=None, max_cost_usd=None
        )
        eval_run_id = eval_run.id

    spy = _EventSpy()
    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)
    try:
        await execute_eval_run(
            session_factory=engine_factory,
            project_id=_PROJECT_ID,
            eval_run_id=eval_run_id,
            rubric_version_ids=["rv-unexpected"],
            max_cost_usd=None,
            judge_factory=lambda _r: _UnexpectedlyRaisingJudge(),
            case_provider=_single_case(),
        )
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)

    run_events = [e for e in spy.events if e["event"] == "run_completed"]
    assert len(run_events) == 1
    assert run_events[0]["payload"]["status"] == "failed"

    async with engine_factory() as session:
        run_row = await session.get(EvalRun, eval_run_id)
        assert run_row is not None
        assert run_row.status == "failed"


async def test_malformed_calibration_row_raises_orchestration_error(tmp_path: Any) -> None:
    bad_file = tmp_path / "bad.jsonl"
    bad_file.write_text("{not-json\n", encoding="utf-8")

    from app.services import eval_runner as runner_module

    original_path = runner_module._DEFAULT_CALIBRATION_PATH
    runner_module._DEFAULT_CALIBRATION_PATH = bad_file
    try:
        with pytest.raises(EvalOrchestrationError) as exc_info:
            await _default_case_provider()
        assert "malformed calibration row 0" in str(exc_info.value)
    finally:
        runner_module._DEFAULT_CALIBRATION_PATH = original_path


async def test_create_eval_run_row_raises_when_rubric_missing(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine_factory() as session:
        with pytest.raises(RubricVersionNotFoundError):
            await create_eval_run_row(
                session=session,
                training_run_id=None,
                max_cost_usd=None,
                rubric_version_ids=["rv-does-not-exist"],
            )


async def test_cost_capped_status_distinct_from_completed(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine_factory() as session:
        await _seed_rubric_version(
            session=session,
            rubric_id="rubric_cap",
            rubric_row_id="rubric-row-cap",
            rubric_version_id="rv-cap",
        )
        eval_run = await create_eval_run_row(
            session=session, training_run_id=None, max_cost_usd=0.015
        )
        eval_run_id = eval_run.id

    async def _many_cases() -> list[EvaluationCase]:
        return [EvaluationCase(prompt=f"Q{idx}", output=f"A{idx}") for idx in range(5)]

    spy = _EventSpy()
    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)
    try:
        judge = _ScriptedJudge(scripted_scores=[_build_score(cost_usd=0.01) for _ in range(5)])
        await execute_eval_run(
            session_factory=engine_factory,
            project_id=_PROJECT_ID,
            eval_run_id=eval_run_id,
            rubric_version_ids=["rv-cap"],
            max_cost_usd=0.015,
            judge_factory=lambda _r: judge,
            case_provider=_many_cases,
        )
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=spy.handle)

    run_events = [e for e in spy.events if e["event"] == "run_completed"]
    assert len(run_events) == 1
    assert run_events[0]["payload"]["status"] == "cost_capped"

    async with engine_factory() as session:
        run_row = await session.get(EvalRun, eval_run_id)
        assert run_row is not None
        assert run_row.status == "cost_capped"


async def test_recover_stale_eval_runs_marks_running_as_failed(
    engine_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine_factory() as session:
        eval_run = await create_eval_run_row(
            session=session, training_run_id=None, max_cost_usd=None
        )
        eval_run_id = eval_run.id
        await session.rollback()
        async with session.begin():
            stuck = await session.get(EvalRun, eval_run_id)
            assert stuck is not None
            stuck.status = "running"

    recovered = await recover_stale_eval_runs(session_factory=engine_factory)
    assert recovered == 1

    async with engine_factory() as session:
        row = await session.get(EvalRun, eval_run_id)
        assert row is not None
        assert row.status == "failed"
        assert row.completed_at is not None


async def _sleep_forever() -> None:
    await asyncio.sleep(3600)


@pytest.mark.asyncio
async def test_drain_in_flight_tasks_cancels_registered_tasks() -> None:
    task = asyncio.create_task(_sleep_forever())
    _IN_FLIGHT_TASKS.add(task)
    task.add_done_callback(_IN_FLIGHT_TASKS.discard)

    try:
        await drain_in_flight_tasks(timeout_s=1.0)
        assert task.cancelled() is True
        assert task not in _IN_FLIGHT_TASKS
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        _IN_FLIGHT_TASKS.discard(task)


@pytest.mark.asyncio
async def test_drain_in_flight_tasks_noop_when_empty() -> None:
    assert len(_IN_FLIGHT_TASKS) == 0
    await drain_in_flight_tasks(timeout_s=1.0)
    assert len(_IN_FLIGHT_TASKS) == 0


@pytest.mark.asyncio
async def test_drain_in_flight_tasks_logs_warning_on_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    inner_started = asyncio.Event()
    release_gate = asyncio.Event()

    async def _delayed_cancel_honor() -> None:
        inner_started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await release_gate.wait()
            raise

    task = asyncio.create_task(_delayed_cancel_honor())
    _IN_FLIGHT_TASKS.add(task)
    task.add_done_callback(_IN_FLIGHT_TASKS.discard)
    await inner_started.wait()

    try:
        with caplog.at_level("WARNING", logger="app.services.eval_runner"):
            await drain_in_flight_tasks(timeout_s=0.2)
        assert any("did not finish" in record.getMessage() for record in caplog.records)
    finally:
        release_gate.set()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, timeout=1.0)
        _IN_FLIGHT_TASKS.discard(task)
