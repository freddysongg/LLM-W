from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric
from app.services.eval import ChainPollJudge, JudgeError, OpenAIJudge

_CHAINPOLL_MODEL = "gpt-4o-mini-2024-07-18"
_CHAINPOLL_TEMPERATURE = 0.3


def _example(*, verdict: str) -> dict[str, Any]:
    return {
        "input": EvaluationCase(prompt="p", output="o").model_dump(),
        "verdict": verdict,
        "reasoning": "because reasons",
    }


def _build_rubric(
    *,
    with_chainpoll: bool = True,
    n: int = 3,
    temperature: float = _CHAINPOLL_TEMPERATURE,
    model: str = _CHAINPOLL_MODEL,
) -> Rubric:
    payload: dict[str, Any] = {
        "id": "faithfulness",
        "version": "1.2.3",
        "description": "measures faithfulness of the output",
        "scale": "binary",
        "criteria": [
            {"name": "claims_supported", "description": "claims supported", "points": 2},
            {"name": "no_hallucinated_facts", "description": "no invented facts", "points": 3},
        ],
        "few_shot_examples": [
            _example(verdict="pass"),
            _example(verdict="pass"),
            _example(verdict="fail"),
            _example(verdict="fail"),
            _example(verdict="pass"),
        ],
        "judge_model_pin": "gpt-4o-mini-2024-07-18",
        "research_basis": ["R4"],
    }
    if with_chainpoll:
        payload["chainpoll"] = {"n": n, "model": model, "temperature": temperature}
    return Rubric.model_validate(payload)


def _build_case() -> EvaluationCase:
    return EvaluationCase(
        prompt="Summarise the article",
        output="The article says the sky is blue.",
        reference="The sky is blue.",
    )


def _build_score(
    *,
    verdict: str,
    reasoning: str,
    cost_usd: float = 0.0001,
    latency_ms: int = 400,
    response_hash_seed: str = "seed",
    per_criterion: dict[str, bool] | None = None,
) -> Score:
    resolved_per_criterion = per_criterion or {
        "claims_supported": verdict == "pass",
        "no_hallucinated_facts": True,
    }
    digest = hashlib.sha256(response_hash_seed.encode("utf-8")).hexdigest()
    return Score(
        reasoning=reasoning,
        verdict=verdict,  # type: ignore[arg-type]
        per_criterion=resolved_per_criterion,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        judge_model=_CHAINPOLL_MODEL,
        rubric_version="1.2.3",
        response_hash=digest,
    )


def _make_base_with_scripted_scores(scores: list[Score]) -> OpenAIJudge:
    judge = OpenAIJudge(client=MagicMock())
    iterator: Iterator[Score] = iter(scores)

    async def _scripted_score_from_messages(
        *,
        messages: list[dict[str, str]],
        rubric: Rubric,
        temperature: float = 0.0,
        judge_model: str | None = None,
    ) -> Score:
        del messages, rubric, temperature, judge_model
        return next(iterator)

    judge.score_from_messages = _scripted_score_from_messages  # type: ignore[method-assign]
    return judge


@pytest.mark.asyncio
async def test_chainpoll_none_delegates_to_base() -> None:
    rubric = _build_rubric(with_chainpoll=False)
    case = _build_case()
    delegated = _build_score(verdict="pass", reasoning="delegated", response_hash_seed="delegated")

    base = OpenAIJudge(client=MagicMock())
    base.evaluate = AsyncMock(return_value=delegated)  # type: ignore[method-assign]
    base.score_from_messages = AsyncMock()  # type: ignore[method-assign]

    judge = ChainPollJudge(base_judge=base)
    score = await judge.evaluate(case=case, rubric=rubric)

    assert score is delegated
    base.evaluate.assert_awaited_once_with(case=case, rubric=rubric)
    base.score_from_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_chainpoll_unanimous_pass() -> None:
    rubric = _build_rubric()
    case = _build_case()
    scripted = [
        _build_score(verdict="pass", reasoning="r1", response_hash_seed="a"),
        _build_score(verdict="pass", reasoning="r2", response_hash_seed="b"),
        _build_score(verdict="pass", reasoning="r3", response_hash_seed="c"),
    ]
    judge = ChainPollJudge(base_judge=_make_base_with_scripted_scores(scripted))

    score = await judge.evaluate(case=case, rubric=rubric)
    parsed = json.loads(score.reasoning)

    assert score.verdict == "pass"
    assert parsed["majority_verdict"] == "pass"
    assert parsed["majority_count"] == 3
    assert len(parsed["calls"]) == 3
    assert all(call["verdict"] == "pass" for call in parsed["calls"])


