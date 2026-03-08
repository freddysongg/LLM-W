from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import (
    ActivationSnapshotNotFoundError,
    LayerNotFoundError,
    ModelNotResolvedError,
    ModelResolveError,
    ProjectNotFoundError,
)
from app.schemas.model import (
    ActivationCaptureRequest,
    ActivationSnapshotResponse,
    FullTensorRequest,
    FullTensorResponse,
    LayerDetailResponse,
    ModelArchitectureResponse,
    ModelProfile,
    ModelResolveRequest,
)
from app.services import model_service, project_service

router = APIRouter(prefix="/api/v1/projects", tags=["models"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/{project_id}/models/resolve", response_model=ModelProfile, status_code=200)
async def resolve_model(
    project_id: str,
    payload: ModelResolveRequest,
    session: DbSession,
) -> ModelProfile:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return await model_service.resolve_model(project_id=project_id, request=payload)
    except ModelResolveError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "MODEL_RESOLVE_ERROR", "message": exc.message, "details": {}},
        ) from exc


@router.get("/{project_id}/models/profile", response_model=ModelProfile)
async def get_model_profile(
    project_id: str,
    session: DbSession,
) -> ModelProfile:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return model_service.get_model_profile(project_id=project_id)
    except ModelNotResolvedError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "MODEL_NOT_RESOLVED", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/models/architecture", response_model=ModelArchitectureResponse)
async def get_model_architecture(
    project_id: str,
    session: DbSession,
) -> ModelArchitectureResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return await model_service.get_model_architecture(project_id=project_id)
    except ModelNotResolvedError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "MODEL_NOT_RESOLVED", "message": str(exc), "details": {}},
        ) from exc
    except ModelResolveError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "MODEL_RESOLVE_ERROR", "message": exc.message, "details": {}},
        ) from exc


@router.get("/{project_id}/models/layers/{layer_name:path}", response_model=LayerDetailResponse)
async def get_layer_detail(
    project_id: str,
    layer_name: str,
    session: DbSession,
) -> LayerDetailResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return model_service.get_layer_detail(project_id=project_id, layer_name=layer_name)
    except ModelNotResolvedError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "MODEL_NOT_RESOLVED", "message": str(exc), "details": {}},
        ) from exc
    except LayerNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "LAYER_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.post(
    "/{project_id}/models/activations",
    response_model=ActivationSnapshotResponse,
    status_code=200,
)
async def capture_activations(
    project_id: str,
    payload: ActivationCaptureRequest,
    session: DbSession,
) -> ActivationSnapshotResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return await model_service.capture_activations(
            project_id=project_id, request=payload
        )
    except ModelNotResolvedError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "MODEL_NOT_RESOLVED", "message": str(exc), "details": {}},
        ) from exc
    except ModelResolveError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "MODEL_RESOLVE_ERROR", "message": exc.message, "details": {}},
        ) from exc


@router.get(
    "/{project_id}/models/activations/{snapshot_id}",
    response_model=ActivationSnapshotResponse,
)
async def get_activation_snapshot(
    project_id: str,
    snapshot_id: str,
    session: DbSession,
) -> ActivationSnapshotResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return model_service.get_activation_snapshot(
            project_id=project_id, snapshot_id=snapshot_id
        )
    except ActivationSnapshotNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SNAPSHOT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.post(
    "/{project_id}/models/activations/{snapshot_id}/full",
    response_model=FullTensorResponse,
    status_code=200,
)
async def request_full_tensor(
    project_id: str,
    snapshot_id: str,
    payload: FullTensorRequest,
    session: DbSession,
) -> FullTensorResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    try:
        return model_service.get_full_tensor(
            project_id=project_id, snapshot_id=snapshot_id, request=payload
        )
    except ActivationSnapshotNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SNAPSHOT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
