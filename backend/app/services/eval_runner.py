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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.events import event_bus
from app.models.eval_call import EvalCall
from app.models.eval_case import EvalCase
from app.models.eval_run import EvalRun
from app.models.rubric_version import RubricVersion
from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric
from app.services.eval.chainpoll import ChainPollJudge
from app.services.eval.judge import JudgeError, JudgeProvider
from app.services.eval.openai_judge import OpenAIJudge

logger = logging.getLogger(__name__)

_STATUS_RUNNING: Literal["running"] = "running"
_STATUS_COMPLETED: Literal["completed"] = "completed"
_STATUS_FAILED: Literal["failed"] = "failed"
_JUDGE_TIER_LLM: Literal["llm"] = "llm"
_EVAL_CHANNEL: Literal["eval"] = "eval"
_EVENT_CASE_COMPLETED: Literal["case_completed"] = "case_completed"
_EVENT_RUN_COMPLETED: Literal["run_completed"] = "run_completed"
_EVENT_COST_WARNING: Literal["cost_warning"] = "cost_warning"
_COST_WARNING_PCT = 0.80

_DEFAULT_CALIBRATION_PATH = (
    Path(__file__).resolve().parents[3] / "eval" / "calibration" / "v1_raw.jsonl"
)
_DEFAULT_CASE_LIMIT = 5


class EvalOrchestrationError(Exception):
    """Raised when an orchestration precondition fails (e.g. missing rubric)."""


class RubricVersionNotFoundError(EvalOrchestrationError):
    def __init__(self, rubric_version_id: str) -> None:
        super().__init__(f"rubric_version not found: {rubric_version_id}")
        self.rubric_version_id = rubric_version_id


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
    lines = _DEFAULT_CALIBRATION_PATH.read_text(encoding="utf-8").splitlines()
    cases: list[EvaluationCase] = []
    for raw_line in lines[:_DEFAULT_CASE_LIMIT]:
        payload = json.loads(raw_line)
        cases.append(
            EvaluationCase(
                prompt=payload["prompt"],
                output=payload["output"],
                reference=payload.get("reference"),
            )
        )
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
) -> EvalRun:
    now_iso = datetime.now(UTC).isoformat()
    eval_run = EvalRun(
        id=str(uuid.uuid4()),
        training_run_id=training_run_id,
        started_at=now_iso,
        completed_at=None,
        status="pending",
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
        logger.warning(
            "judge failure for case=%s rubric_version=%s: %s",
            case_snapshot.id,
            rubric_snapshot.id,
            exc,
        )
        return

    call = await _persist_eval_call(
        session=session,
        eval_run_id=eval_run_id,
        case_id=case_snapshot.id,
        rubric_version_id=rubric_snapshot.id,
        score=score,
    )
    if score.verdict == "pass":
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
                "costUsdTotal": cursor.total_cost_usd,
            },
        },
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
    Swallowed judge errors are logged; orchestration-level failures mark the
    run as failed so the UI can surface them.
    """
    resolved_judge_factory = judge_factory if judge_factory is not None else _default_judge_factory
    resolved_case_provider = case_provider if case_provider is not None else _default_case_provider

    async with session_factory() as session:
        try:
            await _mark_running(session=session, eval_run_id=eval_run_id)
            rubric_snapshots = await _load_rubric_versions(
                session=session, rubric_version_ids=rubric_version_ids
            )
            cases = await resolved_case_provider()
            case_snapshots = await _materialise_cases(
                session=session, eval_run_id=eval_run_id, cases=cases
            )
            cursor = await _run_pairs(
                session=session,
                project_id=project_id,
                eval_run_id=eval_run_id,
                case_snapshots=case_snapshots,
                rubric_snapshots=rubric_snapshots,
                judge_factory=resolved_judge_factory,
                max_cost_usd=max_cost_usd,
            )
        except EvalOrchestrationError as exc:
            logger.exception("eval orchestration aborted: %s", exc)
            await _mark_failed(session=session, eval_run_id=eval_run_id)
            await _emit_run_completed(
                project_id=project_id,
                eval_run_id=eval_run_id,
                cursor=_EvaluationCursor(),
                final_status=_STATUS_FAILED,
            )
            return

        total_cases = cursor.pass_count + cursor.fail_count
        await _update_run_totals(
            session=session,
            eval_run_id=eval_run_id,
            total_cost_usd=cursor.total_cost_usd,
            pass_count=cursor.pass_count,
            total_count=total_cases,
            status=_STATUS_COMPLETED,
            mark_complete=True,
        )
        await _emit_run_completed(
            project_id=project_id,
            eval_run_id=eval_run_id,
            cursor=cursor,
            final_status=_STATUS_COMPLETED,
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

    The route returns immediately; the task owns its own DB session and
    outlives the HTTP request.
    """
    return asyncio.create_task(
        execute_eval_run(
            session_factory=session_factory,
            project_id=project_id,
            eval_run_id=eval_run_id,
            rubric_version_ids=rubric_version_ids,
            max_cost_usd=max_cost_usd,
        )
    )
