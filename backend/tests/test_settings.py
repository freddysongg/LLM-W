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


async def test_modal_test_valid_gpu_without_credentials(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/settings/modal/test",
        json={"default_gpu_type": "a10"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["gpu_type_valid"] is True
    assert body["resolved_gpu_spec"] == "A10G"
    assert "No Modal token" in body["message"]


async def test_modal_test_invalid_gpu_short_circuits(client: AsyncClient) -> None:
    # Sanity that the invalid-GPU branch is independent of credentials and of any
    # network calls — the response must come back fast and consistent.
    response = await client.post(
        "/api/v1/settings/modal/test",
        json={"default_gpu_type": "nvidia-3090"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["gpu_type_valid"] is False
    assert body["resolved_gpu_spec"] is None
    assert "nvidia-3090" in body["message"]


async def test_modal_test_invalid_gpu_short_circuits_without_modal_import(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # If invalid-GPU validation accidentally triggered `import modal` or any
    # Modal client call, this test would crash because the patched module is
    # broken on purpose. Passing proves the early-return path is honored.
    import sys

    monkeypatch.setitem(sys.modules, "modal", None)
    response = await client.post(
        "/api/v1/settings/modal/test",
        json={"default_gpu_type": "totally-fake"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["gpu_type_valid"] is False


async def test_modal_test_no_body_returns_legacy_shape(client: AsyncClient) -> None:
    response = await client.post("/api/v1/settings/modal/test")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["gpu_type_valid"] is None
    assert body["resolved_gpu_spec"] is None
    assert "No Modal token" in body["message"]


async def test_get_modal_credentials_falls_back_to_app_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings_service.settings, "modal_token_id", "env-id")
    monkeypatch.setattr(settings_service.settings, "modal_token_secret", "env-secret")

    credentials = settings_service.get_modal_credentials()
    assert credentials == ("env-id", "env-secret")


async def test_get_modal_credentials_prefers_overrides_over_app_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings_service.settings, "modal_token_id", "env-id")
    monkeypatch.setattr(settings_service.settings, "modal_token_secret", "env-secret")
    settings_service._overrides["modal_token_id"] = "override-id"
    settings_service._overrides["modal_token_secret"] = "override-secret"

    credentials = settings_service.get_modal_credentials()
    assert credentials == ("override-id", "override-secret")


async def test_get_settings_reports_modal_token_set_when_env_provided(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings_service.settings, "modal_token_id", "env-id")
    monkeypatch.setattr(settings_service.settings, "modal_token_secret", "env-secret")

    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["is_modal_token_set"] is True
