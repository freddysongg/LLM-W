from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel, Field, field_validator

from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Criterion, FewShotExample, Rubric
from app.services import settings_service
from app.services.eval.judge import JudgeError, JudgeProvider

if TYPE_CHECKING:
    import instructor
    from openai.types.chat import ChatCompletionMessageParam


class _JudgeLLMOutput(BaseModel):
    """Schema for the fields the LLM itself produces.

    Field order is load-bearing: `reasoning` precedes `verdict` so instructor /
    OpenAI Structured Outputs emit chain-of-thought before the verdict token
    (G-Eval / Critique Shadowing, R7). The remaining Score fields
    (`cost_usd`, `latency_ms`, `judge_model`, `rubric_version`, `response_hash`)
    are computed by the judge after the API call.
    """

    reasoning: str = Field(..., min_length=1)
    verdict: Literal["pass", "fail"]
    per_criterion: dict[str, bool]

    model_config = {"extra": "forbid"}

    @field_validator("reasoning")
    @classmethod
    def _reasoning_not_blank(cls, reasoning: str) -> str:
        if not reasoning.strip():
            raise ValueError("reasoning must not be empty or whitespace-only")
        return reasoning


_SUPPORTED_MODEL_PREFIXES: tuple[str, ...] = ("gpt-4o-mini", "gpt-4o")

# Pricing snapshot (USD per 1K tokens). Values are a point-in-time capture and
# may drift — revisit alongside OpenAI's public pricing page and file a follow-up
# issue when they change. Prefix-matched to tolerate dated SKUs like
# `gpt-4o-mini-2024-07-18`.
_MODEL_RATES_USD_PER_1K: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
}


def _resolve_rate_key(*, model: str) -> str:
    for prefix in _SUPPORTED_MODEL_PREFIXES:
        if model == prefix or model.startswith(f"{prefix}-"):
            return prefix
    raise JudgeError(f"unsupported judge model: {model}")


def _format_criteria(*, criteria: list[Criterion]) -> str:
    lines: list[str] = []
    for criterion in criteria:
        lines.append(f"- {criterion.name} ({criterion.points} pts): {criterion.description}")
    return "\n".join(lines)


def _format_case_user_message(*, case: EvaluationCase) -> str:
    sections: list[str] = ["## Prompt", case.prompt, "", "## Model Output", case.output]
    if case.reference is not None:
        sections += ["", "## Reference", case.reference]
    if case.retrieved_context is not None:
        sections += ["", "## Retrieved Context", case.retrieved_context]
    if case.conversation_history:
        history_json = json.dumps(case.conversation_history, indent=2)
        sections += ["", "## Conversation History", history_json]
    return "\n".join(sections)


def _format_eval_steps(*, eval_steps: list[str]) -> str:
    lines: list[str] = []
    for index, step in enumerate(eval_steps, start=1):
        lines.append(f"{index}. {step}")
    return "\n".join(lines)


def _build_system_message(*, rubric: Rubric, eval_steps: list[str] | None = None) -> str:
    criteria_block = _format_criteria(criteria=rubric.criteria)
    eval_steps_block = ""
    if eval_steps:
        eval_steps_block = f"Evaluation Steps:\n{_format_eval_steps(eval_steps=eval_steps)}\n\n"
    return (
        "You are an expert LLM-as-Judge evaluator applying a binary rubric. "
        "For each criterion, decide whether the model output satisfies it.\n\n"
        "Rubric description:\n"
        f"{rubric.description}\n\n"
        "Criteria (each is a binary pass/fail check):\n"
        f"{criteria_block}\n\n"
        f"{eval_steps_block}"
        "Procedure:\n"
        "1. First, write out your step-by-step reasoning analysing the output "
        "against each criterion. Reasoning MUST come before the verdict.\n"
        "2. Then, for every criterion, record whether it passes (true) or "
        "fails (false) in per_criterion, keyed by criterion name.\n"
        "3. Finally, emit an overall verdict: 'pass' only if every criterion "
        "passes, otherwise 'fail'."
    )


