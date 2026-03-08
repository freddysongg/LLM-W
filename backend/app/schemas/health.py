from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class SystemHealthResponse(BaseModel):
    gpu_available: bool
    gpu_name: str | None
    gpu_memory_total_mb: int | None
    gpu_memory_used_mb: int | None
    cpu_count: int
    ram_total_mb: int
    ram_used_mb: int
    disk_free_gb: float
    model_loaded: bool
    active_run_id: str | None
    torch_device: str
    torch_version: str
    cuda_available: bool
    mps_available: bool
