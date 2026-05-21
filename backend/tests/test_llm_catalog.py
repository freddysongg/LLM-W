from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.llm_catalog import LLM_MODEL_CATALOG
from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_list_llm_models_returns_full_catalog(client: AsyncClient) -> None:
    response = await client.get("/api/v1/catalog/llm-models")
    assert response.status_code == 200
    body = response.json()
    assert len(body["options"]) == len(LLM_MODEL_CATALOG)


async def test_list_llm_models_includes_known_openai_and_anthropic_models(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/catalog/llm-models")
    body = response.json()
    model_ids = {option["model_id"] for option in body["options"]}
    assert "gpt-4o" in model_ids
    assert "claude-sonnet-4-6" in model_ids


async def test_list_llm_models_options_have_provider_model_id_and_label(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/catalog/llm-models")
    body = response.json()
    for option in body["options"]:
        assert option.keys() == {"provider", "model_id", "label"}
        assert option["provider"] in {"openai", "anthropic"}
        assert isinstance(option["model_id"], str) and option["model_id"]
        assert isinstance(option["label"], str) and option["label"]