def _build_few_shot_turns(*, examples: list[FewShotExample]) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    for example in examples:
        turns.append(
            {
                "role": "user",
                "content": _format_case_user_message(case=example.input),
            }
        )
        assistant_payload = {
            "reasoning": example.reasoning,
            "verdict": example.verdict,
        }
        turns.append(
            {
                "role": "assistant",
                "content": json.dumps(assistant_payload),
            }
        )
    return turns


def _build_messages(
    *,
    rubric: Rubric,
    case: EvaluationCase,
    eval_steps: list[str] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": _build_system_message(rubric=rubric, eval_steps=eval_steps),
        }
    ]
    messages.extend(_build_few_shot_turns(examples=rubric.few_shot_examples))
    messages.append({"role": "user", "content": _format_case_user_message(case=case)})
    return messages


def _compute_cost_usd(*, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate_key = _resolve_rate_key(model=model)
    rates = _MODEL_RATES_USD_PER_1K[rate_key]
    prompt_cost = (prompt_tokens / 1000.0) * rates["prompt"]
    completion_cost = (completion_tokens / 1000.0) * rates["completion"]
    return prompt_cost + completion_cost


def _compute_response_hash(*, payload: dict[str, object]) -> str:
    serialised = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


def _extract_usage_tokens(*, completion: object) -> tuple[int, int]:
    usage = getattr(completion, "usage", None)
    if usage is None:
        raise JudgeError("OpenAI completion missing usage metadata")
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if prompt_tokens is None or completion_tokens is None:
        raise JudgeError("OpenAI completion usage missing token counts")
    return int(prompt_tokens), int(completion_tokens)


class OpenAIJudge(JudgeProvider):
    """OpenAI-backed JudgeProvider using instructor for Pydantic-validated Score returns.

    Supports `gpt-4o` and `gpt-4o-mini` (plus dated SKUs with those prefixes).
    The `-latest` alias is rejected by the Rubric validator; this class additionally
    guards against unknown SKUs at the provider level.
    """

    def __init__(
        self,
        *,
        client: instructor.AsyncInstructor | None = None,
        api_key_loader: Callable[[], str | None] = settings_service.get_raw_api_key,
    ) -> None:
        self._client = client
        self._api_key_loader = api_key_loader

    def _get_or_build_client(self) -> instructor.AsyncInstructor:
        if self._client is not None:
            return self._client
        api_key = self._api_key_loader()
        if not api_key:
            raise JudgeError("OpenAI API key not configured in settings_service")
        import instructor
        import openai

        self._client = instructor.from_openai(openai.AsyncOpenAI(api_key=api_key))
        return self._client

    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        messages = _build_messages(rubric=rubric, case=case)
        return await self.score_from_messages(messages=messages, rubric=rubric)

    async def score_from_messages(
        self,
        *,
        messages: list[dict[str, str]],
        rubric: Rubric,
        temperature: float = 0.0,
        judge_model: str | None = None,
    ) -> Score:
        model = judge_model if judge_model is not None else rubric.judge_model_pin
        _resolve_rate_key(model=model)

        client = self._get_or_build_client()

        started_at = time.monotonic()
        try:
            llm_output, completion = await client.chat.completions.create_with_completion(
                model=model,
                response_model=_JudgeLLMOutput,
                messages=cast("list[ChatCompletionMessageParam]", messages),
                temperature=temperature,
            )
        except JudgeError:
            raise
        except Exception as exc:
            raise JudgeError(str(exc)) from exc
        elapsed_ms = int((time.monotonic() - started_at) * 1000)

        prompt_tokens, completion_tokens = _extract_usage_tokens(completion=completion)
        cost_usd = _compute_cost_usd(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        response_hash = _compute_response_hash(payload=llm_output.model_dump())

        return Score(
            reasoning=llm_output.reasoning,
            verdict=llm_output.verdict,
            per_criterion=llm_output.per_criterion,
            cost_usd=cost_usd,
            latency_ms=elapsed_ms,
            judge_model=model,
            rubric_version=rubric.version,
            response_hash=response_hash,
        )
