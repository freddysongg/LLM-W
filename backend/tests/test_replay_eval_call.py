from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import AsyncIterator, Callable
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.eval_call import EvalCall
from app.models.eval_case import EvalCase
from app.models.eval_run import EvalRun
from app.models.rubric import Rubric as RubricModel
from app.models.rubric_version import RubricVersion
from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric
from app.services.eval.judge import JudgeProvider
from app.services.eval.replay import (
    EvalCallNotFoundError,
    replay_eval_call,
)

_JUDGE_MODEL = "gpt-4o-mini-2024-07-18"
_TIER = "tier1"
_RUBRIC_VERSION_STRING = "1.0.0"
_ORIGINAL_REASONING = "the output matches the reference"
_ORIGINAL_VERDICT = "pass"
_ORIGINAL_PER_CRITERION: dict[str, bool] = {
    "claims_supported": True,
    "no_hallucinated_facts": True,
}

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


def _rubric_yaml_payload(*, with_chainpoll: bool = False) -> dict[str, Any]:
    pass_example = {
        "input": EvaluationCase(prompt="p", output="o").model_dump(),
        "verdict": "pass",
        "reasoning": "matches reference",
    }
    fail_example = {
        "input": EvaluationCase(prompt="p", output="o").model_dump(),
        "verdict": "fail",
        "reasoning": "contradicts reference",
    }
    payload: dict[str, Any] = {
        "id": "faithfulness",
        "version": _RUBRIC_VERSION_STRING,
        "description": "measures faithfulness of the output",
        "scale": "binary",
        "criteria": [
            {"name": "claims_supported", "description": "claims supported", "points": 2},
            {"name": "no_hallucinated_facts", "description": "no invented facts", "points": 3},
        ],
        "few_shot_examples": [
            pass_example,
            pass_example,
            fail_example,
            fail_example,
            pass_example,
        ],
        "judge_model_pin": _JUDGE_MODEL,
        "research_basis": ["R4"],
    }
    if with_chainpoll:
        payload["chainpoll"] = {"n": 3, "model": _JUDGE_MODEL, "temperature": 0.3}
    return payload


def _compute_response_hash(
    *,
    reasoning: str,
    verdict: str,
    per_criterion: dict[str, bool],
) -> str:
    payload: dict[str, object] = {
        "reasoning": reasoning,
        "verdict": verdict,
        "per_criterion": per_criterion,
    }
    serialised = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


def _build_score(
    *,
    reasoning: str = _ORIGINAL_REASONING,
    verdict: str = _ORIGINAL_VERDICT,
    per_criterion: dict[str, bool] | None = None,
    cost_usd: float = 0.0004,
    latency_ms: int = 250,
    rubric_version: str = _RUBRIC_VERSION_STRING,
) -> Score:
    resolved_per_criterion = per_criterion or _ORIGINAL_PER_CRITERION
    response_hash = _compute_response_hash(
        reasoning=reasoning,
        verdict=verdict,
        per_criterion=resolved_per_criterion,
    )
    return Score(
        reasoning=reasoning,
        verdict=verdict,  # type: ignore[arg-type]
        per_criterion=resolved_per_criterion,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        judge_model=_JUDGE_MODEL,
        rubric_version=rubric_version,
        response_hash=response_hash,
    )


class _StubJudge(JudgeProvider):
    """Deterministic JudgeProvider that returns a pre-built Score."""

    def __init__(
        self,
        *,
        scripted_score: Score,
        on_evaluate: Callable[[EvaluationCase, Rubric], None] | None = None,
    ) -> None:
        self._scripted_score = scripted_score
        self._on_evaluate = on_evaluate
        self.call_count = 0

    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        self.call_count += 1
        if self._on_evaluate is not None:
            self._on_evaluate(case, rubric)
        return self._scripted_score


def _make_factory(judge: _StubJudge) -> Callable[[Rubric], JudgeProvider]:
    def _factory(rubric: Rubric) -> JudgeProvider:
        _ = rubric
        return judge

    return _factory


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(_TRIGGER_NO_UPDATE))
        await conn.execute(text(_TRIGGER_NO_DELETE))

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        yield session

    await engine.dispose()


