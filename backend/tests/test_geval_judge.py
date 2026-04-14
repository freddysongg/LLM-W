from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric
from app.services.eval import GEvalJudge, JudgeError, OpenAIJudge
from app.services.eval.geval import _EvalSteps, _generate_steps_openai
from app.services.eval.openai_judge import _JudgeLLMOutput


def _example(*, verdict: str, prompt: str = "p", output: str = "o") -> dict[str, Any]:
    return {
        "input": EvaluationCase(prompt=prompt, output=output).model_dump(),
        "verdict": verdict,
        "reasoning": "because reasons",
    }


def _build_rubric(
    *,
    judge_model_pin: str = "gpt-4o-mini-2024-07-18",
    description: str = "measures faithfulness of the output",
) -> Rubric:
    return Rubric.model_validate(
        {
            "id": "faithfulness",
            "version": "1.2.3",
            "description": description,
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
            "judge_model_pin": judge_model_pin,
            "research_basis": ["R1"],
        }
    )


def _build_case(
    *, prompt: str = "Summarise the article", output: str = "Sky is blue"
) -> EvaluationCase:
    return EvaluationCase(prompt=prompt, output=output, reference="The sky is blue.")


def _valid_llm_output() -> _JudgeLLMOutput:
    return _JudgeLLMOutput(
        reasoning="The output restates the reference directly.",
        verdict="pass",
        per_criterion={"claims_supported": True, "no_hallucinated_facts": True},
    )


def _make_mock_completion(*, prompt_tokens: int = 100, completion_tokens: int = 30) -> MagicMock:
    completion = MagicMock()
    completion.usage.prompt_tokens = prompt_tokens
    completion.usage.completion_tokens = completion_tokens
    return completion


def _make_base_judge_with_mock_client(*, llm_output: _JudgeLLMOutput) -> OpenAIJudge:
    client = MagicMock()
    call = AsyncMock()
    call.return_value = (llm_output, _make_mock_completion())
    client.chat.completions.create_with_completion = call
    return OpenAIJudge(client=client)


@pytest.mark.asyncio
async def test_evaluate_generates_steps_once_per_rubric_version() -> None:
    rubric = _build_rubric()
    case = _build_case()
    generator = AsyncMock(return_value=["step 1", "step 2", "step 3"])
    base_judge = _make_base_judge_with_mock_client(llm_output=_valid_llm_output())
    judge = GEvalJudge(base_judge=base_judge, steps_generator=generator)

    await judge.evaluate(case=case, rubric=rubric)
    await judge.evaluate(case=case, rubric=rubric)

    assert generator.await_count == 1


@pytest.mark.asyncio
async def test_evaluate_regenerates_steps_when_rubric_changes() -> None:
    rubric_one = _build_rubric(description="first description")
    rubric_two = _build_rubric(description="second description")
    case = _build_case()
    generator = AsyncMock(return_value=["step 1", "step 2", "step 3"])
    base_judge = _make_base_judge_with_mock_client(llm_output=_valid_llm_output())
    judge = GEvalJudge(base_judge=base_judge, steps_generator=generator)

    await judge.evaluate(case=case, rubric=rubric_one)
    await judge.evaluate(case=case, rubric=rubric_two)

    assert generator.await_count == 2


@pytest.mark.asyncio
async def test_eval_steps_appear_in_judge_prompt() -> None:
    rubric = _build_rubric()
    case = _build_case()
    generated_steps = [
        "Read the retrieved context carefully.",
        "Check each claim against the context.",
        "Flag any fabricated entities.",
    ]
    generator = AsyncMock(return_value=generated_steps)

    captured_messages: dict[str, list[dict[str, str]]] = {}

    class CapturingBase(OpenAIJudge):
        async def score_from_messages(
            self, *, messages: list[dict[str, str]], rubric: Rubric
        ) -> Score:
            captured_messages["messages"] = messages
            return Score(
                reasoning="captured",
                verdict="pass",
                per_criterion={"claims_supported": True, "no_hallucinated_facts": True},
                cost_usd=0.0,
                latency_ms=1,
                judge_model=rubric.judge_model_pin,
                rubric_version=rubric.version,
                response_hash="a" * 64,
            )

    judge = GEvalJudge(base_judge=CapturingBase(client=MagicMock()), steps_generator=generator)
    await judge.evaluate(case=case, rubric=rubric)

    system_message = captured_messages["messages"][0]
    assert system_message["role"] == "system"
    assert "Evaluation Steps:" in system_message["content"]
    for index, step in enumerate(generated_steps, start=1):
        assert f"{index}. {step}" in system_message["content"]


@pytest.mark.asyncio
async def test_evaluate_returns_valid_score() -> None:
    rubric = _build_rubric()
    case = _build_case()
    generator = AsyncMock(return_value=["step 1", "step 2", "step 3"])
    base_judge = _make_base_judge_with_mock_client(llm_output=_valid_llm_output())
    judge = GEvalJudge(base_judge=base_judge, steps_generator=generator)

    score = await judge.evaluate(case=case, rubric=rubric)

    assert isinstance(score, Score)
    assert score.verdict == "pass"
    assert score.reasoning == "The output restates the reference directly."
    assert score.per_criterion == {"claims_supported": True, "no_hallucinated_facts": True}
    assert score.judge_model == rubric.judge_model_pin
    assert score.rubric_version == rubric.version
    assert len(score.response_hash) == 64
    assert score.cost_usd >= 0.0
    assert score.latency_ms >= 0


