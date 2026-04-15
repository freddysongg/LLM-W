from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field, ValidationError

from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Criterion, Rubric
from app.services import settings_service
from app.services.eval.judge import JudgeError, JudgeProvider
from app.services.eval.openai_judge import OpenAIJudge, _build_messages

if TYPE_CHECKING:
    import instructor
    from openai.types.chat import ChatCompletionMessageParam


StepsGenerator = Callable[[Rubric], Awaitable[list[str]]]


_STEPS_MIN = 3
_STEPS_MAX = 7

_STEPS_SYSTEM_PROMPT = (
    "You are designing an evaluation rubric. Given these binary criteria, "
    "produce an ordered list of 3-7 evaluation steps that a careful human "
    "rater would follow. Each step should be concrete and testable. "
    "Output as a JSON list of strings."
)


class _EvalSteps(BaseModel):
    """Response schema for the steps-generation LLM call.

    Bounds match the G-Eval paper (R1): between 3 and 7 ordered steps, each
    non-empty after stripping whitespace.
    """

    steps: list[str] = Field(..., min_length=_STEPS_MIN, max_length=_STEPS_MAX)

    model_config = {"extra": "forbid"}

    @classmethod
    def _strip_and_check(cls, steps: list[str]) -> list[str]:
        cleaned: list[str] = []
        for step in steps:
            stripped = step.strip()
            if not stripped:
                raise ValueError("evaluation steps must not be empty or whitespace-only")
            cleaned.append(stripped)
        return cleaned

    def model_post_init(self, _context: object) -> None:
        object.__setattr__(self, "steps", self._strip_and_check(self.steps))


def _format_criteria_for_steps_prompt(*, criteria: list[Criterion]) -> str:
    lines: list[str] = []
    for index, criterion in enumerate(criteria, start=1):
        lines.append(f"{index}. {criterion.name}: {criterion.description}")
    return "\n".join(lines)


def _build_steps_user_message(*, rubric: Rubric) -> str:
    criteria_block = _format_criteria_for_steps_prompt(criteria=rubric.criteria)
    return (
        "Rubric description:\n"
        f"{rubric.description}\n\n"
        "Criteria:\n"
        f"{criteria_block}"
    )


async def _generate_steps_openai(
    rubric: Rubric,
    *,
    api_key_loader: Callable[[], str | None],
    client: instructor.AsyncInstructor | None,
) -> list[str]:
    """Default OpenAI-backed StepsGenerator.

    Uses the same model as the rubric's ``judge_model_pin`` so steps-generation
    and scoring share temperature/model semantics.
    """

    resolved_client = client
    if resolved_client is None:
        api_key = api_key_loader()
        if not api_key:
            raise JudgeError("OpenAI API key not configured in settings_service")
        import instructor as instructor_module
        import openai

        resolved_client = instructor_module.from_openai(openai.AsyncOpenAI(api_key=api_key))

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _STEPS_SYSTEM_PROMPT},
        {"role": "user", "content": _build_steps_user_message(rubric=rubric)},
    ]

    try:
        response = await resolved_client.chat.completions.create(
            model=rubric.judge_model_pin,
            response_model=_EvalSteps,
            messages=cast("list[ChatCompletionMessageParam]", messages),
            temperature=0.0,
        )
    except JudgeError:
        raise
    except ValidationError as exc:
        raise JudgeError(f"invalid G-Eval steps response: {exc}") from exc
    except Exception as exc:
        raise JudgeError(str(exc)) from exc

    return response.steps


class GEvalJudge(JudgeProvider):
    """G-Eval two-stage judge (R1) composing an ``OpenAIJudge`` for scoring.

    Stage 1: auto-generate 3-7 evaluation steps from the rubric criteria.
    Stage 2: inject those steps into the judge prompt and delegate scoring.

    Steps are cached in-memory keyed on ``sha256(rubric.model_dump_json())`` so
    content-level rubric edits invalidate the cache. No TTL: rubric content is
    immutable per-hash, so entries remain valid indefinitely for the lifetime
    of the judge instance.

    Design choice: composes an injected ``OpenAIJudge`` and calls its
    ``score_from_messages`` helper with a prompt enriched via the shared
    ``_build_messages`` helper (Option A from the ticket). This keeps
    ``OpenAIJudge.evaluate`` free of G-Eval coupling while allowing G-Eval
    to own its prompt enrichment.
    """

    def __init__(
        self,
        *,
        base_judge: OpenAIJudge | None = None,
        steps_generator: StepsGenerator | None = None,
        api_key_loader: Callable[[], str | None] = settings_service.get_raw_api_key,
        steps_client: instructor.AsyncInstructor | None = None,
    ) -> None:
        self._base_judge = base_judge if base_judge is not None else OpenAIJudge()
        self._steps_generator = steps_generator
        self._api_key_loader = api_key_loader
        self._steps_client = steps_client
        self._steps_cache: dict[str, list[str]] = {}

    @staticmethod
    def _cache_key(rubric: Rubric) -> str:
        serialised = rubric.model_dump_json().encode("utf-8")
        return hashlib.sha256(serialised).hexdigest()

    async def _get_or_generate_steps(self, *, rubric: Rubric) -> list[str]:
        key = self._cache_key(rubric)
        cached = self._steps_cache.get(key)
        if cached is not None:
            return cached

        generator = self._steps_generator
        if generator is None:
            generator = self._default_generator
        steps = await generator(rubric)

        if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
            raise JudgeError("steps_generator must return a list[str]")
        if len(steps) < _STEPS_MIN or len(steps) > _STEPS_MAX:
            raise JudgeError(
                f"steps_generator must return between {_STEPS_MIN} and {_STEPS_MAX} steps, "
                f"got {len(steps)}"
            )

        self._steps_cache[key] = steps
        return steps

    async def _default_generator(self, rubric: Rubric) -> list[str]:
        return await _generate_steps_openai(
            rubric,
            api_key_loader=self._api_key_loader,
            client=self._steps_client,
        )

    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        steps = await self._get_or_generate_steps(rubric=rubric)
        messages = _build_messages(rubric=rubric, case=case, eval_steps=steps)
        return await self._base_judge.score_from_messages(messages=messages, rubric=rubric)
