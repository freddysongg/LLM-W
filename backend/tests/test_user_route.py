from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_get_current_user_defaults(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": "local",
        "name": "Local User",
        "email": "local@llm-workbench.dev",
    }


async def test_get_current_user_respects_settings_overrides(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "local_user_id", "alice")
    monkeypatch.setattr(cfg_module.settings, "local_user_name", "Alice Smith")
    monkeypatch.setattr(cfg_module.settings, "local_user_email", "alice@example.com")

    response = await client.get("/api/v1/me")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "alice"
    assert body["name"] == "Alice Smith"
    assert body["email"] == "alice@example.com"
