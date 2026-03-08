from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import settings_service


@pytest.fixture(autouse=True)
def reset_overrides():
    settings_service._overrides.clear()
    yield
    settings_service._overrides.clear()


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_get_settings_defaults(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert "ai_provider" in body
    assert "ai_api_key_set" in body
    assert "ai_model_id" in body
    assert "storage_warning_threshold_gb" in body
    assert "watchdog_stale_timeout_seconds" in body
    assert "watchdog_heartbeat_interval_seconds" in body


async def test_patch_settings_model_id(client: AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/settings",
        json={"ai_model_id": "claude-opus-4-6"},
    )
    assert response.status_code == 200
    assert response.json()["ai_model_id"] == "claude-opus-4-6"


async def test_patch_settings_threshold(client: AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/settings",
        json={"storage_warning_threshold_gb": 100.0},
    )
    assert response.status_code == 200
    assert response.json()["storage_warning_threshold_gb"] == 100.0


async def test_patch_settings_persists_across_get(client: AsyncClient) -> None:
    await client.patch("/api/v1/settings", json={"ai_provider": "openai_compatible"})
    get_resp = await client.get("/api/v1/settings")
    assert get_resp.json()["ai_provider"] == "openai_compatible"


async def test_ai_test_no_key(client: AsyncClient) -> None:
    response = await client.post("/api/v1/settings/ai/test")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "No API key" in body["message"]
