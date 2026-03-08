from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_system_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health/system")
    assert response.status_code == 200
    body = response.json()
    assert "cpu_count" in body
    assert "ram_total_mb" in body
    assert "disk_free_gb" in body
    assert "model_loaded" in body
    assert body["model_loaded"] is False
