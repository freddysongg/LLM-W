from __future__ import annotations

import asyncio
import statistics
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.eval import (
    Tier1Result,
    list_validators,
    register_validator,
    run_tier1,
)
from app.services.eval.tier1 import _REGISTRY

EXPECTED_VALIDATORS: set[str] = {
    "json_schema",
    "regex_match",
    "max_length",
    "contains_keywords",
    "moderation_openai",
}


def test_registry_lists_five_validators() -> None:
    assert set(list_validators()) == EXPECTED_VALIDATORS


def test_register_duplicate_raises() -> None:
    async def noop(_output: str, _config: object) -> tuple[bool, str]:
        return True, ""

    with pytest.raises(ValueError, match="already registered"):
        register_validator("json_schema")(noop)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_json_schema_passes_valid_payload() -> None:
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    result = await run_tier1(
        name="json_schema",
        output='{"name": "Ada", "age": 30}',
        config={"schema": schema},
    )
    assert result.passed is True
    assert result.reason == ""
    assert result.validator == "json_schema"


@pytest.mark.asyncio
async def test_json_schema_fails_invalid_payload() -> None:
    schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
    result = await run_tier1(
        name="json_schema",
        output='{"age": 30}',
        config={"schema": schema},
    )
    assert result.passed is False
    assert "schema violation" in result.reason


@pytest.mark.asyncio
async def test_json_schema_fails_malformed_json() -> None:
    result = await run_tier1(
        name="json_schema",
        output="{not valid json",
        config={"schema": {"type": "object"}},
    )
    assert result.passed is False
    assert "not valid JSON" in result.reason


