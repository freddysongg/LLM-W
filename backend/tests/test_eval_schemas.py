from __future__ import annotations

import random
import string

import pytest
from pydantic import ValidationError

from app.schemas.eval import EvaluationCase, Score

_HEX_ALPHABET = "0123456789abcdef"
_ROLE_CHOICES = ("system", "user", "assistant")
_VERDICT_CHOICES = ("pass", "fail")
_ROUND_TRIP_COUNT = 100
_RANDOM_SEED = 42


def _random_hash(rng: random.Random) -> str:
    return "".join(rng.choices(_HEX_ALPHABET, k=64))


def _random_text(rng: random.Random, *, min_len: int = 1, max_len: int = 80) -> str:
    length = rng.randint(min_len, max_len)
    return "".join(rng.choices(string.ascii_letters + " ", k=length)).strip() or "x"


def _random_metadata(rng: random.Random) -> dict[str, str]:
    entry_count = rng.randint(0, 4)
    return {
        f"key_{idx}_{rng.randint(0, 9999)}": _random_text(rng, min_len=1, max_len=20)
        for idx in range(entry_count)
    }


def _random_history(rng: random.Random) -> list[dict[str, str]] | None:
    if rng.random() < 0.3:
        return None
    turn_count = rng.randint(1, 5)
    return [
        {"role": rng.choice(_ROLE_CHOICES), "content": _random_text(rng)} for _ in range(turn_count)
    ]


def _random_per_criterion(rng: random.Random) -> dict[str, bool]:
    criterion_count = rng.randint(0, 6)
    return {f"criterion_{idx}": rng.choice([True, False]) for idx in range(criterion_count)}


def _random_evaluation_case(rng: random.Random) -> EvaluationCase:
    return EvaluationCase(
        prompt=_random_text(rng),
        output=_random_text(rng),
        reference=_random_text(rng) if rng.random() < 0.5 else None,
        retrieved_context=_random_text(rng) if rng.random() < 0.5 else None,
        conversation_history=_random_history(rng),
        metadata=_random_metadata(rng),
    )


def _random_score(rng: random.Random) -> Score:
    return Score(
        reasoning=_random_text(rng, min_len=3, max_len=200),
        verdict=rng.choice(_VERDICT_CHOICES),
        per_criterion=_random_per_criterion(rng),
        cost_usd=round(rng.uniform(0.0, 5.0), 6),
        latency_ms=rng.randint(0, 30_000),
        judge_model=f"gpt-4o-mini-{rng.randint(1000, 9999)}",
        rubric_version="".join(rng.choices(_HEX_ALPHABET, k=16)),
        response_hash=_random_hash(rng),
    )


def test_evaluation_case_round_trip_100() -> None:
    rng = random.Random(_RANDOM_SEED)
    for _ in range(_ROUND_TRIP_COUNT):
        original = _random_evaluation_case(rng)
        dumped = original.model_dump()
        rebuilt = EvaluationCase.model_validate(dumped)
        assert rebuilt == original


def test_score_round_trip_100() -> None:
    rng = random.Random(_RANDOM_SEED)
    for _ in range(_ROUND_TRIP_COUNT):
        original = _random_score(rng)
        dumped = original.model_dump()
        rebuilt = Score.model_validate(dumped)
        assert rebuilt == original


def test_score_json_schema_reasoning_before_verdict() -> None:
    schema = Score.model_json_schema()
    property_names = list(schema["properties"].keys())
    assert property_names[0] == "reasoning"
    assert property_names[1] == "verdict"


def test_score_empty_reasoning_rejected() -> None:
    with pytest.raises(ValidationError):
        Score(
            reasoning="",
            verdict="pass",
            per_criterion={},
            cost_usd=0.0,
            latency_ms=10,
            judge_model="gpt-4o-mini-2024-07-18",
            rubric_version="v1",
            response_hash="a" * 64,
        )


def test_score_whitespace_reasoning_rejected() -> None:
    with pytest.raises(ValidationError):
        Score(
            reasoning="   ",
            verdict="pass",
            per_criterion={},
            cost_usd=0.0,
            latency_ms=10,
            judge_model="gpt-4o-mini-2024-07-18",
            rubric_version="v1",
            response_hash="a" * 64,
        )


def test_score_invalid_verdict_rejected() -> None:
    with pytest.raises(ValidationError):
        Score.model_validate(
            {
                "reasoning": "reasoned carefully",
                "verdict": "maybe",
                "per_criterion": {},
                "cost_usd": 0.0,
                "latency_ms": 10,
                "judge_model": "gpt-4o-mini-2024-07-18",
                "rubric_version": "v1",
                "response_hash": "a" * 64,
            }
        )


def test_score_malformed_response_hash_rejected() -> None:
    with pytest.raises(ValidationError):
        Score(
            reasoning="reasoned carefully",
            verdict="pass",
            per_criterion={},
            cost_usd=0.0,
            latency_ms=10,
            judge_model="gpt-4o-mini-2024-07-18",
            rubric_version="v1",
            response_hash="a" * 32,
        )


def test_score_negative_cost_rejected() -> None:
    with pytest.raises(ValidationError):
        Score(
            reasoning="reasoned carefully",
            verdict="pass",
            per_criterion={},
            cost_usd=-0.01,
            latency_ms=10,
            judge_model="gpt-4o-mini-2024-07-18",
            rubric_version="v1",
            response_hash="a" * 64,
        )


def test_score_negative_latency_rejected() -> None:
    with pytest.raises(ValidationError):
        Score(
            reasoning="reasoned carefully",
            verdict="pass",
            per_criterion={},
            cost_usd=0.0,
            latency_ms=-1,
            judge_model="gpt-4o-mini-2024-07-18",
            rubric_version="v1",
            response_hash="a" * 64,
        )


def test_instructor_tool_schema_reasoning_first() -> None:
    instructor = pytest.importorskip("instructor")
    _, tool_schema = instructor.handle_response_model(Score)
    properties = tool_schema["tools"][0]["function"]["parameters"]["properties"]
    property_names = list(properties.keys())
    assert property_names[0] == "reasoning"
    assert property_names[1] == "verdict"