async def _seed(
    *,
    session: AsyncSession,
    with_chainpoll: bool = False,
    eval_call_id: str = "call-1",
    rubric_version_id: str = "rv-1",
) -> str:
    rubric_payload = _rubric_yaml_payload(with_chainpoll=with_chainpoll)
    yaml_blob = yaml.safe_dump(rubric_payload)

    rubric_row = RubricModel(
        id="rubric-1",
        name="faithfulness",
        description="measures faithfulness",
        research_basis=json.dumps(["R4"]),
        created_at="2026-04-14T00:00:00+00:00",
    )
    rubric_version_row = RubricVersion(
        id=rubric_version_id,
        rubric_id="rubric-1",
        version_number=1,
        yaml_blob=yaml_blob,
        content_hash="a" * 64,
        diff_from_prev=None,
        calibration_metrics=None,
        calibration_status="uncalibrated",
        judge_model_pin=_JUDGE_MODEL,
        created_at="2026-04-14T00:00:00+00:00",
    )
    eval_run = EvalRun(
        id="er-1",
        training_run_id=None,
        started_at="2026-04-14T00:00:00+00:00",
        completed_at=None,
        status="running",
        pass_rate=None,
        total_cost_usd=0.0,
        max_cost_usd=None,
    )
    case_payload = {
        "prompt": "Summarise the article",
        "output": "The article says the sky is blue.",
        "reference": "The sky is blue.",
        "retrieved_context": None,
        "conversation_history": None,
        "metadata": {},
    }
    eval_case = EvalCase(
        id="ec-1",
        eval_run_id="er-1",
        case_input=json.dumps(case_payload),
        input_hash="b" * 64,
    )
    original_hash = _compute_response_hash(
        reasoning=_ORIGINAL_REASONING,
        verdict=_ORIGINAL_VERDICT,
        per_criterion=_ORIGINAL_PER_CRITERION,
    )
    eval_call = EvalCall(
        id=eval_call_id,
        eval_run_id="er-1",
        case_id="ec-1",
        rubric_version_id=rubric_version_id,
        judge_model=_JUDGE_MODEL,
        tier=_TIER,
        verdict=_ORIGINAL_VERDICT,
        reasoning=_ORIGINAL_REASONING,
        per_criterion=json.dumps(_ORIGINAL_PER_CRITERION, sort_keys=True),
        response_hash=original_hash,
        cost_usd=0.0004,
        latency_ms=250,
        replayed_from_id=None,
        created_at="2026-04-14T00:00:00+00:00",
    )
    session.add_all([rubric_row, rubric_version_row, eval_run, eval_case, eval_call])
    await session.commit()
    session.expunge_all()
    return eval_call_id


async def test_replay_match_writes_new_row_with_same_hash(db_session: AsyncSession) -> None:
    original_id = await _seed(session=db_session)
    matching_score = _build_score()
    stub_judge = _StubJudge(scripted_score=matching_score)

    outcome = await replay_eval_call(
        eval_call_id=original_id,
        session=db_session,
        judge_factory=_make_factory(stub_judge),
    )

    assert outcome.hash_matched is True
    assert outcome.verdict_changed is False
    assert outcome.original_response_hash == outcome.new_response_hash
    assert stub_judge.call_count == 1

    new_row = await db_session.get(EvalCall, outcome.new_eval_call_id)
    assert new_row is not None
    assert new_row.replayed_from_id == original_id
    assert new_row.eval_run_id == "er-1"
    assert new_row.rubric_version_id == "rv-1"
    assert new_row.response_hash == outcome.original_response_hash


async def test_replay_divergence_writes_new_row_with_different_hash(
    db_session: AsyncSession,
) -> None:
    original_id = await _seed(session=db_session)
    divergent_score = _build_score(reasoning="entirely different chain of reasoning")
    stub_judge = _StubJudge(scripted_score=divergent_score)

    outcome = await replay_eval_call(
        eval_call_id=original_id,
        session=db_session,
        judge_factory=_make_factory(stub_judge),
    )

    assert outcome.hash_matched is False
    assert outcome.original_response_hash != outcome.new_response_hash

    new_row = await db_session.get(EvalCall, outcome.new_eval_call_id)
    assert new_row is not None
    assert new_row.response_hash == divergent_score.response_hash
    assert new_row.reasoning == divergent_score.reasoning
    assert new_row.replayed_from_id == original_id


async def test_replay_preserves_rubric_version(db_session: AsyncSession) -> None:
    original_id = await _seed(session=db_session, rubric_version_id="rv-1")

    rubric_v2 = RubricVersion(
        id="rv-2",
        rubric_id="rubric-1",
        version_number=2,
        yaml_blob=yaml.safe_dump(_rubric_yaml_payload()),
        content_hash="d" * 64,
        diff_from_prev=None,
        calibration_metrics=None,
        calibration_status="uncalibrated",
        judge_model_pin=_JUDGE_MODEL,
        created_at="2026-04-14T00:01:00+00:00",
    )
    db_session.add(rubric_v2)
    await db_session.commit()

    stub_judge = _StubJudge(scripted_score=_build_score())

    outcome = await replay_eval_call(
        eval_call_id=original_id,
        session=db_session,
        judge_factory=_make_factory(stub_judge),
    )

    new_row = await db_session.get(EvalCall, outcome.new_eval_call_id)
    assert new_row is not None
    assert new_row.rubric_version_id == "rv-1"


async def test_replay_nonexistent_id_raises(db_session: AsyncSession) -> None:
    stub_judge = _StubJudge(scripted_score=_build_score())
    with pytest.raises(EvalCallNotFoundError):
        await replay_eval_call(
            eval_call_id="does-not-exist",
            session=db_session,
            judge_factory=_make_factory(stub_judge),
        )


