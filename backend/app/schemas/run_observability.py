from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigDiff(BaseModel):
    changed: dict[str, dict[str, Any]]
    added: dict[str, Any]
    removed: dict[str, Any]


class ConfigSnapshotResponse(BaseModel):
    run_id: str
    parent_config_version_id: str
    yaml: str
    diff: ConfigDiff


class MetricNamesResponse(BaseModel):
    metric_names: list[str]


class RunSummaryResponse(BaseModel):
    run_id: str
    status: str
    final_train_loss: float | None
    final_eval_loss: float | None
    wall_clock_ms: int
    step_count: int
    train_loss_sparkline: list[float]


class RunSummaryBatchResponse(BaseModel):
    runs: list[RunSummaryResponse]
