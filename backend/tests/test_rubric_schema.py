from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.eval import EvaluationCase
from app.schemas.rubric import (
    ChainPollConfig,
    Criterion,
    FewShotExample,
    Rubric,
)


def _example(*, verdict: str, prompt: str = "p", output: str = "o") -> dict:
    return {
        "input": EvaluationCase(prompt=prompt, output=output).model_dump(),
        "verdict": verdict,
        "reasoning": "because reasons",
    }


def _valid_rubric_dict(**overrides) -> dict:
    base = {
        "id": "faithfulness",
        "version": "1.0.0",
        "description": "measures faithfulness of the output",
        "scale": "binary",
        "criteria": [
            {"name": "claims_supported", "description": "claims supported by ref", "points": 2},
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
        "research_basis": ["R1", "R3"],
    }
    base.update(overrides)
    return base


def test_valid_rubric_loads_cleanly() -> None:
    rubric = Rubric.model_validate(_valid_rubric_dict())
    assert rubric.id == "faithfulness"
    assert len(rubric.criteria) == 2
    assert len(rubric.few_shot_examples) == 5


def test_fewer_than_five_examples_raises() -> None:
    payload = _valid_rubric_dict(
        few_shot_examples=[
            _example(verdict="pass"),
            _example(verdict="fail"),
            _example(verdict="pass"),
            _example(verdict="fail"),
        ]
    )
    with pytest.raises(ValidationError, match=r"rubric requires ≥5 few-shot examples, got 4"):
        Rubric.model_validate(payload)


def test_all_pass_examples_raises() -> None:
    payload = _valid_rubric_dict(few_shot_examples=[_example(verdict="pass") for _ in range(5)])
    with pytest.raises(
        ValidationError, match="few-shot examples must include at least one 'fail' instance"
    ):
        Rubric.model_validate(payload)


def test_all_fail_examples_raises() -> None:
    payload = _valid_rubric_dict(few_shot_examples=[_example(verdict="fail") for _ in range(5)])
    with pytest.raises(
        ValidationError, match="few-shot examples must include at least one 'pass' instance"
    ):
        Rubric.model_validate(payload)


def test_judge_model_pin_latest_is_rejected() -> None:
    payload = _valid_rubric_dict(judge_model_pin="gpt-4o-latest")
    with pytest.raises(ValidationError, match="'-latest' aliases are forbidden"):
        Rubric.model_validate(payload)


def test_chainpoll_model_latest_is_rejected() -> None:
    payload = _valid_rubric_dict(
        chainpoll={"n": 3, "model": "gpt-4o-latest", "temperature": 0.3},
    )
    with pytest.raises(ValidationError, match="'-latest' aliases are forbidden"):
        Rubric.model_validate(payload)


def test_research_basis_invalid_id_raises() -> None:
    payload = _valid_rubric_dict(research_basis=["R1", "not-an-r-id"])
    with pytest.raises(
        ValidationError, match="research_basis entries must match R<digits>, got not-an-r-id"
    ):
        Rubric.model_validate(payload)


def test_likert_scale_is_rejected() -> None:
    payload = _valid_rubric_dict(scale="likert")
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)


def test_roundtrip_model_dump_validate_equality() -> None:
    rubric = Rubric.model_validate(_valid_rubric_dict())
    dumped = rubric.model_dump()
    rehydrated = Rubric.model_validate(dumped)
    assert rehydrated == rubric


def test_chainpoll_config_valid() -> None:
    config = ChainPollConfig(n=3, model="gpt-4o-mini-2024-07-18", temperature=0.3)
    assert config.n == 3


def test_chainpoll_config_latest_rejected_directly() -> None:
    with pytest.raises(ValidationError, match="'-latest' aliases are forbidden"):
        ChainPollConfig(n=3, model="gpt-4o-LATEST", temperature=0.3)


def test_criterion_points_bounds() -> None:
    with pytest.raises(ValidationError):
        Criterion(name="x", description="y", points=11)
    with pytest.raises(ValidationError):
        Criterion(name="x", description="y", points=-1)


def test_few_shot_example_reasoning_required() -> None:
    with pytest.raises(ValidationError):
        FewShotExample.model_validate(
            {
                "input": EvaluationCase(prompt="p", output="o").model_dump(),
                "verdict": "pass",
                "reasoning": "",
            }
        )


def test_rubric_id_pattern_enforced() -> None:
    payload = _valid_rubric_dict(id="InvalidId")
    with pytest.raises(ValidationError):
        Rubric.model_validate(payload)
