from __future__ import annotations

import inspect

import pytest

from app.schemas.eval import EvaluationCase, Score
from app.schemas.rubric import Rubric
from app.services.eval import JudgeError, JudgeProvider


class _StubJudge(JudgeProvider):
    async def evaluate(self, *, case: EvaluationCase, rubric: Rubric) -> Score:
        raise JudgeError("stub not implemented")


def test_judge_provider_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        JudgeProvider()  # type: ignore[abstract]


def test_concrete_subclass_instantiates() -> None:
    judge = _StubJudge()
    assert isinstance(judge, JudgeProvider)


def test_evaluate_signature_matches_contract() -> None:
    signature = inspect.signature(JudgeProvider.evaluate, eval_str=True)
    parameters = signature.parameters

    assert list(parameters) == ["self", "case", "rubric"]
    assert parameters["case"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["rubric"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["case"].annotation is EvaluationCase
    assert parameters["rubric"].annotation is Rubric
    assert signature.return_annotation is Score


def test_evaluate_is_coroutine_function() -> None:
    assert inspect.iscoroutinefunction(JudgeProvider.evaluate)
    assert inspect.iscoroutinefunction(_StubJudge.evaluate)


def test_judge_error_is_exception_subclass() -> None:
    assert issubclass(JudgeError, Exception)
