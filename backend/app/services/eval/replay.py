from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval_call import EvalCall
from app.models.eval_case import EvalCase
from app.models.rubric_version import RubricVersion
from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric
from app.services.eval.chainpoll import ChainPollJudge
from app.services.eval.judge import JudgeProvider
from app.services.eval.openai_judge import OpenAIJudge


class EvalCallNotFoundError(Exception):
    """Raised when replay is requested for an eval_call_id with no matching row."""


@dataclass(frozen=True)
class _OriginalEvalCallSnapshot:
    """Pure-data snapshot of an eval_calls row, safe across session rollbacks."""

    id: str
    eval_run_id: str
    case_id: str
    rubric_version_id: str
    judge_model: str
    tier: str
    verdict: str
    response_hash: str


@dataclass(frozen=True)
class ReplayOutcome:
    """Boundary-safe summary of a replay operation.

    `hash_matched=False` is a finding, not a failure — indicates judge drift
    across time for the (case_input, rubric_version, judge_model) triple.
    """

    original_eval_call_id: str
    new_eval_call_id: str
    original_response_hash: str
    new_response_hash: str
    verdict_changed: bool
    hash_matched: bool
    cost_usd: float
    latency_ms: int


def _default_judge_factory(rubric: Rubric) -> JudgeProvider:
    if rubric.chainpoll is not None:
        return ChainPollJudge(base_judge=OpenAIJudge())
    return OpenAIJudge()


def _parse_case_input(*, case_input_blob: str) -> EvaluationCase:
    payload = json.loads(case_input_blob)
    if not isinstance(payload, dict):
        raise ValueError("case_input must deserialize to a JSON object")
    return EvaluationCase.model_validate(payload)


def _parse_rubric(*, yaml_blob: str) -> Rubric:
    parsed = yaml.safe_load(yaml_blob)
    if not isinstance(parsed, dict):
        raise ValueError("rubric yaml_blob must deserialize to a mapping")
    return Rubric.model_validate(parsed)


def _serialise_per_criterion(*, per_criterion: dict[str, bool]) -> str:
    return json.dumps(per_criterion, sort_keys=True)


async def _load_original(*, session: AsyncSession, eval_call_id: str) -> _OriginalEvalCallSnapshot:
    original = await session.get(EvalCall, eval_call_id)
    if original is None:
        raise EvalCallNotFoundError(eval_call_id)
    return _OriginalEvalCallSnapshot(
        id=original.id,
        eval_run_id=original.eval_run_id,
        case_id=original.case_id,
        rubric_version_id=original.rubric_version_id,
        judge_model=original.judge_model,
        tier=original.tier,
        verdict=original.verdict,
        response_hash=original.response_hash,
    )


async def replay_eval_call(
    *,
    eval_call_id: str,
    session: AsyncSession,
    judge_factory: Callable[[Rubric], JudgeProvider] | None = None,
) -> ReplayOutcome:
    """Replay a stored eval_call; return outcome with hash match/divergence.

    The new eval_calls row is written inside an explicit transaction so the
    BEGIN IMMEDIATE listener serialises concurrent replayers. `judge_factory`
    is injectable for tests — production callers pass None to get the default
    OpenAIJudge / ChainPollJudge resolution driven by rubric.chainpoll.
    """
    original_snapshot = await _load_original(session=session, eval_call_id=eval_call_id)
    case_row = await session.get(EvalCase, original_snapshot.case_id)
    if case_row is None:
        raise EvalCallNotFoundError(
            f"eval_case {original_snapshot.case_id} "
            f"referenced by eval_call {eval_call_id} not found"
        )

    rubric_version_row = await session.get(RubricVersion, original_snapshot.rubric_version_id)
    if rubric_version_row is None:
        raise EvalCallNotFoundError(
            f"rubric_version {original_snapshot.rubric_version_id} "
            f"referenced by eval_call {eval_call_id} not found"
        )

    evaluation_case = _parse_case_input(case_input_blob=case_row.case_input)
    rubric = _parse_rubric(yaml_blob=rubric_version_row.yaml_blob)

    factory = judge_factory if judge_factory is not None else _default_judge_factory
    judge = factory(rubric)

    await session.rollback()

    new_score: Score = await judge.evaluate(case=evaluation_case, rubric=rubric)

    hash_matched = new_score.response_hash == original_snapshot.response_hash
    verdict_changed = new_score.verdict != original_snapshot.verdict

    new_eval_call_id = str(uuid.uuid4())
    per_criterion_serialised = _serialise_per_criterion(per_criterion=new_score.per_criterion)
    now_iso = datetime.now(UTC).isoformat()

    async with session.begin():
        new_row = EvalCall(
            id=new_eval_call_id,
            eval_run_id=original_snapshot.eval_run_id,
            case_id=original_snapshot.case_id,
            rubric_version_id=original_snapshot.rubric_version_id,
            judge_model=original_snapshot.judge_model,
            tier=original_snapshot.tier,
            verdict=new_score.verdict,
            reasoning=new_score.reasoning,
            per_criterion=per_criterion_serialised,
            response_hash=new_score.response_hash,
            cost_usd=new_score.cost_usd,
            latency_ms=new_score.latency_ms,
            replayed_from_id=original_snapshot.id,
            created_at=now_iso,
        )
        session.add(new_row)

    return ReplayOutcome(
        original_eval_call_id=original_snapshot.id,
        new_eval_call_id=new_eval_call_id,
        original_response_hash=original_snapshot.response_hash,
        new_response_hash=new_score.response_hash,
        verdict_changed=verdict_changed,
        hash_matched=hash_matched,
        cost_usd=new_score.cost_usd,
        latency_ms=new_score.latency_ms,
    )
