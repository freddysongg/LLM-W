from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Literal, cast

import jsonschema
import jsonschema.exceptions

from app.services import settings_service

Tier1Validator = Callable[[str, Mapping[str, object]], Awaitable[tuple[bool, str]]]

_MODERATION_MODEL: str = "omni-moderation-latest"
_DEFAULT_KEYWORD_MODE: Literal["all", "any"] = "all"


@dataclass(frozen=True)
class Tier1Result:
    """Outcome of a Tier-1 deterministic validator invocation.

    `elapsed_ms` is measured by the registry so validators cannot under-report.
    `reason` is empty on pass, human-readable on fail.
    """

    passed: bool
    reason: str
    validator: str
    elapsed_ms: float


class Tier1ValidatorError(Exception):
    """Raised only when a validator cannot be invoked at all.

    Most Tier-1 failures are verdicts (passed=False with a reason), not
    exceptions. This error is reserved for misconfiguration like an unknown
    validator name.
    """


_REGISTRY: dict[str, Tier1Validator] = {}


def register_validator(name: str) -> Callable[[Tier1Validator], Tier1Validator]:
    def decorator(fn: Tier1Validator) -> Tier1Validator:
        if name in _REGISTRY:
            raise ValueError(f"validator already registered: {name}")
        _REGISTRY[name] = fn
        return fn

    return decorator


def list_validators() -> list[str]:
    return sorted(_REGISTRY.keys())


async def run_tier1(
    *,
    name: str,
    output: str,
    config: Mapping[str, object],
) -> Tier1Result:
    if name not in _REGISTRY:
        raise Tier1ValidatorError(f"unknown validator: {name}")
    validator = _REGISTRY[name]
    started_at = time.monotonic()
    passed, reason = await validator(output, config)
    elapsed_ms = (time.monotonic() - started_at) * 1000.0
    return Tier1Result(
        passed=passed,
        reason=reason,
        validator=name,
        elapsed_ms=elapsed_ms,
    )


@register_validator("json_schema")
async def _json_schema(output: str, config: Mapping[str, object]) -> tuple[bool, str]:
    schema_obj = config.get("schema")
    if not isinstance(schema_obj, Mapping):
        return False, "json_schema config missing 'schema' mapping"
    try:
        instance = json.loads(output)
    except json.JSONDecodeError as exc:
        return False, f"output is not valid JSON: {exc.msg}"
    try:
        jsonschema.validate(instance=instance, schema=dict(schema_obj))
    except jsonschema.exceptions.ValidationError as exc:
        return False, f"schema violation: {exc.message}"
    return True, ""


@register_validator("regex_match")
async def _regex_match(output: str, config: Mapping[str, object]) -> tuple[bool, str]:
    pattern_obj = config.get("pattern")
    if not isinstance(pattern_obj, str):
        return False, "regex_match config missing string 'pattern'"
    fullmatch_flag = bool(config.get("fullmatch", False))
    try:
        compiled = re.compile(pattern_obj)
    except re.error as exc:
        return False, f"invalid regex pattern: {exc}"
    matched = (
        compiled.fullmatch(output) is not None
        if fullmatch_flag
        else compiled.search(output) is not None
    )
    if matched:
        return True, ""
    return False, f"no match for pattern: {pattern_obj}"


@register_validator("max_length")
async def _max_length(output: str, config: Mapping[str, object]) -> tuple[bool, str]:
    limit_obj = config.get("limit")
    if not isinstance(limit_obj, int) or isinstance(limit_obj, bool):
        return False, "max_length config missing integer 'limit'"
    length = len(output)
    if length <= limit_obj:
        return True, ""
    return False, f"output length {length} exceeds limit {limit_obj}"


@register_validator("contains_keywords")
async def _contains_keywords(output: str, config: Mapping[str, object]) -> tuple[bool, str]:
    keywords_obj = config.get("keywords")
    if not isinstance(keywords_obj, list) or not all(isinstance(k, str) for k in keywords_obj):
        return False, "contains_keywords config missing list[str] 'keywords'"
    keywords = cast(list[str], keywords_obj)
    case_sensitive = bool(config.get("case_sensitive", False))
    mode_obj = config.get("mode", _DEFAULT_KEYWORD_MODE)
    if mode_obj != "all" and mode_obj != "any":
        return False, f"contains_keywords 'mode' must be 'all' or 'any', got: {mode_obj!r}"
    mode: Literal["all", "any"] = mode_obj

    haystack = output if case_sensitive else output.lower()
    prepared = [kw if case_sensitive else kw.lower() for kw in keywords]

    if mode == "all":
        missing = [
            original_kw
            for original_kw, normalised in zip(keywords, prepared, strict=True)
            if normalised not in haystack
        ]
        if missing:
            return False, f"missing keywords: {missing}"
        return True, ""

    if any(kw in haystack for kw in prepared):
        return True, ""
    return False, f"no keywords found, expected any of: {keywords}"


@register_validator("moderation_openai")
async def _moderation_openai(output: str, config: Mapping[str, object]) -> tuple[bool, str]:
    del config
    api_key = settings_service.get_raw_api_key()
    if not api_key:
        return False, "moderation_openai: OpenAI API key not configured"
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.moderations.create(model=_MODERATION_MODEL, input=output)
    except Exception as exc:
        return False, f"moderation_openai error: {exc}"

    results = getattr(response, "results", None)
    if not results:
        return False, "moderation_openai: response missing results"
    first = results[0]
    if not getattr(first, "flagged", False):
        return True, ""
    categories = getattr(first, "categories", None)
    flagged_categories = _extract_flagged_categories(categories=categories)
    return False, f"flagged by moderation: {', '.join(flagged_categories)}"


def _extract_flagged_categories(*, categories: object) -> list[str]:
    if categories is None:
        return []
    if isinstance(categories, Mapping):
        return sorted(str(k) for k, v in categories.items() if v)
    flagged: list[str] = []
    for attr in dir(categories):
        if attr.startswith("_"):
            continue
        try:
            value = getattr(categories, attr)
        except AttributeError:
            continue
        if isinstance(value, bool) and value:
            flagged.append(attr)
    return sorted(flagged)
