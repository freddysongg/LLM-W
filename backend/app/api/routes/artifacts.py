from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import ArtifactFileNotFoundError, ArtifactNotFoundError
from app.schemas.artifact import ArtifactCleanupResponse, ArtifactListResponse, ArtifactResponse
from app.services import storage_manager

router = APIRouter(prefix="/api/v1/projects", tags=["artifacts"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/{project_id}/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    project_id: str,
    session: DbSession,
    run_id: str | None = Query(default=None),
    artifact_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ArtifactListResponse:
    return await storage_manager.list_artifacts(
        session=session,
        project_id=project_id,
        run_id=run_id,
        artifact_type=artifact_type,
        limit=limit,
        offset=offset,
    )


# /cleanup must be registered before /{artifact_id} to avoid path conflicts
@router.post("/{project_id}/artifacts/cleanup", response_model=ArtifactCleanupResponse)
async def cleanup_artifacts(
    project_id: str,
    session: DbSession,
) -> ArtifactCleanupResponse:
    return await storage_manager.run_artifact_cleanup(
        session=session,
        project_id=project_id,
    )


@router.get("/{project_id}/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    project_id: str,
    artifact_id: str,
    session: DbSession,
) -> ArtifactResponse:
    try:
        return await storage_manager.get_artifact(
            session=session,
            project_id=project_id,
            artifact_id=artifact_id,
        )
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "ARTIFACT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    project_id: str,
    artifact_id: str,
    session: DbSession,
) -> FileResponse:
    try:
        return await storage_manager.get_artifact_download(
            session=session,
            project_id=project_id,
            artifact_id=artifact_id,
        )
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "ARTIFACT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except ArtifactFileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "ARTIFACT_FILE_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.delete("/{project_id}/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(
    project_id: str,
    artifact_id: str,
    session: DbSession,
) -> None:
    try:
        await storage_manager.delete_artifact(
            session=session,
            project_id=project_id,
            artifact_id=artifact_id,
        )
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "ARTIFACT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
