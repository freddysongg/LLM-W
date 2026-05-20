from __future__ import annotations

from app.api.websocket.stream import _collect_system_resources


def test_collect_system_resources_includes_ram_total() -> None:
    payload = _collect_system_resources()
    assert "ram_total_mb" in payload
    assert payload["ram_total_mb"] > 0
    assert payload["ram_used_mb"] <= payload["ram_total_mb"]


def test_collect_system_resources_has_vram_total_field() -> None:
    payload = _collect_system_resources()
    assert "vram_total_mb" in payload


def test_collect_system_resources_drops_gpu_utilization_pct() -> None:
    payload = _collect_system_resources()
    assert "gpu_utilization_pct" not in payload
