from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.events import event_bus
from app.models.eval_call import EvalCall
from app.models.eval_case import EvalCase
from app.models.eval_run import EvalRun
from app.models.rubric_version import RubricVersion
from app.schemas.eval import (
    EvalCallRow,
    EvalCallsPageResponse,
    EvalCaseRow,
    EvalRunDetailResponse,
    EvalRunListResponse,
    EvalRunSummary,
    EvaluationCase,
    EvaluationCasePayload,
    Score,
)
from app.schemas.rubric import Rubric
from app.services.eval.chainpoll import ChainPollJudge
from app.services.eval.judge import JudgeError, JudgeProvider
from app.services.eval.openai_judge import OpenAIJudge

logger = logging.getLogger(__name__)

_STATUS_PENDING: Literal["pending"] = "pending"
_STATUS_RUNNING: Literal["running"] = "running"
_STATUS_COMPLETED: Literal["completed"] = "completed"
_STATUS_FAILED: Literal["failed"] = "failed"
_STATUS_COST_CAPPED: Literal["cost_capped"] = "cost_capped"
_JUDGE_TIER_LLM: Literal["llm"] = "llm"
_JUDGE_TIER_ERROR: Literal["error"] = "error"
_VERDICT_PASS: Literal["pass"] = "pass"
_VERDICT_FAIL: Literal["fail"] = "fail"
_VERDICT_ERROR: Literal["error"] = "error"
_EVAL_CHANNEL: Literal["eval"] = "eval"
_EVENT_CASE_COMPLETED: Literal["case_completed"] = "case_completed"
_EVENT_CASE_FAILED: Literal["case_failed"] = "case_failed"
_EVENT_RUN_COMPLETED: Literal["run_completed"] = "run_completed"
_EVENT_COST_WARNING: Literal["cost_warning"] = "cost_warning"
_COST_WARNING_PCT = 0.80
_ORPHAN_REASON = "orphaned by server restart"
_ERROR_RESPONSE_HASH = "0" * 64

_DEFAULT_CALIBRATION_PATH = (
    Path(__file__).resolve().parents[3] / "eval" / "calibration" / "v1_raw.jsonl"
)
_DEFAULT_CASE_LIMIT = 5

_IN_FLIGHT_TASKS: set[asyncio.Task[None]] = set()


class EvalOrchestrationError(Exception):
    """Raised when an orchestration precondition fails (e.g. missing rubric)."""


class RubricVersionNotFoundError(EvalOrchestrationError):
    def __init__(self, rubric_version_id: str) -> None:
        super().__init__(f"rubric_version not found: {rubric_version_id}")
        self.rubric_version_id = rubric_version_id


class EvalCallCorruptError(Exception):
    """Raised when a persisted eval_call row has an unparseable blob."""

    def __init__(self, *, call_id: str, field_name: str, cause: Exception) -> None:
        super().__init__(f"corrupt {field_name} in eval_call {call_id}: {cause}")
        self.call_id = call_id
        self.field_name = field_name


class EvalCaseCorruptError(Exception):
    """Raised when a persisted eval_case row has an unparseable case_input blob."""

    def __init__(self, *, case_id: str, cause: Exception) -> None:
        super().__init__(f"corrupt case_input in eval_case {case_id}: {cause}")
        self.case_id = case_id


class EvalRunNotFoundError(Exception):
    def __init__(self, eval_run_id: str) -> None:
        super().__init__(f"eval_run not found: {eval_run_id}")
        self.eval_run_id = eval_run_id


@dataclass(frozen=True)
class _RubricVersionSnapshot:
    id: str
    rubric_id: str
    yaml_blob: str
    judge_model_pin: str


@dataclass(frozen=True)
class _CaseSnapshot:
    id: str
    case_input: EvaluationCase
    input_hash: str


JudgeFactory = Callable[[Rubric], JudgeProvider]
CaseProvider = Callable[[], Awaitable[list[EvaluationCase]]]


def _default_judge_factory(rubric: Rubric) -> JudgeProvider:
    if rubric.chainpoll is not None:
        return ChainPollJudge(base_judge=OpenAIJudge())
    return OpenAIJudge()


