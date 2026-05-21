from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.project import Project
from app.models.suggestion import AISuggestion
from app.services import llm_chat, settings_service, suggestion_chat_service

_NOW = "2026-05-20T12:00:00+00:00"


@pytest.fixture(autouse=True)
def reset_settings_overrides() -> None:
    settings_service._overrides.clear()
    yield
    settings_service._overrides.clear()


@pytest.fixture
async def db_engine_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    db_path = tmp_path / "workbench.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
async def client(
    db_engine_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with db_engine_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _seed_project_and_suggestion(
    *,
    factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "p1"
    project_dir.mkdir(parents=True, exist_ok=True)
    async with factory() as session:
        session.add(
            Project(
                id="p1",
                name="p1",
                directory_path=str(project_dir),
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        session.add(
            AISuggestion(
                id="s1",
                project_id="p1",
                provider="rule_engine",
                config_diff='{"training.learning_rate": {"current": 2e-4, "suggested": 1e-4}}',
                rationale="Loss plateaued; reduce LR.",
                evidence_json='[{"type": "metric", "reference_id": "eval_loss"}]',
                expected_effect="Allow finer convergence.",
                tradeoffs="Longer training time.",
                confidence=0.7,
                risk_level="low",
                status="pending",
                created_at=_NOW,
            )
        )
        await session.commit()


async def test_list_chat_messages_returns_empty_when_no_history(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed_project_and_suggestion(factory=db_engine_factory, tmp_path=tmp_path)
    response = await client.get("/api/v1/projects/p1/suggestions/s1/chat")
    body = response.json()
    assert response.status_code == 200, body
    assert body["messages"] == []


async def test_list_chat_messages_404_when_suggestion_missing(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed_project_and_suggestion(factory=db_engine_factory, tmp_path=tmp_path)
    response = await client.get("/api/v1/projects/p1/suggestions/does-not-exist/chat")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SUGGESTION_NOT_FOUND"


async def test_send_chat_message_persists_pair_and_returns_assistant_reply(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_project_and_suggestion(factory=db_engine_factory, tmp_path=tmp_path)

    captured_calls: list[dict[str, object]] = []

    async def fake_chat_completion(
        *,
        provider: str,
        api_key: str | None,
        model_id: str,
        base_url: str | None,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        captured_calls.append(
            {
                "provider": provider,
                "system": system,
                "messages": messages,
            }
        )
        return "Lowering the learning rate gives the optimiser smaller updates."

    monkeypatch.setattr(
        suggestion_chat_service.llm_chat, "chat_completion", fake_chat_completion
    )
    settings_service._overrides["ai_api_key"] = "test-key"

    response = await client.post(
        "/api/v1/projects/p1/suggestions/s1/chat",
        json={"message": "Why this learning rate?"},
    )
    body = response.json()
    assert response.status_code == 201, body
    assert body["role"] == "assistant"
    assert "smaller updates" in body["content"]

    list_response = await client.get("/api/v1/projects/p1/suggestions/s1/chat")
    messages = list_response.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Why this learning rate?"

    assert len(captured_calls) == 1
    call = captured_calls[0]
    assert "Loss plateaued" in str(call["system"])
    assert call["messages"] == [{"role": "user", "content": "Why this learning rate?"}]


async def test_send_chat_message_502_when_llm_fails(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_project_and_suggestion(factory=db_engine_factory, tmp_path=tmp_path)

    async def fake_chat_completion(**_: object) -> str:
        raise llm_chat.LLMChatError("provider down")

    monkeypatch.setattr(
        suggestion_chat_service.llm_chat, "chat_completion", fake_chat_completion
    )
    settings_service._overrides["ai_api_key"] = "test-key"

    response = await client.post(
        "/api/v1/projects/p1/suggestions/s1/chat",
        json={"message": "Why?"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "LLM_CHAT_ERROR"
