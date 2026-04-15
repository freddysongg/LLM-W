from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.models.rubric import Rubric
from app.schemas.eval import RubricSummary, RubricVersionSummary

router = APIRouter(prefix="/api/v1", tags=["rubrics"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _rubric_summary(*, rubric: Rubric) -> RubricSummary:
    return RubricSummary(
        id=rubric.id,
        name=rubric.name,
        description=rubric.description,
        research_basis=rubric.research_basis,
        created_at=rubric.created_at,
        versions=[
            RubricVersionSummary(
                id=version.id,
                rubric_id=version.rubric_id,
                version_number=version.version_number,
                content_hash=version.content_hash,
                calibration_status=version.calibration_status,
                judge_model_pin=version.judge_model_pin,
                created_at=version.created_at,
            )
            for version in rubric.versions
        ],
    )


@router.get("/rubrics", response_model=list[RubricSummary])
async def list_rubrics(session: DbSession) -> list[RubricSummary]:
    result = await session.execute(select(Rubric).options(selectinload(Rubric.versions)))
    rubrics = result.scalars().all()
    return [_rubric_summary(rubric=rubric) for rubric in rubrics]
