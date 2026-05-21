from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.config_version import ConfigVersion
from app.models.project import Project
from app.models.suggestion import AISuggestion
from app.services import ai_recommender, suggestion_service
from app.services.ai_recommender import _parse_llm_response
from app.services.rule_engine import AISuggestionCreate


def _llm_payload(*, extra: dict[str, Any] | None = None) -> str:
    base: dict[str, Any] = {
        "config_diff": {
            "training.learning_rate": {"current": 2e-4, "suggested": 1e-4},
            "optimization.warmup_ratio": {"current": 0.03, "suggested": 0.05},
        },
        "rationale": "loss plateau then warmup tweak",
        "evidence": [],
        "expected_effect": "smoother convergence",
        "tradeoffs": "slower start",
        "confidence": 0.8,
        "risk_level": "low",
    }
    if extra:
        base.update(extra)
    return json.dumps(base)


def test_parse_llm_response_preserves_valid_confidence_per_action() -> None:
    raw = _llm_payload(extra={"confidence_per_action": [0.9, 0.6]})

    parsed = _parse_llm_response(raw=raw, provider="openai")

    assert parsed.confidence_per_action == [0.9, 0.6]


def test_parse_llm_response_clamps_out_of_range_entries() -> None:
    raw = _llm_payload(extra={"confidence_per_action": [1.4, -0.2]})

    parsed = _parse_llm_response(raw=raw, provider="openai")

    assert parsed.confidence_per_action == [1.0, 0.0]


def test_parse_llm_response_drops_length_mismatch() -> None:
    raw = _llm_payload(extra={"confidence_per_action": [0.5]})

    parsed = _parse_llm_response(raw=raw, provider="openai")

    assert parsed.confidence_per_action is None


def test_parse_llm_response_drops_non_numeric_entries() -> None:
    raw = _llm_payload(extra={"confidence_per_action": [0.5, "nope"]})

    parsed = _parse_llm_response(raw=raw, provider="openai")

    assert parsed.confidence_per_action is None


def test_parse_llm_response_returns_none_when_field_absent() -> None:
    raw = _llm_payload()

    parsed = _parse_llm_response(raw=raw, provider="openai")

    assert parsed.confidence_per_action is None


def test_build_prompt_advertises_confidence_per_action() -> None:
    prompt = ai_recommender._build_prompt(
        config_yaml="training:\n  learning_rate: 0.0002\n",
        run_metrics=[],
        dataset_profile={},
        comparison_data=None,
        notes=None,
    )

    assert "confidence_per_action" in prompt
    assert "one entry per config_diff key" in prompt


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_project_with_config(
    *, factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC).isoformat()
    async with factory() as session:
        session.add(
            Project(
                id="p1",
                name="recommender-project",
                directory_path="/tmp/p1",
                active_config_version_id="cv1",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            ConfigVersion(
                id="cv1",
                project_id="p1",
                version_number=1,
                yaml_blob="training:\n  learning_rate: 0.0002\n",
                yaml_hash="hash",
                source_tag="user",
                created_at=now,
            )
        )
        await session.commit()


async def test_generate_suggestions_persists_confidence_per_action(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_project_with_config(factory=session_factory)

    create = AISuggestionCreate(
        provider="openai",
        config_diff={
            "training.learning_rate": {"current": 2e-4, "suggested": 1e-4},
            "optimization.warmup_ratio": {"current": 0.03, "suggested": 0.05},
        },
        rationale="loss plateau",
        evidence=[],
        expected_effect="smoother",
        tradeoffs=None,
        confidence=0.8,
        risk_level="low",
        confidence_per_action=[0.85, 0.55],
    )

    class _StubEngine:
        async def generate_recommendations(self, **_: object) -> list[AISuggestionCreate]:
            return [create]

    monkeypatch.setattr(ai_recommender, "build_engine", lambda **_: _StubEngine())
    monkeypatch.setattr(suggestion_service, "build_engine", lambda **_: _StubEngine())
    monkeypatch.setattr(suggestion_service, "get_raw_api_key", lambda: "key")

    async with session_factory() as session:
        await suggestion_service.generate_suggestions(session=session, project_id="p1")

    async with session_factory() as session:
        rows = list((await session.execute(select(AISuggestion))).scalars().all())

    assert len(rows) == 1
    assert rows[0].confidence_per_action_json == json.dumps([0.85, 0.55])


async def test_generate_suggestions_persists_null_when_absent(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_project_with_config(factory=session_factory)

    create = AISuggestionCreate(
        provider="rule_engine",
        config_diff={"training.learning_rate": {"current": 2e-4, "suggested": 1e-4}},
        rationale="loss plateau",
        evidence=[],
        expected_effect=None,
        tradeoffs=None,
        confidence=0.7,
        risk_level="low",
    )

    class _StubEngine:
        async def generate_recommendations(self, **_: object) -> list[AISuggestionCreate]:
            return [create]

    monkeypatch.setattr(ai_recommender, "build_engine", lambda **_: _StubEngine())
    monkeypatch.setattr(suggestion_service, "build_engine", lambda **_: _StubEngine())
    monkeypatch.setattr(suggestion_service, "get_raw_api_key", lambda: "key")

    async with session_factory() as session:
        await suggestion_service.generate_suggestions(session=session, project_id="p1")

    async with session_factory() as session:
        rows = list((await session.execute(select(AISuggestion))).scalars().all())

    assert len(rows) == 1
    assert rows[0].confidence_per_action_json is None
