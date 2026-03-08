from __future__ import annotations

from pydantic import BaseModel


class StorageRecordResponse(BaseModel):
    id: str
    project_id: str
    category: str
    total_bytes: int
    file_count: int
    last_computed_at: str

    model_config = {"from_attributes": True}


class StorageBreakdownResponse(BaseModel):
    project_id: str
    records: list[StorageRecordResponse]
    total_bytes: int


class StorageCategoryDetail(BaseModel):
    bytes: int
    file_count: int


class RunStorageSummary(BaseModel):
    run_id: str
    total_bytes: int
    checkpoint_count: int
    status: str


class RetentionPolicySummary(BaseModel):
    keep_last_n: int
    reclaimable_bytes: int
    reclaimable_checkpoints: int


class ProjectStorageResponse(BaseModel):
    project_id: str
    total_bytes: int
    breakdown: dict[str, StorageCategoryDetail]
    per_run: list[RunStorageSummary]
    retention_policy: RetentionPolicySummary


class StorageTotalResponse(BaseModel):
    total_bytes: int
    per_project: dict[str, int]
    project_count: int