async def _default_case_provider() -> list[EvaluationCase]:
    if not _DEFAULT_CALIBRATION_PATH.exists():
        raise EvalOrchestrationError(
            f"default calibration set missing at {_DEFAULT_CALIBRATION_PATH}"
        )
    try:
        lines = _DEFAULT_CALIBRATION_PATH.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise EvalOrchestrationError(
            f"failed to read calibration set at {_DEFAULT_CALIBRATION_PATH}: {exc}"
        ) from exc
    cases: list[EvaluationCase] = []
    for row_index, raw_line in enumerate(lines[:_DEFAULT_CASE_LIMIT]):
        try:
            payload = json.loads(raw_line)
            cases.append(
                EvaluationCase(
                    prompt=payload["prompt"],
                    output=payload["output"],
                    reference=payload.get("reference"),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise EvalOrchestrationError(f"malformed calibration row {row_index}: {exc}") from exc
    return cases


def _serialise_case_input(*, case: EvaluationCase) -> str:
    return case.model_dump_json()


def _hash_case_input(*, serialised: str) -> str:
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _serialise_per_criterion(*, per_criterion: dict[str, bool]) -> str:
    return json.dumps(per_criterion, sort_keys=True)


def _parse_rubric(*, yaml_blob: str) -> Rubric:
    parsed = yaml.safe_load(yaml_blob)
    if not isinstance(parsed, dict):
        raise EvalOrchestrationError("rubric yaml_blob must deserialize to a mapping")
    return Rubric.model_validate(parsed)


async def _load_rubric_versions(
    *,
    session: AsyncSession,
    rubric_version_ids: list[str],
) -> list[_RubricVersionSnapshot]:
    result = await session.execute(
        select(RubricVersion).where(RubricVersion.id.in_(rubric_version_ids))
    )
    rows = result.scalars().all()
    by_id = {row.id: row for row in rows}
    snapshots: list[_RubricVersionSnapshot] = []
    for version_id in rubric_version_ids:
        row = by_id.get(version_id)
        if row is None:
            raise RubricVersionNotFoundError(version_id)
        snapshots.append(
            _RubricVersionSnapshot(
                id=row.id,
                rubric_id=row.rubric_id,
                yaml_blob=row.yaml_blob,
                judge_model_pin=row.judge_model_pin,
            )
        )
    await session.rollback()
    return snapshots


async def create_eval_run_row(
    *,
    session: AsyncSession,
    training_run_id: str | None,
    max_cost_usd: float | None,
    rubric_version_ids: list[str] | None = None,
) -> EvalRun:
    if rubric_version_ids:
        await _load_rubric_versions(session=session, rubric_version_ids=rubric_version_ids)
    now_iso = datetime.now(UTC).isoformat()
    eval_run = EvalRun(
        id=str(uuid.uuid4()),
        training_run_id=training_run_id,
        started_at=now_iso,
        completed_at=None,
        status=_STATUS_PENDING,
        pass_rate=None,
        total_cost_usd=0.0,
        max_cost_usd=max_cost_usd,
    )
    await session.rollback()
    async with session.begin():
        session.add(eval_run)
    return eval_run


async def _materialise_cases(
    *,
    session: AsyncSession,
    eval_run_id: str,
    cases: Iterable[EvaluationCase],
) -> list[_CaseSnapshot]:
    snapshots: list[_CaseSnapshot] = []
    await session.rollback()
    async with session.begin():
        for case in cases:
            serialised = _serialise_case_input(case=case)
            row = EvalCase(
                id=str(uuid.uuid4()),
                eval_run_id=eval_run_id,
                case_input=serialised,
                input_hash=_hash_case_input(serialised=serialised),
            )
            session.add(row)
            snapshots.append(_CaseSnapshot(id=row.id, case_input=case, input_hash=row.input_hash))
    return snapshots


async def _publish(
    *,
    project_id: str,
    event: str,
    eval_run_id: str,
    payload: dict[str, object],
) -> None:
    envelope = {
        "channel": _EVAL_CHANNEL,
        "event": event,
        "runId": eval_run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    await event_bus.publish(event_type=f"project.{project_id}.ws", payload=envelope)


async def _persist_eval_call(
    *,
    session: AsyncSession,
    eval_run_id: str,
    case_id: str,
    rubric_version_id: str,
    score: Score,
) -> EvalCall:
    now_iso = datetime.now(UTC).isoformat()
    row = EvalCall(
        id=str(uuid.uuid4()),
        eval_run_id=eval_run_id,
        case_id=case_id,
        rubric_version_id=rubric_version_id,
        judge_model=score.judge_model,
        tier=_JUDGE_TIER_LLM,
        verdict=score.verdict,
        reasoning=score.reasoning,
        per_criterion=_serialise_per_criterion(per_criterion=score.per_criterion),
        response_hash=score.response_hash,
        cost_usd=score.cost_usd,
        latency_ms=score.latency_ms,
        replayed_from_id=None,
        created_at=now_iso,
    )
    await session.rollback()
    async with session.begin():
        session.add(row)
    return row


async def _persist_error_call(
    *,
    session: AsyncSession,
    eval_run_id: str,
    case_id: str,
    rubric_version_id: str,
    judge_model_pin: str,
    error_message: str,
) -> EvalCall:
    now_iso = datetime.now(UTC).isoformat()
    row = EvalCall(
        id=str(uuid.uuid4()),
        eval_run_id=eval_run_id,
        case_id=case_id,
        rubric_version_id=rubric_version_id,
        judge_model=judge_model_pin,
        tier=_JUDGE_TIER_ERROR,
        verdict=_VERDICT_ERROR,
        reasoning=error_message,
        per_criterion=None,
        response_hash=_ERROR_RESPONSE_HASH,
        cost_usd=0.0,
        latency_ms=None,
        replayed_from_id=None,
        created_at=now_iso,
    )
    await session.rollback()
    async with session.begin():
        session.add(row)
    return row


async def _update_run_totals(
    *,
    session: AsyncSession,
    eval_run_id: str,
    total_cost_usd: float,
    pass_count: int,
    total_count: int,
    status: str,
    mark_complete: bool,
) -> None:
    await session.rollback()
    async with session.begin():
        eval_run = await session.get(EvalRun, eval_run_id)
        if eval_run is None:
            return
        eval_run.total_cost_usd = total_cost_usd
        eval_run.pass_rate = (pass_count / total_count) if total_count > 0 else None
        eval_run.status = status
        if mark_complete:
            eval_run.completed_at = datetime.now(UTC).isoformat()


@dataclass
class _EvaluationCursor:
    pass_count: int = 0
    fail_count: int = 0
    failed_pairs: int = 0
    total_cost_usd: float = 0.0
    is_cost_warning_sent: bool = False
    is_cost_cap_hit: bool = False


async def _evaluate_pair(
    *,
    case_snapshot: _CaseSnapshot,
    rubric_snapshot: _RubricVersionSnapshot,
    judge_factory: JudgeFactory,
) -> Score:
    rubric = _parse_rubric(yaml_blob=rubric_snapshot.yaml_blob)
    judge = judge_factory(rubric)
    return await judge.evaluate(case=case_snapshot.case_input, rubric=rubric)


async def _maybe_emit_cost_warning(
    *,
    cursor: _EvaluationCursor,
    max_cost_usd: float | None,
    eval_run_id: str,
    project_id: str,
) -> None:
    if max_cost_usd is None or cursor.is_cost_warning_sent:
        return
    if cursor.total_cost_usd < _COST_WARNING_PCT * max_cost_usd:
        return
    cursor.is_cost_warning_sent = True
    await _publish(
        project_id=project_id,
        event=_EVENT_COST_WARNING,
        eval_run_id=eval_run_id,
        payload={
            "evalRunId": eval_run_id,
            "currentCostUsd": cursor.total_cost_usd,
            "maxCostUsd": max_cost_usd,
            "warningPct": _COST_WARNING_PCT,
        },
    )


def _is_cost_cap_breached(*, cursor: _EvaluationCursor, max_cost_usd: float | None) -> bool:
    if max_cost_usd is None:
        return False
    return cursor.total_cost_usd >= max_cost_usd


async def _emit_case_completed(
    *,
    project_id: str,
    eval_run_id: str,
    case_snapshot: _CaseSnapshot,
    rubric_snapshot: _RubricVersionSnapshot,
    call_id: str,
    score: Score,
) -> None:
    await _publish(
        project_id=project_id,
        event=_EVENT_CASE_COMPLETED,
        eval_run_id=eval_run_id,
        payload={
            "evalRunId": eval_run_id,
            "caseId": case_snapshot.id,
            "rubricVersionId": rubric_snapshot.id,
            "evalCallId": call_id,
            "verdict": score.verdict,
            "costUsd": score.cost_usd,
            "latencyMs": score.latency_ms,
        },
    )


async def _emit_case_failed(
    *,
    project_id: str,
    eval_run_id: str,
    case_snapshot: _CaseSnapshot,
    rubric_snapshot: _RubricVersionSnapshot,
    call_id: str,
    error_message: str,
) -> None:
    await _publish(
        project_id=project_id,
        event=_EVENT_CASE_FAILED,
        eval_run_id=eval_run_id,
        payload={
            "evalRunId": eval_run_id,
            "caseId": case_snapshot.id,
            "rubricVersionId": rubric_snapshot.id,
            "evalCallId": call_id,
            "errorMessage": error_message,
        },
    )


async def _handle_judge_failure(
    *,
    session: AsyncSession,
    project_id: str,
    eval_run_id: str,
    case_snapshot: _CaseSnapshot,
    rubric_snapshot: _RubricVersionSnapshot,
    cursor: _EvaluationCursor,
    exc: JudgeError,
) -> None:
    logger.warning(
        "judge failure for case=%s rubric_version=%s: %s",
        case_snapshot.id,
        rubric_snapshot.id,
        exc,
    )
    call = await _persist_error_call(
        session=session,
        eval_run_id=eval_run_id,
        case_id=case_snapshot.id,
        rubric_version_id=rubric_snapshot.id,
        judge_model_pin=rubric_snapshot.judge_model_pin,
        error_message=str(exc),
    )
    cursor.failed_pairs += 1
    await _emit_case_failed(
        project_id=project_id,
        eval_run_id=eval_run_id,
        case_snapshot=case_snapshot,
        rubric_snapshot=rubric_snapshot,
        call_id=call.id,
        error_message=str(exc),
    )


async def _record_pair_success(
    *,
    session: AsyncSession,
    project_id: str,
    eval_run_id: str,
    case_snapshot: _CaseSnapshot,
    rubric_snapshot: _RubricVersionSnapshot,
    cursor: _EvaluationCursor,
    max_cost_usd: float | None,
    score: Score,
) -> None:
    call = await _persist_eval_call(
        session=session,
        eval_run_id=eval_run_id,
        case_id=case_snapshot.id,
        rubric_version_id=rubric_snapshot.id,
        score=score,
    )
    if score.verdict == _VERDICT_PASS:
        cursor.pass_count += 1
    else:
        cursor.fail_count += 1
    cursor.total_cost_usd += score.cost_usd
    await _emit_case_completed(
        project_id=project_id,
        eval_run_id=eval_run_id,
        case_snapshot=case_snapshot,
        rubric_snapshot=rubric_snapshot,
        call_id=call.id,
        score=score,
    )
    await _maybe_emit_cost_warning(
        cursor=cursor,
        max_cost_usd=max_cost_usd,
        eval_run_id=eval_run_id,
        project_id=project_id,
    )
    if _is_cost_cap_breached(cursor=cursor, max_cost_usd=max_cost_usd):
        cursor.is_cost_cap_hit = True


async def _process_one_pair(
    *,
    session: AsyncSession,
    project_id: str,
    eval_run_id: str,
    case_snapshot: _CaseSnapshot,
    rubric_snapshot: _RubricVersionSnapshot,
    judge_factory: JudgeFactory,
    cursor: _EvaluationCursor,
    max_cost_usd: float | None,
) -> None:
    try:
        score = await _evaluate_pair(
            case_snapshot=case_snapshot,
            rubric_snapshot=rubric_snapshot,
            judge_factory=judge_factory,
        )
    except JudgeError as exc:
        await _handle_judge_failure(
            session=session,
            project_id=project_id,
            eval_run_id=eval_run_id,
            case_snapshot=case_snapshot,
            rubric_snapshot=rubric_snapshot,
            cursor=cursor,
            exc=exc,
        )
        return
    await _record_pair_success(
        session=session,
        project_id=project_id,
        eval_run_id=eval_run_id,
        case_snapshot=case_snapshot,
        rubric_snapshot=rubric_snapshot,
        cursor=cursor,
        max_cost_usd=max_cost_usd,
        score=score,
    )


async def _run_pairs(
    *,
    session: AsyncSession,
    project_id: str,
    eval_run_id: str,
    case_snapshots: list[_CaseSnapshot],
    rubric_snapshots: list[_RubricVersionSnapshot],
    judge_factory: JudgeFactory,
    max_cost_usd: float | None,
) -> _EvaluationCursor:
    cursor = _EvaluationCursor()
    # O(|cases| * |rubric_versions|): pairwise by design; cost ceiling short-circuits both loops.
    for case_snapshot in case_snapshots:
        if cursor.is_cost_cap_hit:
            break
        for rubric_snapshot in rubric_snapshots:
            if cursor.is_cost_cap_hit:
                break
            await _process_one_pair(
                session=session,
                project_id=project_id,
                eval_run_id=eval_run_id,
                case_snapshot=case_snapshot,
                rubric_snapshot=rubric_snapshot,
                judge_factory=judge_factory,
                cursor=cursor,
                max_cost_usd=max_cost_usd,
            )
    return cursor


async def _emit_run_completed(
    *,
    project_id: str,
    eval_run_id: str,
    cursor: _EvaluationCursor,
    final_status: str,
) -> None:
    total_cases = cursor.pass_count + cursor.fail_count
    pass_rate = (cursor.pass_count / total_cases) if total_cases > 0 else None
    await _publish(
        project_id=project_id,
        event=_EVENT_RUN_COMPLETED,
        eval_run_id=eval_run_id,
        payload={
            "evalRunId": eval_run_id,
            "status": final_status,
            "passRate": pass_rate,
            "totalCostUsd": cursor.total_cost_usd,
            "totals": {
                "cases": total_cases,
                "pass": cursor.pass_count,
                "fail": cursor.fail_count,
                "failed_pairs": cursor.failed_pairs,
                "costUsdTotal": cursor.total_cost_usd,
            },
        },
    )


async def _finalize_success(
    *,
    session: AsyncSession,
    project_id: str,
    eval_run_id: str,
    cursor: _EvaluationCursor,
) -> None:
    total_cases = cursor.pass_count + cursor.fail_count
    final_status = _STATUS_COST_CAPPED if cursor.is_cost_cap_hit else _STATUS_COMPLETED
    await _update_run_totals(
        session=session,
        eval_run_id=eval_run_id,
        total_cost_usd=cursor.total_cost_usd,
        pass_count=cursor.pass_count,
        total_count=total_cases,
        status=final_status,
        mark_complete=True,
    )
    await _emit_run_completed(
        project_id=project_id,
        eval_run_id=eval_run_id,
        cursor=cursor,
        final_status=final_status,
    )


async def _finalize_failure(
    *,
    session: AsyncSession,
    project_id: str,
    eval_run_id: str,
) -> None:
    await _mark_failed(session=session, eval_run_id=eval_run_id)
    await _emit_run_completed(
        project_id=project_id,
        eval_run_id=eval_run_id,
        cursor=_EvaluationCursor(),
        final_status=_STATUS_FAILED,
    )


async def _drive_orchestration(
    *,
    session: AsyncSession,
    project_id: str,
    eval_run_id: str,
    rubric_version_ids: list[str],
    max_cost_usd: float | None,
    judge_factory: JudgeFactory,
    case_provider: CaseProvider,
) -> _EvaluationCursor:
    await _mark_running(session=session, eval_run_id=eval_run_id)
    rubric_snapshots = await _load_rubric_versions(
        session=session, rubric_version_ids=rubric_version_ids
    )
    cases = await case_provider()
    case_snapshots = await _materialise_cases(session=session, eval_run_id=eval_run_id, cases=cases)
    return await _run_pairs(
        session=session,
        project_id=project_id,
        eval_run_id=eval_run_id,
        case_snapshots=case_snapshots,
        rubric_snapshots=rubric_snapshots,
        judge_factory=judge_factory,
        max_cost_usd=max_cost_usd,
    )


async def execute_eval_run(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    project_id: str,
    eval_run_id: str,
    rubric_version_ids: list[str],
    max_cost_usd: float | None,
    judge_factory: JudgeFactory | None = None,
    case_provider: CaseProvider | None = None,
) -> None:
    """Run the orchestration loop for an already-persisted pending eval_run.

    Creates a dedicated AsyncSession for the lifetime of the orchestration so
    cleanup of the caller's request-scoped session does not abort the worker.
    Orchestration-level failures mark the run as failed so the UI can surface
    them; unexpected exceptions are also caught and converted to failed status
    to prevent the row from getting stuck in `running`.
    """
    resolved_judge_factory = judge_factory if judge_factory is not None else _default_judge_factory
    resolved_case_provider = case_provider if case_provider is not None else _default_case_provider

    async with session_factory() as session:
        try:
            cursor = await _drive_orchestration(
                session=session,
                project_id=project_id,
                eval_run_id=eval_run_id,
                rubric_version_ids=rubric_version_ids,
                max_cost_usd=max_cost_usd,
                judge_factory=resolved_judge_factory,
                case_provider=resolved_case_provider,
            )
        except EvalOrchestrationError as exc:
            logger.exception("eval orchestration aborted: %s", exc)
            await _finalize_failure(session=session, project_id=project_id, eval_run_id=eval_run_id)
            return
        except Exception as exc:
            logger.exception("unexpected eval orchestration failure: %s", exc)
            await _finalize_failure(session=session, project_id=project_id, eval_run_id=eval_run_id)
            return

        await _finalize_success(
            session=session,
            project_id=project_id,
            eval_run_id=eval_run_id,
            cursor=cursor,
        )


async def _mark_running(*, session: AsyncSession, eval_run_id: str) -> None:
    await session.rollback()
    async with session.begin():
        eval_run = await session.get(EvalRun, eval_run_id)
        if eval_run is not None:
            eval_run.status = _STATUS_RUNNING


async def _mark_failed(*, session: AsyncSession, eval_run_id: str) -> None:
    await session.rollback()
    async with session.begin():
        eval_run = await session.get(EvalRun, eval_run_id)
        if eval_run is not None:
            eval_run.status = _STATUS_FAILED
            eval_run.completed_at = datetime.now(UTC).isoformat()


def schedule_eval_run(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    project_id: str,
    eval_run_id: str,
    rubric_version_ids: list[str],
    max_cost_usd: float | None,
) -> asyncio.Task[None]:
    """Schedule the orchestrator as a detached asyncio task.

    The task is held in a module-level set and cleared on completion so the
    GC cannot collect a still-running coroutine.
    """
    task = asyncio.create_task(
        execute_eval_run(
            session_factory=session_factory,
            project_id=project_id,
            eval_run_id=eval_run_id,
            rubric_version_ids=rubric_version_ids,
            max_cost_usd=max_cost_usd,
        )
    )
    _IN_FLIGHT_TASKS.add(task)
    task.add_done_callback(_IN_FLIGHT_TASKS.discard)
    return task


async def drain_in_flight_tasks(timeout_s: float = 10.0) -> None:
    """Cancel and await any in-flight eval orchestration tasks on shutdown.

    A bounded wait prevents the FastAPI lifespan from hanging if a task does
    not respond to cancellation; stragglers are logged but not re-raised since
    each task is expected to surface ``CancelledError``.
    """
    snapshot = list(_IN_FLIGHT_TASKS)
    if not snapshot:
        return
    for task in snapshot:
        task.cancel()
    _done, pending = await asyncio.wait(
        snapshot,
        timeout=timeout_s,
        return_when=asyncio.ALL_COMPLETED,
    )
    if pending:
        logger.warning(
            "drain_in_flight_tasks: %d eval task(s) did not finish within %.1fs",
            len(pending),
            timeout_s,
        )


async def recover_stale_eval_runs(
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Mark any `running` eval_runs as failed on startup.

    A `running` row with no live asyncio task implies the previous server
    process crashed mid-flight; we flip it to failed and emit a terminal
    run_completed so any reconnecting client closes its progress state.
    """
    async with session_factory() as session:
        result = await session.execute(select(EvalRun).where(EvalRun.status == _STATUS_RUNNING))
        stale_runs = list(result.scalars().all())

    recovered_count = 0
    for eval_run in stale_runs:
        async with session_factory() as session:
            refreshed = await session.get(EvalRun, eval_run.id)
            if refreshed is None or refreshed.status != _STATUS_RUNNING:
                continue
            await session.rollback()
            async with session.begin():
                refreshed.status = _STATUS_FAILED
                refreshed.completed_at = datetime.now(UTC).isoformat()
        recovered_count += 1
        logger.info("recovered stale eval_run %s: %s", eval_run.id, _ORPHAN_REASON)
    return recovered_count


def _eval_run_summary(*, eval_run: EvalRun) -> EvalRunSummary:
    return EvalRunSummary.model_validate(eval_run)


def _parse_per_criterion(*, blob: str | None, call_id: str) -> dict[str, bool] | None:
    if blob is None:
        return None
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise EvalCallCorruptError(call_id=call_id, field_name="per_criterion", cause=exc) from exc
    if not isinstance(parsed, dict):
        raise EvalCallCorruptError(
            call_id=call_id,
            field_name="per_criterion",
            cause=TypeError("per_criterion blob is not a JSON object"),
        )
    return {str(k): bool(v) for k, v in parsed.items()}


def _parse_case_input(*, blob: str, case_id: str) -> EvaluationCasePayload:
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise EvalCaseCorruptError(case_id=case_id, cause=exc) from exc
    if not isinstance(parsed, dict):
        raise EvalCaseCorruptError(
            case_id=case_id, cause=TypeError("case_input blob is not a JSON object")
        )
    try:
        return EvaluationCasePayload.model_validate(parsed)
    except ValidationError as exc:
        raise EvalCaseCorruptError(case_id=case_id, cause=exc) from exc


def _eval_call_row(*, call: EvalCall) -> EvalCallRow:
    return EvalCallRow(
        id=call.id,
        eval_run_id=call.eval_run_id,
        case_id=call.case_id,
        rubric_version_id=call.rubric_version_id,
        judge_model=call.judge_model,
        tier=call.tier,
        verdict=call.verdict,
        reasoning=call.reasoning,
        per_criterion=_parse_per_criterion(blob=call.per_criterion, call_id=call.id),
        response_hash=call.response_hash,
        cost_usd=call.cost_usd,
        latency_ms=call.latency_ms,
        replayed_from_id=call.replayed_from_id,
        created_at=call.created_at,
    )


def _eval_case_row(*, case: EvalCase) -> EvalCaseRow:
    return EvalCaseRow(
        id=case.id,
        eval_run_id=case.eval_run_id,
        case_input=_parse_case_input(blob=case.case_input, case_id=case.id),
        input_hash=case.input_hash,
    )


async def list_runs(
    *,
    session: AsyncSession,
    training_run_id: str | None,
    limit: int,
    offset: int,
) -> EvalRunListResponse:
    count_stmt = select(func.count(EvalRun.id))
    query_stmt = select(EvalRun)
    if training_run_id is not None:
        count_stmt = count_stmt.where(EvalRun.training_run_id == training_run_id)
        query_stmt = query_stmt.where(EvalRun.training_run_id == training_run_id)
    total_result = await session.execute(count_stmt)
    total = int(total_result.scalar_one() or 0)
    rows_result = await session.execute(
        query_stmt.order_by(EvalRun.started_at.desc()).limit(limit).offset(offset)
    )
    rows = rows_result.scalars().all()
    return EvalRunListResponse(
        items=[_eval_run_summary(eval_run=row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_run(
    *,
    session: AsyncSession,
    eval_run_id: str,
) -> EvalRunDetailResponse:
    eval_run = await session.get(EvalRun, eval_run_id)
    if eval_run is None:
        raise EvalRunNotFoundError(eval_run_id)
    cases_result = await session.execute(
        select(EvalCase).where(EvalCase.eval_run_id == eval_run_id)
    )
    cases = cases_result.scalars().all()
    calls_result = await session.execute(
        select(EvalCall).where(EvalCall.eval_run_id == eval_run_id).order_by(EvalCall.created_at)
    )
    calls = calls_result.scalars().all()
    return EvalRunDetailResponse(
        run=_eval_run_summary(eval_run=eval_run),
        cases=[_eval_case_row(case=case) for case in cases],
        calls=[_eval_call_row(call=call) for call in calls],
    )


async def list_calls(
    *,
    session: AsyncSession,
    eval_run_id: str,
    limit: int,
    offset: int,
) -> EvalCallsPageResponse:
    eval_run = await session.get(EvalRun, eval_run_id)
    if eval_run is None:
        raise EvalRunNotFoundError(eval_run_id)
    count_result = await session.execute(
        select(func.count(EvalCall.id)).where(EvalCall.eval_run_id == eval_run_id)
    )
    total = int(count_result.scalar_one() or 0)
    rows_result = await session.execute(
        select(EvalCall)
        .where(EvalCall.eval_run_id == eval_run_id)
        .order_by(EvalCall.created_at)
        .limit(limit)
        .offset(offset)
    )
    rows = rows_result.scalars().all()
    return EvalCallsPageResponse(
        items=[_eval_call_row(call=row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
