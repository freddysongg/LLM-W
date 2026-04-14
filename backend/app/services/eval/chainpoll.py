from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from typing import Literal

from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import ChainPollConfig, Rubric
from app.services.eval.judge import JudgeError, JudgeProvider
from app.services.eval.openai_judge import OpenAIJudge, _build_messages

_Verdict = Literal["pass", "fail"]
_METHOD_LABEL = "chainpoll"


def _majority_verdict(*, verdicts: list[_Verdict]) -> tuple[_Verdict, int]:
    """Return the majority verdict and its count.

    Ties are broken by the first call's verdict, preserving deterministic
    replay across runs (documented in the class docstring).
    """

    counts = Counter(verdicts)
    top_count = max(counts.values())
    winners = [verdict for verdict, count in counts.items() if count == top_count]
    if len(winners) == 1:
        return winners[0], top_count
    for verdict in verdicts:
        if verdict in winners:
            return verdict, top_count
    raise JudgeError("unreachable: no verdict matched tie-break candidates")


def _build_calls_payload(*, scores: list[Score]) -> list[dict[str, object]]:
    return [
        {
            "verdict": score.verdict,
            "reasoning": score.reasoning,
            "response_hash": score.response_hash,
            "cost_usd": score.cost_usd,
            "latency_ms": score.latency_ms,
        }
        for score in scores
    ]


def _serialise_reasoning(*, payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _hash_reasoning(*, serialised: str) -> str:
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _first_majority_score(*, scores: list[Score], majority: _Verdict) -> Score:
    for score in scores:
        if score.verdict == majority:
            return score
    raise JudgeError("unreachable: majority verdict missing from scores")


class ChainPollJudge(JudgeProvider):
    """ChainPoll wrapper (R4): fires N judge calls and majority-votes the verdict.

    When ``rubric.chainpoll`` is ``None`` the call is delegated verbatim to the
    base judge (no wrapping cost). Otherwise N parallel calls are dispatched
    via ``asyncio.gather`` at ``rubric.chainpoll.temperature``, and the
    aggregated ``Score`` carries a structured JSON ``reasoning`` field so every
    dissenting reasoning is recoverable for replay.

    Ties are broken by the first call's verdict. With an odd N and binary
    verdicts, a tie is impossible; the tie-break path exists only for
    even-N configurations (N=2 in practice).

    Composes an injected ``OpenAIJudge`` and invokes its
    ``score_from_messages`` helper for each call. This mirrors ``GEvalJudge``
    (Option A from the G-Eval ticket) and keeps the ``JudgeProvider`` ABC
    free of ChainPoll-specific kwargs.
    """

    def __init__(
        self,
        *,
        base_judge: OpenAIJudge | None = None,
    ) -> None:
        self._base = base_judge if base_judge is not None else OpenAIJudge()

    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        if rubric.chainpoll is None:
            return await self._base.evaluate(case=case, rubric=rubric)

        config = rubric.chainpoll
        scores = await self._gather_scores(case=case, rubric=rubric, config=config)

        verdicts: list[_Verdict] = [score.verdict for score in scores]
        majority, majority_count = _majority_verdict(verdicts=verdicts)

        payload: dict[str, object] = {
            "method": _METHOD_LABEL,
            "n": config.n,
            "temperature": config.temperature,
            "model": config.model,
            "majority_verdict": majority,
            "majority_count": majority_count,
            "calls": _build_calls_payload(scores=scores),
        }
        serialised_reasoning = _serialise_reasoning(payload=payload)
        aggregate_hash = _hash_reasoning(serialised=serialised_reasoning)

        representative = _first_majority_score(scores=scores, majority=majority)

        return Score(
            reasoning=serialised_reasoning,
            verdict=majority,
            per_criterion=representative.per_criterion,
            cost_usd=sum(score.cost_usd for score in scores),
            latency_ms=max(score.latency_ms for score in scores),
            judge_model=config.model,
            rubric_version=rubric.version,
            response_hash=aggregate_hash,
        )

    async def _gather_scores(
        self,
        *,
        case: EvaluationCase,
        rubric: Rubric,
        config: ChainPollConfig,
    ) -> list[Score]:
        messages = _build_messages(rubric=rubric, case=case)
        tasks = [
            self._base.score_from_messages(
                messages=messages,
                rubric=rubric,
                temperature=config.temperature,
                judge_model=config.model,
            )
            for _ in range(config.n)
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        scores: list[Score] = []
        for index, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                raise JudgeError(
                    f"ChainPoll call {index + 1}/{config.n} failed: {outcome}"
                ) from outcome
            scores.append(outcome)
        return scores
