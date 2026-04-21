from __future__ import annotations

from pydantic import BaseModel


class LayerProfile(BaseModel):
    name: str
    shape: list[int]
    param_count: int
    trainable: bool
    dtype: str


class ModelProfileResponse(BaseModel):
    run_id: str
    total_params: int
    trainable_params: int
    layers: list[LayerProfile]


class LayerWeightStats(BaseModel):
    step: int
    mean: float
    std: float
    norm: float
    min_val: float
    max_val: float


class WeightSnapshotResponse(BaseModel):
    run_id: str
    layer_name: str | None
    points: list[LayerWeightStats]


class WeightSnapshotAllResponse(BaseModel):
    run_id: str
    snapshots_by_layer: dict[str, list[LayerWeightStats]]