@pytest.mark.asyncio
async def test_chainpoll_unanimous_fail() -> None:
    rubric = _build_rubric()
    case = _build_case()
    scripted = [
        _build_score(verdict="fail", reasoning="r1", response_hash_seed="a"),
        _build_score(verdict="fail", reasoning="r2", response_hash_seed="b"),
        _build_score(verdict="fail", reasoning="r3", response_hash_seed="c"),
    ]
    judge = ChainPollJudge(base_judge=_make_base_with_scripted_scores(scripted))

    score = await judge.evaluate(case=case, rubric=rubric)
    parsed = json.loads(score.reasoning)

    assert score.verdict == "fail"
    assert parsed["majority_verdict"] == "fail"
    assert parsed["majority_count"] == 3
    assert all(call["verdict"] == "fail" for call in parsed["calls"])


@pytest.mark.asyncio
async def test_chainpoll_2_1_split_preserves_dissent() -> None:
    rubric = _build_rubric()
    case = _build_case()
    dissenting_reasoning = "the output fabricates a citation"
    scripted = [
        _build_score(
            verdict="pass", reasoning="output matches the reference", response_hash_seed="a"
        ),
        _build_score(verdict="fail", reasoning=dissenting_reasoning, response_hash_seed="b"),
        _build_score(
            verdict="pass", reasoning="output is faithful to the source", response_hash_seed="c"
        ),
    ]
    judge = ChainPollJudge(base_judge=_make_base_with_scripted_scores(scripted))

    score = await judge.evaluate(case=case, rubric=rubric)
    parsed = json.loads(score.reasoning)

    assert parsed["majority_verdict"] == "pass"
    assert parsed["majority_count"] == 2
    assert len(parsed["calls"]) == 3

    dissenting_calls = [call for call in parsed["calls"] if call["verdict"] == "fail"]
    assert len(dissenting_calls) == 1
    assert dissenting_calls[0]["reasoning"] == dissenting_reasoning

    expected_hash = hashlib.sha256(score.reasoning.encode("utf-8")).hexdigest()
    assert score.response_hash == expected_hash


@pytest.mark.asyncio
async def test_chainpoll_aggregates_cost_and_latency() -> None:
    rubric = _build_rubric()
    case = _build_case()
    scripted = [
        _build_score(
            verdict="pass",
            reasoning="r1",
            cost_usd=0.0001,
            latency_ms=100,
            response_hash_seed="a",
        ),
        _build_score(
            verdict="pass",
            reasoning="r2",
            cost_usd=0.0002,
            latency_ms=500,
            response_hash_seed="b",
        ),
        _build_score(
            verdict="fail",
            reasoning="r3",
            cost_usd=0.0003,
            latency_ms=250,
            response_hash_seed="c",
        ),
    ]
    judge = ChainPollJudge(base_judge=_make_base_with_scripted_scores(scripted))

    score = await judge.evaluate(case=case, rubric=rubric)

    assert score.cost_usd == pytest.approx(0.0006)
    assert score.latency_ms == 500
    assert score.judge_model == _CHAINPOLL_MODEL
    assert score.rubric_version == rubric.version


