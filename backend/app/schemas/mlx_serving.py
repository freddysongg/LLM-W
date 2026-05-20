"""Request/response shapes for the local MLX serving routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ServingState = Literal["stopped", "starting", "running", "failed", "stopping"]


class ServeRequest(BaseModel):
    serving_model_id: str | None = None
    run_id: str | None = None
    trust_remote_code: bool = False


class ServingStatus(BaseModel):
    project_id: str
    state: ServingState
    base_url: str | None = None
    model_id: str | None = None
    adapter_path: str | None = None
    pid: int | None = None
    started_at: str | None = None
    last_error: str | None = None


class ServingStartResponse(BaseModel):
    status: ServingStatus
