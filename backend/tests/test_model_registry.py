from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from app.core.model_registry import MODEL_REGISTRY
from app.main import app

_REQUIRED_ENTRY_KEYS = {"name", "source", "is_pinned"}
_OPTIONAL_ENTRY_KEYS = {"params", "context", "license", "path", "dtype"}


@pytest.fixture
def isolated_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "data_dir", tmp_path)
    return tmp_path


@pytest.fixture
async def client(isolated_data_dir: Path) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_list_model_registry_returns_seed_when_no_manifest(client: AsyncClient) -> None:
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


async def test_list_model_registry_entries_have_unified_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/catalog/model-registry")
    body = response.json()
    for entry in body["entries"]:
        assert _REQUIRED_ENTRY_KEYS.issubset(entry.keys())
        assert entry.keys() <= _REQUIRED_ENTRY_KEYS | _OPTIONAL_ENTRY_KEYS
        assert isinstance(entry["is_pinned"], bool)


async def test_register_model_entry_persists_to_yaml_manifest(
    client: AsyncClient, isolated_data_dir: Path
) -> None:
    response = await client.post(
        "/api/v1/catalog/model-registry",
        json={
            "name": "qwen2.5-3b",
            "source": "hf",
            "path": "Qwen/Qwen2.5-3B",
            "dtype": "bfloat16",
            "is_pinned": False,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "qwen2.5-3b"
    assert body["path"] == "Qwen/Qwen2.5-3B"
    assert body["dtype"] == "bfloat16"
    assert body["is_pinned"] is False

    manifest_path = isolated_data_dir / "model_registry.yaml"
    assert manifest_path.exists()
    parsed = yaml.safe_load(manifest_path.read_text())
    names = [entry["name"] for entry in parsed["entries"]]
    assert "qwen2.5-3b" in names


async def test_register_then_list_returns_new_entry(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/catalog/model-registry",
        json={
            "name": "phi-4",
            "source": "hf",
            "path": "microsoft/phi-4",
            "dtype": "bfloat16",
            "is_pinned": False,
        },
    )
    response = await client.get("/api/v1/catalog/model-registry")
    names = [entry["name"] for entry in response.json()["entries"]]
    assert "phi-4" in names


async def test_register_same_name_upserts(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/catalog/model-registry",
        json={
            "name": "phi-4",
            "source": "hf",
            "path": "microsoft/phi-4",
            "dtype": "bfloat16",
            "is_pinned": False,
        },
    )
    await client.post(
        "/api/v1/catalog/model-registry",
        json={
            "name": "phi-4",
            "source": "local",
            "path": "/models/phi-4",
            "dtype": "float16",
            "is_pinned": True,
        },
    )
    response = await client.get("/api/v1/catalog/model-registry")
    matches = [entry for entry in response.json()["entries"] if entry["name"] == "phi-4"]
    assert len(matches) == 1
    assert matches[0]["source"] == "local"
    assert matches[0]["dtype"] == "float16"
    assert matches[0]["is_pinned"] is True


async def test_first_register_preserves_seed_entries(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/catalog/model-registry",
        json={
            "name": "phi-4",
            "source": "hf",
            "path": "microsoft/phi-4",
            "dtype": "bfloat16",
            "is_pinned": False,
        },
    )
    response = await client.get("/api/v1/catalog/model-registry")
    names = {entry["name"] for entry in response.json()["entries"]}
    for seed in MODEL_REGISTRY:
        assert seed.name in names


async def test_register_rejects_invalid_source(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/catalog/model-registry",
        json={
            "name": "phi-4",
            "source": "ftp",
            "path": "ftp://example.com/phi-4",
            "dtype": "bfloat16",
            "is_pinned": False,
        },
    )
    assert response.status_code == 422