async def test_replay_chainpoll_rubric_uses_chainpoll_judge(db_session: AsyncSession) -> None:
    original_id = await _seed(session=db_session, with_chainpoll=True)

    observed_chainpoll: list[object] = []

    def _record(_case: EvaluationCase, rubric: Rubric) -> None:
        observed_chainpoll.append(rubric.chainpoll)

    stub_judge = _StubJudge(scripted_score=_build_score(), on_evaluate=_record)

    await replay_eval_call(
        eval_call_id=original_id,
        session=db_session,
        judge_factory=_make_factory(stub_judge),
    )

    assert len(observed_chainpoll) == 1
    assert observed_chainpoll[0] is not None


async def test_replay_never_updates_original_row(db_session: AsyncSession) -> None:
    original_id = await _seed(session=db_session)
    original_before = await db_session.get(EvalCall, original_id)
    assert original_before is not None
    baseline = {
        "verdict": original_before.verdict,
        "reasoning": original_before.reasoning,
        "response_hash": original_before.response_hash,
        "per_criterion": original_before.per_criterion,
        "cost_usd": original_before.cost_usd,
        "latency_ms": original_before.latency_ms,
        "replayed_from_id": original_before.replayed_from_id,
        "created_at": original_before.created_at,
    }
    db_session.expunge_all()

    divergent_score = _build_score(reasoning="wildly different reasoning")
    stub_judge = _StubJudge(scripted_score=divergent_score)

    await replay_eval_call(
        eval_call_id=original_id,
        session=db_session,
        judge_factory=_make_factory(stub_judge),
    )

    refreshed = await db_session.get(EvalCall, original_id)
    assert refreshed is not None
    assert refreshed.verdict == baseline["verdict"]
    assert refreshed.reasoning == baseline["reasoning"]
    assert refreshed.response_hash == baseline["response_hash"]
    assert refreshed.per_criterion == baseline["per_criterion"]
    assert refreshed.cost_usd == baseline["cost_usd"]
    assert refreshed.latency_ms == baseline["latency_ms"]
    assert refreshed.replayed_from_id == baseline["replayed_from_id"]
    assert refreshed.created_at == baseline["created_at"]


async def _run_cli_with_session(
    *,
    session: AsyncSession,
    argv: list[str],
    stub_judge: _StubJudge | None = None,
) -> int:
    from app.cli import eval_replay as eval_replay_module

    class _FactoryContext:
        async def __aenter__(self) -> AsyncSession:
            return session

        async def __aexit__(self, *_: object) -> None:
            return None

    def _factory() -> _FactoryContext:
        return _FactoryContext()

    parsed_eval_call_id = argv[-1]

    patches: list[object] = [
        patch("app.cli.eval_replay.async_session_factory", _factory),
    ]

    if stub_judge is not None:
        original_replay = eval_replay_module.replay_eval_call

        async def _patched_replay(**kwargs: object) -> object:
            kwargs["judge_factory"] = _make_factory(stub_judge)
            return await original_replay(**kwargs)  # type: ignore[misc]

        patches.append(patch("app.cli.eval_replay.replay_eval_call", _patched_replay))

    for active_patch in patches:
        active_patch.__enter__()  # type: ignore[attr-defined]
    try:
        return await eval_replay_module.run_eval_replay_command(eval_call_id=parsed_eval_call_id)
    finally:
        for active_patch in reversed(patches):
            active_patch.__exit__(None, None, None)  # type: ignore[attr-defined]


async def test_cli_replay_match_exit_0(
    db_session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_id = await _seed(session=db_session)
    stub_judge = _StubJudge(scripted_score=_build_score())

    exit_code = await _run_cli_with_session(
        session=db_session,
        argv=["eval", "replay", original_id],
        stub_judge=stub_judge,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[llmw] replay match: response_hash = " in captured.out
    assert "[llmw] new eval_call row: " in captured.out


async def test_cli_replay_divergence_exit_0(
    db_session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_id = await _seed(session=db_session)
    stub_judge = _StubJudge(
        scripted_score=_build_score(reasoning="divergent chain of thought for drift")
    )

    exit_code = await _run_cli_with_session(
        session=db_session,
        argv=["eval", "replay", original_id],
        stub_judge=stub_judge,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[llmw] replay divergence: stored=" in captured.out
    assert "[llmw] new eval_call row: " in captured.out


async def test_cli_replay_nonexistent_id_exit_2(
    db_session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"
    exit_code = await _run_cli_with_session(
        session=db_session,
        argv=["eval", "replay", missing_id],
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert f"[llmw] eval_call {missing_id} not found" in captured.err
    assert sys.stderr is not None


def test_cli_main_dispatches_eval_replay_subcommand() -> None:
    from app.cli import main as cli_main

    invoked_with: list[str] = []

    async def _fake_run(*, eval_call_id: str) -> int:
        invoked_with.append(eval_call_id)
        return 0

    with patch("app.cli.run_eval_replay_command", _fake_run):
        exit_code = cli_main(["eval", "replay", "the-id"])

    assert exit_code == 0
    assert invoked_with == ["the-id"]
