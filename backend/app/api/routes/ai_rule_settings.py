from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import ProjectNotFoundError
from app.models.project import Project
from app.schemas.ai_rule_settings import (
    AIRuleSettingsResponse,
    AIRuleSettingsUpdateRequest,
)
from app.services import ai_rule_settings_service

router = APIRouter(prefix="/api/v1/projects", tags=["ai-rule-settings"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def _resolve_project_dir(*, session: AsyncSession, project_id: str) -> Path:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(project_id)
    return Path(project.directory_path)


@router.get(
    "/{project_id}/ai-rule-settings", response_model=AIRuleSettingsResponse
)
async def get_ai_rule_settings(
    project_id: str, session: DbSession
) -> AIRuleSettingsResponse:
    try:
        project_dir = await _resolve_project_dir(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    settings = ai_rule_settings_service.get_rule_settings(project_dir=project_dir)
    return AIRuleSettingsResponse.model_validate(settings.model_dump())


@router.put(
    "/{project_id}/ai-rule-settings", response_model=AIRuleSettingsResponse
)
async def update_ai_rule_settings(
    project_id: str,
    payload: AIRuleSettingsUpdateRequest,
    session: DbSession,
) -> AIRuleSettingsResponse:
    try:
        project_dir = await _resolve_project_dir(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    saved = ai_rule_settings_service.save_rule_settings(
        project_dir=project_dir, settings=payload
    )
    return AIRuleSettingsResponse.model_validate(saved.model_dump())
