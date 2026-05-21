from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.modal_catalog import (
    MODAL_GPU_CATALOG,
    get_modal_gpu_option,
    get_modal_gpu_rate_usd_per_second,
)
from app.main import app

_EXPECTED_GPU_TYPES: tuple[str, ...] = (
    "t4",
    "a10",
    "l40s",
    "a100-40gb",
    "a100-80gb",
    "h100",
)


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_modal_gpu_catalog_route_returns_all_options(client: AsyncClient) -> None:
    response = await client.get("/api/v1/catalog/modal-gpus")
    assert response.status_code == 200, response.text
    body = response.json()
    options = body["options"]
    assert len(options) == len(_EXPECTED_GPU_TYPES)
    for entry in options:
        assert set(entry.keys()) == {"gpu_type", "label", "vram_gb", "rate_usd_hr"}


async def test_modal_gpu_catalog_content_stable(client: AsyncClient) -> None:
    response = await client.get("/api/v1/catalog/modal-gpus")
    assert response.status_code == 200, response.text
    options = response.json()["options"]
    received_types = tuple(entry["gpu_type"] for entry in options)
    assert received_types == _EXPECTED_GPU_TYPES
    for entry in options:
        assert entry["rate_usd_hr"] > 0.0
        assert entry["vram_gb"] > 0
        assert entry["label"]


def test_get_modal_gpu_rate_returns_zero_for_unknown_type() -> None:
    assert get_modal_gpu_rate_usd_per_second(gpu_type="nvidia-3090") == 0.0
    assert get_modal_gpu_rate_usd_per_second(gpu_type="") == 0.0


def test_get_modal_gpu_rate_matches_per_hour_division() -> None:
    for option in MODAL_GPU_CATALOG:
        rate_per_second = get_modal_gpu_rate_usd_per_second(gpu_type=option.gpu_type)
        assert rate_per_second == pytest.approx(option.rate_usd_hr / 3600.0)


def test_get_modal_gpu_option_lookup() -> None:
    assert get_modal_gpu_option(gpu_type="l40s") is not None
    assert get_modal_gpu_option(gpu_type="nvidia-3090") is None
