from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ModelResolveRequest(BaseModel):
    source: Literal["huggingface", "local"]
    model_id: str
    revision: str = "main"
    trust_remote_code: bool = False


class ResourceEstimate(BaseModel):
    vram_gb: float
    disk_gb: float
    training_memory_gb: float


class ModelProfile(BaseModel):
    model_id: str
    source: Literal["huggingface", "local"]
    family: str
    architecture_name: str
    total_parameters: int
    trainable_parameters: int
    resource_estimate: ResourceEstimate
    torch_dtype: str
    vocabulary_size: int | None
    context_length: int | None
    resolved_at: str


class LayerNode(BaseModel):
    name: str
    type: str
    params: int | None = None
    trainable: bool | None = None
    dtype: str | None = None
    shape: list[int] | None = None
    children: list[LayerNode] | None = None


class ModelArchitectureResponse(BaseModel):
    model_id: str
    architecture_name: str
    total_parameters: int
    trainable_parameters: int
    tree: LayerNode


class LayerDetailResponse(BaseModel):
    name: str
    type: str
    params: int
    trainable: bool
    dtype: str | None
    shape: list[int] | None


class ActivationCaptureRequest(BaseModel):
    layer_names: list[str]
    sample_input: str


class TierOneStats(BaseModel):
    mean: float
    std: float
    min: float
    max: float
    histogram_bins: list[float]


class ActivationLayerSnapshot(BaseModel):
    layer_name: str
    tier1: TierOneStats
    shape: list[int]


class ActivationSnapshotResponse(BaseModel):
    id: str
    created_at: str
    layers: list[ActivationLayerSnapshot]


class FullTensorRequest(BaseModel):
    layer_names: list[str] | None = None


class FullTensorResponse(BaseModel):
    snapshot_id: str
    layer_tensors: dict[str, Any]
