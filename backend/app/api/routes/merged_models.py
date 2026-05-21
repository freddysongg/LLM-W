from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import (
    ConfigVersionNotFoundError,
    NoCheckpointError,
    ProjectNotFoundError,
    RunNotFoundError,
)
from app.schemas.merged_model import (
    MergedModelListResponse,
    MergedModelResponse,
    MergeRunRequest,
)
from app.services import merged_models_service
from app.services.merged_models_service import (
    MergedModelNotFoundError,
    MissingBaseModelError,
)

router = APIRouter(prefix="/api/v1/projects", tags=["merged-models"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "/{project_id}/merged-models",
    response_model=MergedModelListResponse,
)
async def list_merged_models(
    project_id: str,
    session: DbSession,
) -> MergedModelListResponse:
    try:
        return await merged_models_service.list_merged_models(
            session=session, project_id=project_id
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.post(
    "/{project_id}/merged-models",
    response_model=MergedModelResponse,
    status_code=201,
)
async def create_merged_model(
    project_id: str,
    payload: MergeRunRequest,
    session: DbSession,
) -> MergedModelResponse:
    try:
        return await merged_models_service.merge_run_into_base(
            session=session,
            project_id=project_id,
            source_run_id=payload.source_run_id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RUN_NOT_FOUND",
                "message": str(exc),
                "details": {"run_id": exc.run_id},
            },
        ) from exc
    except NoCheckpointError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_CHECKPOINT_FOR_MERGE",
                "message": str(exc),
                "details": {"run_id": exc.run_id},
            },
        ) from exc
    except MissingBaseModelError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "MISSING_BASE_MODEL",
                "message": str(exc),
                "details": {"project_id": exc.project_id},
            },
        ) from exc
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_ACTIVE_CONFIG", "message": str(exc), "details": {}},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "MERGE_FAILED",
                "message": str(exc),
                "details": {},
            },
        ) from exc


@router.get(
    "/{project_id}/merged-models/{merged_id}",
    response_model=MergedModelResponse,
)
async def get_merged_model(
    project_id: str,
    merged_id: str,
    session: DbSession,
) -> MergedModelResponse:
    try:
        return await merged_models_service.get_merged_model(
            session=session, project_id=project_id, merged_id=merged_id
        )
    except MergedModelNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MERGED_MODEL_NOT_FOUND",
                "message": str(exc),
                "details": {"merged_id": exc.merged_id},
            },
        ) from exc


@router.delete(
    "/{project_id}/merged-models/{merged_id}",
    status_code=204,
)
async def delete_merged_model(
    project_id: str,
    merged_id: str,
    session: DbSession,
) -> None:
    try:
        await merged_models_service.delete_merged_model(
            session=session, project_id=project_id, merged_id=merged_id
        )
    except MergedModelNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MERGED_MODEL_NOT_FOUND",
                "message": str(exc),
                "details": {"merged_id": exc.merged_id},
            },
        ) from exc