@pytest.mark.asyncio
async def test_ticket_ac_200_mock_outputs_all_produce_valid_score() -> None:
    rubric = _build_rubric()
    generator = AsyncMock(return_value=["step 1", "step 2", "step 3", "step 4"])

    for index in range(200):
        case = _build_case(prompt=f"prompt {index}", output=f"output {index}")
        llm_output = _JudgeLLMOutput(
            reasoning=f"iteration {index} reasoning",
            verdict="pass" if index % 2 == 0 else "fail",
            per_criterion={
                "claims_supported": index % 2 == 0,
                "no_hallucinated_facts": index % 3 != 0,
            },
        )
        base_judge = _make_base_judge_with_mock_client(llm_output=llm_output)
        judge = GEvalJudge(base_judge=base_judge, steps_generator=generator)

        score = await judge.evaluate(case=case, rubric=rubric)

        assert isinstance(score, Score)
        assert score.verdict in {"pass", "fail"}
        assert len(score.response_hash) == 64


@pytest.mark.asyncio
async def test_steps_generator_rejects_too_few_steps() -> None:
    rubric = _build_rubric()
    case = _build_case()
    generator = AsyncMock(return_value=["only one", "only two"])
    base_judge = _make_base_judge_with_mock_client(llm_output=_valid_llm_output())
    judge = GEvalJudge(base_judge=base_judge, steps_generator=generator)

    with pytest.raises(JudgeError, match="between 3 and 7 steps"):
        await judge.evaluate(case=case, rubric=rubric)


@pytest.mark.asyncio
async def test_steps_generator_rejects_too_many_steps() -> None:
    rubric = _build_rubric()
    case = _build_case()
    generator = AsyncMock(return_value=[f"step {idx}" for idx in range(8)])
    base_judge = _make_base_judge_with_mock_client(llm_output=_valid_llm_output())
    judge = GEvalJudge(base_judge=base_judge, steps_generator=generator)

    with pytest.raises(JudgeError, match="between 3 and 7 steps"):
        await judge.evaluate(case=case, rubric=rubric)


@pytest.mark.asyncio
async def test_default_generator_wraps_validation_error_as_judge_error() -> None:
    rubric = _build_rubric()

    class _TwoItemModel(BaseModel):
        items: list[str]

    try:
        _TwoItemModel.model_validate({"items": 123})
    except ValidationError as caught:
        validation_exc = caught
    else:
        raise AssertionError("expected ValidationError from construction")

    bad_client = MagicMock()
    bad_call = AsyncMock(side_effect=validation_exc)
    bad_client.chat.completions.create = bad_call

    with pytest.raises(JudgeError, match="invalid G-Eval steps response"):
        await _generate_steps_openai(
            rubric,
            api_key_loader=lambda: "sk-test",
            client=bad_client,
        )


@pytest.mark.asyncio
async def test_default_generator_returns_steps_from_openai() -> None:
    rubric = _build_rubric()
    generated = _EvalSteps(steps=["read context", "check claims", "flag fabrications"])

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=generated)

    steps = await _generate_steps_openai(
        rubric,
        api_key_loader=lambda: "sk-test",
        client=client,
    )

    assert steps == ["read context", "check claims", "flag fabrications"]
    call_kwargs = client.chat.completions.create.await_args.kwargs
    assert call_kwargs["model"] == rubric.judge_model_pin
    assert call_kwargs["response_model"] is _EvalSteps


@pytest.mark.asyncio
async def test_default_generator_raises_when_api_key_missing() -> None:
    rubric = _build_rubric()

    with pytest.raises(JudgeError, match="not configured"):
        await _generate_steps_openai(
            rubric,
            api_key_loader=lambda: None,
            client=None,
        )


def test_eval_steps_schema_strips_whitespace_and_rejects_empty() -> None:
    cleaned = _EvalSteps(steps=["  step a  ", "step b", "step c"])
    assert cleaned.steps == ["step a", "step b", "step c"]

    with pytest.raises(ValueError, match="must not be empty"):
        _EvalSteps(steps=["valid", "   ", "also valid"])


def test_eval_steps_schema_enforces_bounds() -> None:
    with pytest.raises(ValidationError):
        _EvalSteps(steps=["one", "two"])

    with pytest.raises(ValidationError):
        _EvalSteps(steps=[f"step {i}" for i in range(8)])


@pytest.mark.asyncio
async def test_error_from_base_judge_propagates_as_judge_error() -> None:
    rubric = _build_rubric()
    case = _build_case()
    generator = AsyncMock(return_value=["step 1", "step 2", "step 3"])

    class FailingBase(OpenAIJudge):
        async def score_from_messages(
            self, *, messages: list[dict[str, str]], rubric: Rubric
        ) -> Score:
            raise JudgeError("upstream base judge failure")

    judge = GEvalJudge(
        base_judge=FailingBase(client=MagicMock()),
        steps_generator=generator,
    )

    with pytest.raises(JudgeError, match="upstream base judge failure"):
        await judge.evaluate(case=case, rubric=rubric)


@pytest.mark.asyncio
async def test_cache_key_differs_for_different_rubrics() -> None:
    rubric_one = _build_rubric(description="alpha")
    rubric_two = _build_rubric(description="beta")
    assert GEvalJudge._cache_key(rubric_one) != GEvalJudge._cache_key(rubric_two)


@pytest.mark.asyncio
async def test_cache_key_identical_for_equivalent_rubrics() -> None:
    rubric_one = _build_rubric()
    rubric_two = _build_rubric()
    assert GEvalJudge._cache_key(rubric_one) == GEvalJudge._cache_key(rubric_two)
