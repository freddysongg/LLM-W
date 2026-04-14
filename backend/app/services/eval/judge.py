from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric


class JudgeProvider(ABC):
    """Abstract interface for LLM-as-Judge providers.

    Concrete implementations (e.g., OpenAIJudge) return a schema-validated
    Score for a (case, rubric) pair. Mirrors the RecommendationEngine pattern
    in ai_recommender.py.
    """

    @abstractmethod
    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        """Score a single case against a rubric.

        Raises:
            JudgeError: on any judge-layer failure (network, schema, cost cap).
        """


class JudgeError(Exception):
    """Raised by JudgeProvider implementations on failure."""
