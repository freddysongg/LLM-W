from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import ProjectNotFoundError
from app.schemas.artifact import ArtifactCleanupResponse
from app.schemas.storage import ProjectStorageResponse, StorageTotalResponse
from app.services import storage_manager
from app.services.project_service import get_project

router = APIRouter(tags=["storage"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/api/v1/projects/{project_id}/storage", response_model=ProjectStorageResponse)
async def get_project_storage(
    project_id: str,
    session: DbSession,
) -> ProjectStorageResponse:
    try:
        await get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    return await storage_manager.get_project_storage(
        session=session,
        project_id=project_id,
    )


@router.get("/api/v1/storage/total", response_model=StorageTotalResponse)
async def get_total_storage(
    session: DbSession,
) -> StorageTotalResponse:
    return await storage_manager.get_total_storage(session=session)


@router.post(
    "/api/v1/projects/{project_id}/storage/cleanup",
    response_model=ArtifactCleanupResponse,
)
async def run_storage_cleanup(
    project_id: str,
    session: DbSession,
) -> ArtifactCleanupResponse:
    try:
        await get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    return await storage_manager.run_project_cleanup(
        session=session,
        project_id=project_id,
    )
