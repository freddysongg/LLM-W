from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric
from app.services.eval import JudgeError, OpenAIJudge
from app.services.eval.openai_judge import _JudgeLLMOutput


def _example(*, verdict: str, prompt: str = "p", output: str = "o") -> dict[str, Any]:
    return {
        "input": EvaluationCase(prompt=prompt, output=output).model_dump(),
        "verdict": verdict,
        "reasoning": "because reasons",
    }


def _build_rubric(*, judge_model_pin: str = "gpt-4o-mini-2024-07-18") -> Rubric:
    return Rubric.model_validate(
        {
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
            "judge_model_pin": judge_model_pin,
            "research_basis": ["R1", "R3"],
        }
    )


def _build_case() -> EvaluationCase:
    return EvaluationCase(
        prompt="Summarise the article",
        output="The article says the sky is blue.",
        reference="The sky is blue.",
    )


def _make_mock_completion(*, prompt_tokens: int = 120, completion_tokens: int = 40) -> MagicMock:
    completion = MagicMock()
    completion.usage.prompt_tokens = prompt_tokens
    completion.usage.completion_tokens = completion_tokens
    return completion


def _make_mock_client(
    *,
    llm_output: _JudgeLLMOutput,
    completion: MagicMock | None = None,
    side_effect: BaseException | None = None,
) -> MagicMock:
    client = MagicMock()
    call = AsyncMock()
    if side_effect is not None:
        call.side_effect = side_effect
    else:
        call.return_value = (llm_output, completion or _make_mock_completion())
    client.chat.completions.create_with_completion = call
    return client


def _valid_llm_output() -> _JudgeLLMOutput:
    return _JudgeLLMOutput(
        reasoning="The output restates the reference directly.",
        verdict="pass",
        per_criterion={"claims_supported": True, "no_hallucinated_facts": True},
    )


@pytest.mark.asyncio
async def test_evaluate_returns_valid_score_from_mock() -> None:
    rubric = _build_rubric()
    case = _build_case()

    for index in range(10):
        llm_output = _JudgeLLMOutput(
            reasoning=f"iteration {index} reasoning trace",
            verdict="pass" if index % 2 == 0 else "fail",
            per_criterion={
                "claims_supported": index % 2 == 0,
                "no_hallucinated_facts": True,
            },
        )
        client = _make_mock_client(llm_output=llm_output)
        judge = OpenAIJudge(client=client)

        score = await judge.evaluate(case=case, rubric=rubric)

        assert isinstance(score, Score)
        assert score.verdict == llm_output.verdict
        assert score.reasoning == llm_output.reasoning
        assert score.per_criterion == llm_output.per_criterion
        assert score.judge_model == rubric.judge_model_pin
        assert score.rubric_version == rubric.version
        assert len(score.response_hash) == 64
        assert score.cost_usd >= 0.0
        assert score.latency_ms >= 0


@pytest.mark.asyncio
async def test_evaluate_raises_on_unsupported_model() -> None:
    rubric = _build_rubric(judge_model_pin="gpt-3.5-turbo-0125")
    case = _build_case()
    judge = OpenAIJudge(client=_make_mock_client(llm_output=_valid_llm_output()))

    with pytest.raises(JudgeError, match="unsupported judge model: gpt-3.5-turbo-0125"):
        await judge.evaluate(case=case, rubric=rubric)


@pytest.mark.asyncio
async def test_evaluate_raises_on_missing_api_key() -> None:
    rubric = _build_rubric()
    case = _build_case()
    judge = OpenAIJudge(api_key_loader=lambda: None)

    with pytest.raises(JudgeError, match="not configured"):
        await judge.evaluate(case=case, rubric=rubric)


@pytest.mark.asyncio
async def test_evaluate_computes_cost_from_usage() -> None:
    rubric = _build_rubric(judge_model_pin="gpt-4o-mini-2024-07-18")
    case = _build_case()
    completion = _make_mock_completion(prompt_tokens=1000, completion_tokens=500)
    client = _make_mock_client(llm_output=_valid_llm_output(), completion=completion)
    judge = OpenAIJudge(client=client)

    score = await judge.evaluate(case=case, rubric=rubric)

    expected_cost = (1000 / 1000.0) * 0.00015 + (500 / 1000.0) * 0.0006
    assert score.cost_usd == pytest.approx(expected_cost)


@pytest.mark.asyncio
async def test_evaluate_computes_cost_for_gpt_4o() -> None:
    rubric = _build_rubric(judge_model_pin="gpt-4o-2024-11-20")
    case = _build_case()
    completion = _make_mock_completion(prompt_tokens=2000, completion_tokens=200)
    client = _make_mock_client(llm_output=_valid_llm_output(), completion=completion)
    judge = OpenAIJudge(client=client)

    score = await judge.evaluate(case=case, rubric=rubric)

    expected_cost = (2000 / 1000.0) * 0.005 + (200 / 1000.0) * 0.015
    assert score.cost_usd == pytest.approx(expected_cost)


@pytest.mark.asyncio
async def test_evaluate_captures_latency_ms() -> None:
    rubric = _build_rubric()
    case = _build_case()
    client = _make_mock_client(llm_output=_valid_llm_output())
    judge = OpenAIJudge(client=client)

    monotonic_values = iter([100.0, 100.25])

    with patch(
        "app.services.eval.openai_judge.time.monotonic",
        side_effect=lambda: next(monotonic_values),
    ):
        score = await judge.evaluate(case=case, rubric=rubric)

    assert score.latency_ms == 250


@pytest.mark.asyncio
async def test_evaluate_fills_rubric_version_and_judge_model() -> None:
    rubric = _build_rubric(judge_model_pin="gpt-4o-mini")
    case = _build_case()
    client = _make_mock_client(llm_output=_valid_llm_output())
    judge = OpenAIJudge(client=client)

    score = await judge.evaluate(case=case, rubric=rubric)

    assert score.judge_model == "gpt-4o-mini"
    assert score.rubric_version == "1.2.3"
    create_call = client.chat.completions.create_with_completion
    passed_model = create_call.await_args.kwargs["model"]
    assert passed_model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_evaluate_computes_response_hash() -> None:
    rubric = _build_rubric()
    case = _build_case()
    llm_output = _valid_llm_output()

    client_one = _make_mock_client(llm_output=llm_output)
    client_two = _make_mock_client(llm_output=llm_output)

    score_one = await OpenAIJudge(client=client_one).evaluate(case=case, rubric=rubric)
    score_two = await OpenAIJudge(client=client_two).evaluate(case=case, rubric=rubric)

    assert score_one.response_hash == score_two.response_hash
    assert len(score_one.response_hash) == 64
    int(score_one.response_hash, 16)


@pytest.mark.asyncio
async def test_evaluate_wraps_openai_errors_as_judge_error() -> None:
    rubric = _build_rubric()
    case = _build_case()
    underlying_error = openai.APIError(message="boom", request=MagicMock(), body=None)
    client = _make_mock_client(llm_output=_valid_llm_output(), side_effect=underlying_error)
    judge = OpenAIJudge(client=client)

    with pytest.raises(JudgeError) as exc_info:
        await judge.evaluate(case=case, rubric=rubric)

    assert not isinstance(exc_info.value, openai.APIError)
    assert exc_info.value.__cause__ is underlying_error
