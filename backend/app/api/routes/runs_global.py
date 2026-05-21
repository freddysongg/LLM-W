from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.run import Run
from app.schemas.run import RunListResponse, RunResponse

router = APIRouter(prefix="/api/v1", tags=["runs"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

_DEFAULT_LIMIT = 10
_MIN_LIMIT = 1
_MAX_LIMIT = 100


@router.get("/runs", response_model=RunListResponse)
async def list_runs_global(
    session: DbSession,
    limit: int = _DEFAULT_LIMIT,
) -> RunListResponse:
    """Cross-project recent runs feed.

    Used by the command palette so the user can jump to any recent run without
    having to switch to the owning project first. The endpoint is intentionally
    unfiltered by status — the client filters down to active runs for actions
    like pause/stop while still being able to display the full list.
    """
    effective_limit = max(_MIN_LIMIT, min(limit, _MAX_LIMIT))
    result = await session.execute(
        select(Run).order_by(Run.created_at.desc()).limit(effective_limit)
    )
    runs = list(result.scalars().all())
    return RunListResponse(
        items=[RunResponse.model_validate(run) for run in runs],
        total=len(runs),
        limit=effective_limit,
        offset=0,
    )
