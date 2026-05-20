"""HTTP routes for the local MLX serving lifecycle.

Routes are project-scoped (`/api/v1/projects/{project_id}/serve`) per the
design decision documented in `.context/designs/mlx-serving.md`. The
serving state map keys on project id, not on model id, because the project
owns the active config resolution.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import (
    MissingServingModelIdError,
    ProjectNotFoundError,
)
from app.schemas.mlx_serving import (
    ServeRequest,
    ServingStartResponse,
    ServingStatus,
)
from app.services import config_service, project_service
from app.services.cloud import mlx_serving_registry
from app.services.cloud.mlx_serving import (
    AdapterConversionUnsupportedError,
    MLXNotInstalledError,
    MLXServerStartupTimeoutError,
    ServingStartupError,
    UnsupportedServingPlatformError,
)
from app.services.cloud.mlx_serving_registry import (
    ServingCapacityExceededError,
    ServingNotRunningError,
)

router = APIRouter(prefix="/api/v1/projects", tags=["mlx-serving"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


_ServingDomainError = (
    MissingServingModelIdError,
    ServingCapacityExceededError,
    UnsupportedServingPlatformError,
    MLXNotInstalledError,
    AdapterConversionUnsupportedError,
    ServingStartupError,
    MLXServerStartupTimeoutError,
)


@router.post(
    "/{project_id}/serve",
    response_model=ServingStartResponse,
    status_code=200,
)
async def start_serve(
    project_id: str,
    payload: ServeRequest,
    session: DbSession,
) -> ServingStartResponse:
    await _require_project(session=session, project_id=project_id)
    try:
        serving_model_id = await _resolve_serving_model_id(
            session=session,
            project_id=project_id,
            requested_model_id=payload.serving_model_id,
        )
        status = await mlx_serving_registry.start_serving(
            project_id=project_id,
            serving_model_id=serving_model_id,
            adapter_path=_resolve_adapter_path(run_id=payload.run_id),
            trust_remote_code=payload.trust_remote_code,
        )
    except _ServingDomainError as exc:
        raise _map_serving_exception(exc) from exc
    return ServingStartResponse(status=status)


@router.get("/{project_id}/serve", response_model=ServingStatus)
async def get_serve_status(
    project_id: str,
    session: DbSession,
) -> ServingStatus:
    await _require_project(session=session, project_id=project_id)
    return mlx_serving_registry.get_status(project_id=project_id)


@router.delete("/{project_id}/serve", status_code=204)
async def stop_serve(
    project_id: str,
    session: DbSession,
) -> Response:
    await _require_project(session=session, project_id=project_id)
    with contextlib.suppress(ServingNotRunningError):
        await mlx_serving_registry.stop_serving(project_id=project_id)
    return Response(status_code=204)


async def _require_project(*, session: AsyncSession, project_id: str) -> None:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


async def _resolve_serving_model_id(
    *,
    session: AsyncSession,
    project_id: str,
    requested_model_id: str | None,
) -> str:
    if requested_model_id:
        return requested_model_id
    active = await config_service.get_active_config_version(
        session=session, project_id=project_id
    )
    yaml_blob = await config_service.get_config_yaml(
        session=session, project_id=project_id, version_id=active.id
    )
    parsed = yaml.safe_load(yaml_blob) or {}
    model_section = parsed.get("model", {}) if isinstance(parsed, dict) else {}
    configured: object = (
        model_section.get("serving_model_id") if isinstance(model_section, dict) else None
    )
    if isinstance(configured, str) and configured:
        return configured
    raise MissingServingModelIdError(project_id)


def _resolve_adapter_path(*, run_id: str | None) -> Path | None:
    """Resolve run id to a checkpoint path. v1 only validates the type.

    Real adapter conversion (peft → MLX) is deferred per the design doc.
    `MLXServingAdapter._guard_adapter_compatibility` will reject the
    incompatible combination at start time with a typed exception.
    """
    if run_id is None:
        return None
    return Path(run_id)


def _map_serving_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, MissingServingModelIdError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "MODEL_NOT_CONFIGURED_FOR_SERVING",
                "message": str(exc),
                "details": {},
            },
        )
    if isinstance(exc, ServingCapacityExceededError):
        return HTTPException(
            status_code=409,
            detail={
                "code": "SERVING_CAPACITY_EXCEEDED",
                "message": str(exc),
                "details": {"active_project_id": exc.active_project_id},
            },
        )
    if isinstance(exc, UnsupportedServingPlatformError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_PLATFORM",
                "message": str(exc),
                "details": {"system": exc.system, "machine": exc.machine},
            },
        )
    if isinstance(exc, MLXNotInstalledError):
        return HTTPException(
            status_code=422,
            detail={"code": "MLX_NOT_INSTALLED", "message": str(exc), "details": {}},
        )
    if isinstance(exc, AdapterConversionUnsupportedError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "ADAPTER_CONVERSION_UNSUPPORTED",
                "message": str(exc),
                "details": {"serving_model_id": exc.serving_model_id},
            },
        )
    return HTTPException(
        status_code=500,
        detail={
            "code": "SERVING_STARTUP_FAILED",
            "message": str(exc),
            "details": {},
        },
    )
