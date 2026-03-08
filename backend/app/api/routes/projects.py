from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import ProjectNameConflictError, ProjectNotFoundError
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.storage import ProjectStorageResponse
from app.services import project_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=list[ProjectResponse])
async def list_projects(session: DbSession) -> list[ProjectResponse]:
    projects = await project_service.list_projects(session=session)
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    payload: ProjectCreate,
    session: DbSession,
) -> ProjectResponse:
    try:
        project = await project_service.create_project(session=session, payload=payload)
    except ProjectNameConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "PROJECT_NAME_CONFLICT", "message": str(exc), "details": {}},
        ) from exc
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    session: DbSession,
) -> ProjectResponse:
    try:
        project = await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    session: DbSession,
) -> ProjectResponse:
    try:
        project = await project_service.update_project(
            session=session, project_id=project_id, payload=payload
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except ProjectNameConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "PROJECT_NAME_CONFLICT", "message": str(exc), "details": {}},
        ) from exc
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: DbSession,
) -> None:
    try:
        await project_service.delete_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/storage", response_model=ProjectStorageResponse)
async def get_project_storage(
    project_id: str,
    session: DbSession,
) -> ProjectStorageResponse:
    try:
        return await project_service.get_project_storage(
            session=session, project_id=project_id
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
