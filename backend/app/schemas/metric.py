from __future__ import annotations

from pydantic import BaseModel


class MetricPointResponse(BaseModel):
    id: str
    run_id: str
    step: int
    epoch: float | None
    metric_name: str
    metric_value: float
    stage_name: str | None
    recorded_at: str

    model_config = {"from_attributes": True}
