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