@pytest.mark.asyncio
async def test_regex_match_search_passes() -> None:
    result = await run_tier1(
        name="regex_match",
        output="the quick brown fox",
        config={"pattern": r"brown\s+fox"},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_regex_match_search_fails() -> None:
    result = await run_tier1(
        name="regex_match",
        output="hello world",
        config={"pattern": r"goodbye"},
    )
    assert result.passed is False
    assert "no match for pattern" in result.reason


@pytest.mark.asyncio
async def test_regex_match_fullmatch_passes() -> None:
    result = await run_tier1(
        name="regex_match",
        output="foo",
        config={"pattern": r"^foo$", "fullmatch": True},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_regex_match_fullmatch_fails_when_only_partial() -> None:
    result = await run_tier1(
        name="regex_match",
        output="foo bar",
        config={"pattern": r"foo", "fullmatch": True},
    )
    assert result.passed is False


@pytest.mark.asyncio
async def test_max_length_passes_within_limit() -> None:
    result = await run_tier1(
        name="max_length",
        output="x" * 100,
        config={"limit": 500},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_max_length_fails_over_limit() -> None:
    result = await run_tier1(
        name="max_length",
        output="x" * 600,
        config={"limit": 500},
    )
    assert result.passed is False
    assert "600" in result.reason
    assert "500" in result.reason


@pytest.mark.asyncio
async def test_contains_keywords_all_passes() -> None:
    result = await run_tier1(
        name="contains_keywords",
        output="Foo and Bar are here",
        config={"keywords": ["foo", "bar"], "mode": "all"},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_keywords_all_fails_one_missing() -> None:
    result = await run_tier1(
        name="contains_keywords",
        output="foo is here",
        config={"keywords": ["foo", "bar"], "mode": "all"},
    )
    assert result.passed is False
    assert "bar" in result.reason


@pytest.mark.asyncio
async def test_contains_keywords_any_passes_on_single_match() -> None:
    result = await run_tier1(
        name="contains_keywords",
        output="only foo here",
        config={"keywords": ["foo", "bar"], "mode": "any"},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_contains_keywords_any_fails_on_no_matches() -> None:
    result = await run_tier1(
        name="contains_keywords",
        output="nothing here",
        config={"keywords": ["foo", "bar"], "mode": "any"},
    )
    assert result.passed is False
    assert "no keywords found" in result.reason


@pytest.mark.asyncio
async def test_contains_keywords_case_sensitive_respected() -> None:
    case_insensitive = await run_tier1(
        name="contains_keywords",
        output="FOO Bar",
        config={"keywords": ["foo"], "case_sensitive": False},
    )
    assert case_insensitive.passed is True

    case_sensitive = await run_tier1(
        name="contains_keywords",
        output="FOO Bar",
        config={"keywords": ["foo"], "case_sensitive": True},
    )
    assert case_sensitive.passed is False


def _mock_moderation_response(
    *, flagged: bool, categories: dict[str, bool] | None = None
) -> MagicMock:
    response = MagicMock()
    result = MagicMock()
    result.flagged = flagged
    category_obj = MagicMock(spec=[])
    for category_name, is_set in (categories or {}).items():
        setattr(category_obj, category_name, is_set)
    result.categories = category_obj
    response.results = [result]
    return response


@pytest.mark.asyncio
async def test_moderation_openai_passes_when_not_flagged() -> None:
    response = _mock_moderation_response(flagged=False)
    mock_client = MagicMock()
    mock_client.moderations.create = AsyncMock(return_value=response)

    with (
        patch(
            "app.services.eval.tier1.settings_service.get_raw_api_key",
            return_value="test-key",
        ),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        result = await run_tier1(name="moderation_openai", output="hello", config={})

    assert result.passed is True
    assert result.reason == ""


@pytest.mark.asyncio
async def test_moderation_openai_fails_when_flagged() -> None:
    response = _mock_moderation_response(flagged=True, categories={"violence": True, "hate": False})
    mock_client = MagicMock()
    mock_client.moderations.create = AsyncMock(return_value=response)

    with (
        patch(
            "app.services.eval.tier1.settings_service.get_raw_api_key",
            return_value="test-key",
        ),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        result = await run_tier1(name="moderation_openai", output="bad", config={})

    assert result.passed is False
    assert "violence" in result.reason
    assert "hate" not in result.reason


@pytest.mark.asyncio
async def test_moderation_openai_wraps_errors_as_verdict() -> None:
    mock_client = MagicMock()
    mock_client.moderations.create = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch(
            "app.services.eval.tier1.settings_service.get_raw_api_key",
            return_value="test-key",
        ),
        patch("openai.AsyncOpenAI", return_value=mock_client),
    ):
        result = await run_tier1(name="moderation_openai", output="x", config={})

    assert result.passed is False
    assert "boom" in result.reason


@pytest.mark.asyncio
async def test_run_tier1_returns_result_with_elapsed_ms() -> None:
    sentinel_name = "__timing_probe__"

    async def slow_validator(_output: str, _config: object) -> tuple[bool, str]:
        await asyncio.sleep(0.001)
        return True, ""

    _REGISTRY[sentinel_name] = slow_validator  # type: ignore[assignment]
    try:
        result = await run_tier1(name=sentinel_name, output="x", config={})
    finally:
        del _REGISTRY[sentinel_name]

    assert isinstance(result, Tier1Result)
    assert result.elapsed_ms > 0.0
    assert result.validator == sentinel_name


@pytest.mark.asyncio
async def test_p95_latency_under_50ms_on_200_case_batch() -> None:
    """AC: deterministic validators p95 under 50ms across a 200-case batch.

    If this flakes under shared CI, bump the ceiling to 100ms — but the intent
    remains the ticket's literal 50ms target.
    """
    batch_size = 200
    latencies: list[float] = []

    schema = {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "label": {"type": "string"}},
        "required": ["id", "label"],
    }

    for index in range(batch_size):
        json_payload = f'{{"id": {index}, "label": "item-{index}"}}'
        json_result = await run_tier1(
            name="json_schema",
            output=json_payload,
            config={"schema": schema},
        )
        latencies.append(json_result.elapsed_ms)

        regex_result = await run_tier1(
            name="regex_match",
            output=f"row-{index} brown fox jumps",
            config={"pattern": r"brown\s+fox"},
        )
        latencies.append(regex_result.elapsed_ms)

        length_result = await run_tier1(
            name="max_length",
            output="x" * (100 + index),
            config={"limit": 1000},
        )
        latencies.append(length_result.elapsed_ms)

        keywords_result = await run_tier1(
            name="contains_keywords",
            output=f"the quick brown fox {index}",
            config={"keywords": ["brown", "fox"], "mode": "all"},
        )
        latencies.append(keywords_result.elapsed_ms)

    latencies.sort()
    p95_index = int(0.95 * len(latencies))
    p95_ms = latencies[p95_index]
    mean_ms = statistics.fmean(latencies)

    assert p95_ms < 50.0, f"p95 latency {p95_ms:.2f}ms exceeds 50ms (mean {mean_ms:.2f}ms)"
