from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.model_registry import MODEL_REGISTRY
from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_list_model_registry_returns_full_catalog(client: AsyncClient) -> None:
    response = await client.get("/api/v1/catalog/model-registry")
    assert response.status_code == 200
    body = response.json()
    assert len(body["entries"]) == len(MODEL_REGISTRY)


async def test_list_model_registry_includes_pinned_entry(client: AsyncClient) -> None:
    response = await client.get("/api/v1/catalog/model-registry")
    body = response.json()
    pinned = [entry for entry in body["entries"] if entry["is_pinned"]]
    assert len(pinned) >= 1
    assert pinned[0]["name"] == "qwen2.5-1.5b"


async def test_list_model_registry_entries_have_required_fields(client: AsyncClient) -> None:
    response = await client.get("/api/v1/catalog/model-registry")
    body = response.json()
    for entry in body["entries"]:
        assert entry.keys() == {"name", "params", "context", "license", "source", "is_pinned"}
        assert isinstance(entry["is_pinned"], bool)