@pytest.mark.asyncio
async def test_chainpoll_propagates_single_call_failure() -> None:
    rubric = _build_rubric()
    case = _build_case()

    base = OpenAIJudge(client=MagicMock())
    call_outcomes: list[Score | Exception] = [
        _build_score(verdict="pass", reasoning="ok", response_hash_seed="a"),
        JudgeError("network exploded"),
        _build_score(verdict="pass", reasoning="ok", response_hash_seed="c"),
    ]
    iterator = iter(call_outcomes)

    async def _scripted(
        *,
        messages: list[dict[str, str]],
        rubric: Rubric,
        temperature: float = 0.0,
        judge_model: str | None = None,
    ) -> Score:
        del messages, rubric, temperature, judge_model
        outcome = next(iterator)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    base.score_from_messages = _scripted  # type: ignore[method-assign]
    judge = ChainPollJudge(base_judge=base)

    with pytest.raises(JudgeError, match=r"ChainPoll call 2/3 failed: network exploded"):
        await judge.evaluate(case=case, rubric=rubric)


@pytest.mark.asyncio
async def test_chainpoll_json_reasoning_is_valid_sorted_json() -> None:
    rubric = _build_rubric()
    case = _build_case()

    def _scripted_scores() -> list[Score]:
        return [
            _build_score(verdict="pass", reasoning="alpha", response_hash_seed="a"),
            _build_score(verdict="fail", reasoning="beta", response_hash_seed="b"),
            _build_score(verdict="pass", reasoning="gamma", response_hash_seed="c"),
        ]

    judge_one = ChainPollJudge(base_judge=_make_base_with_scripted_scores(_scripted_scores()))
    judge_two = ChainPollJudge(base_judge=_make_base_with_scripted_scores(_scripted_scores()))

    score_one = await judge_one.evaluate(case=case, rubric=rubric)
    score_two = await judge_two.evaluate(case=case, rubric=rubric)

    json.loads(score_one.reasoning)
    assert score_one.reasoning == score_two.reasoning
    assert score_one.response_hash == score_two.response_hash

    reserialised = json.dumps(json.loads(score_one.reasoning), sort_keys=True, ensure_ascii=True)
    assert reserialised == score_one.reasoning


@pytest.mark.asyncio
async def test_chainpoll_n_2_tie_break_uses_first_verdict() -> None:
    rubric = _build_rubric(n=2)
    case = _build_case()
    scripted = [
        _build_score(verdict="fail", reasoning="first", response_hash_seed="a"),
        _build_score(verdict="pass", reasoning="second", response_hash_seed="b"),
    ]
    judge = ChainPollJudge(base_judge=_make_base_with_scripted_scores(scripted))

    score = await judge.evaluate(case=case, rubric=rubric)
    parsed = json.loads(score.reasoning)

    assert score.verdict == "fail"
    assert parsed["majority_verdict"] == "fail"
    assert parsed["majority_count"] == 1
    assert parsed["calls"][0]["verdict"] == "fail"
    assert parsed["calls"][1]["verdict"] == "pass"


@pytest.mark.asyncio
async def test_chainpoll_passes_temperature_and_model_to_base() -> None:
    rubric = _build_rubric(temperature=0.5, model="gpt-4o-2024-11-20")
    case = _build_case()

    captured_kwargs: list[dict[str, object]] = []

    base = OpenAIJudge(client=MagicMock())
    iterator = iter(
        [
            _build_score(verdict="pass", reasoning="r1", response_hash_seed="a"),
            _build_score(verdict="pass", reasoning="r2", response_hash_seed="b"),
            _build_score(verdict="fail", reasoning="r3", response_hash_seed="c"),
        ]
    )

    async def _capture(
        *,
        messages: list[dict[str, str]],
        rubric: Rubric,
        temperature: float = 0.0,
        judge_model: str | None = None,
    ) -> Score:
        del messages, rubric
        captured_kwargs.append({"temperature": temperature, "judge_model": judge_model})
        return next(iterator)

    base.score_from_messages = _capture  # type: ignore[method-assign]
    judge = ChainPollJudge(base_judge=base)

    await judge.evaluate(case=case, rubric=rubric)

    assert len(captured_kwargs) == 3
    for kwargs in captured_kwargs:
        assert kwargs["temperature"] == 0.5
        assert kwargs["judge_model"] == "gpt-4o-2024-11-20"
