from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import (
    ConfigVersionNotFoundError,
    DatasetNotResolvedError,
    DatasetResolveError,
    ProjectNotFoundError,
)
from app.schemas.dataset import (
    DatasetProfile,
    DatasetResolveRequest,
    DatasetSamplesResponse,
    PreviewTransformRequest,
    PreviewTransformResponse,
    TokenStats,
)
from app.services import dataset_service, project_service

router = APIRouter(prefix="/api/v1/projects", tags=["datasets"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/{project_id}/datasets/resolve", response_model=DatasetProfile, status_code=200)
async def resolve_dataset(
    project_id: str,
    payload: DatasetResolveRequest,
    session: DbSession,
) -> DatasetProfile:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return await dataset_service.resolve_dataset(
            project_id=project_id, request=payload, session=session
        )
    except DatasetResolveError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "DATASET_RESOLVE_ERROR", "message": exc.message, "details": {}},
        ) from exc
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONFIG_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/datasets/profile", response_model=DatasetProfile)
async def get_dataset_profile(
    project_id: str,
    session: DbSession,
) -> DatasetProfile:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return dataset_service.get_dataset_profile(project_id=project_id)
    except DatasetNotResolvedError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "DATASET_NOT_RESOLVED", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/datasets/samples", response_model=DatasetSamplesResponse)
async def get_dataset_samples(
    project_id: str,
    session: DbSession,
    limit: int = 20,
    offset: int = 0,
) -> DatasetSamplesResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return dataset_service.get_dataset_samples(
            project_id=project_id, limit=limit, offset=offset
        )
    except DatasetNotResolvedError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "DATASET_NOT_RESOLVED", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/datasets/token-stats", response_model=TokenStats)
async def get_token_stats(
    project_id: str,
    session: DbSession,
) -> TokenStats:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return dataset_service.get_token_stats(project_id=project_id)
    except DatasetNotResolvedError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "DATASET_NOT_RESOLVED", "message": str(exc), "details": {}},
        ) from exc
    except DatasetResolveError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "DATASET_RESOLVE_ERROR", "message": exc.message, "details": {}},
        ) from exc


@router.post(
    "/{project_id}/datasets/preview-transform",
    response_model=PreviewTransformResponse,
    status_code=200,
)
async def preview_transform(
    project_id: str,
    payload: PreviewTransformRequest,
    session: DbSession,
) -> PreviewTransformResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return dataset_service.preview_transform(project_id=project_id, request=payload)
    except DatasetNotResolvedError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "DATASET_NOT_RESOLVED", "message": str(exc), "details": {}},
        ) from exc
