from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import (
    ConfigValidationError,
    ConfigVersionNotFoundError,
    ProjectNotFoundError,
)
from app.schemas.config_version import (
    ConfigDiffResponse,
    ConfigValidationResponse,
    ConfigVersionCreate,
    ConfigVersionListResponse,
    ConfigVersionResponse,
)
from app.services import config_service, project_service

router = APIRouter(prefix="/api/v1/projects", tags=["configs"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/{project_id}/configs", response_model=ConfigVersionListResponse)
async def list_config_versions(
    project_id: str,
    limit: int = 20,
    offset: int = 0,
    session: DbSession = None,  # type: ignore[assignment]
) -> ConfigVersionListResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc

    return await config_service.list_config_versions(
        session=session, project_id=project_id, limit=limit, offset=offset
    )


@router.get("/{project_id}/configs/active", response_model=ConfigVersionResponse)
async def get_active_config_version(
    project_id: str,
    session: DbSession = None,  # type: ignore[assignment]
) -> ConfigVersionResponse:
    try:
        return await config_service.get_active_config_version(
            session=session, project_id=project_id
        )
    except (ConfigVersionNotFoundError, ProjectNotFoundError) as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONFIG_VERSION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/configs/{version_id}", response_model=ConfigVersionResponse)
async def get_config_version(
    project_id: str,
    version_id: str,
    session: DbSession = None,  # type: ignore[assignment]
) -> ConfigVersionResponse:
    try:
        return await config_service.get_config_version(
            session=session, project_id=project_id, version_id=version_id
        )
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONFIG_VERSION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.put("/{project_id}/configs", response_model=ConfigVersionResponse, status_code=201)
async def create_config_version(
    project_id: str,
    payload: ConfigVersionCreate,
    session: DbSession = None,  # type: ignore[assignment]
) -> ConfigVersionResponse:
    try:
        await project_service.get_project(session=session, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc

    try:
        version = await config_service.create_config_version(
            session=session, project_id=project_id, payload=payload
        )
    except ConfigValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "CONFIG_VALIDATION_ERROR", "message": str(exc), "details": {}},
        ) from exc

    await project_service.set_active_config_version(
        session=session,
        project_id=project_id,
        config_version_id=version.id,
    )

    return ConfigVersionResponse.model_validate(version)


@router.get(
    "/{project_id}/configs/{version_id}/diff/{other_version_id}",
    response_model=ConfigDiffResponse,
)
async def diff_config_versions(
    project_id: str,
    version_id: str,
    other_version_id: str,
    session: DbSession = None,  # type: ignore[assignment]
) -> ConfigDiffResponse:
    try:
        return await config_service.diff_config_versions(
            session=session,
            project_id=project_id,
            version_a_id=version_id,
            version_b_id=other_version_id,
        )
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONFIG_VERSION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.post(
    "/{project_id}/configs/{version_id}/validate",
    response_model=ConfigValidationResponse,
)
async def validate_config_version(
    project_id: str,
    version_id: str,
    session: DbSession = None,  # type: ignore[assignment]
) -> ConfigValidationResponse:
    try:
        yaml_content = await config_service.get_config_yaml(
            session=session, project_id=project_id, version_id=version_id
        )
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONFIG_VERSION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc

    return config_service.validate_config(yaml_content=yaml_content)


@router.get("/{project_id}/configs/{version_id}/yaml")
async def get_config_yaml(
    project_id: str,
    version_id: str,
    session: DbSession = None,  # type: ignore[assignment]
) -> PlainTextResponse:
    try:
        yaml_content = await config_service.get_config_yaml(
            session=session, project_id=project_id, version_id=version_id
        )
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONFIG_VERSION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc

    return PlainTextResponse(content=yaml_content, media_type="text/yaml")
