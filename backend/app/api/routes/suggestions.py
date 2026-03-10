from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import (
    ConfigVersionNotFoundError,
    ProjectNotFoundError,
    SuggestionNotFoundError,
)
from app.schemas.suggestion import (
    SuggestionGenerateRequest,
    SuggestionListResponse,
    SuggestionResponse,
)
from app.services import suggestion_service

router = APIRouter(prefix="/api/v1/projects", tags=["suggestions"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/{project_id}/suggestions", response_model=SuggestionListResponse)
async def list_suggestions(
    project_id: str,
    session: DbSession,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuggestionListResponse:
    try:
        return await suggestion_service.list_suggestions(
            session=session,
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.post(
    "/{project_id}/suggestions/generate",
    response_model=SuggestionListResponse,
    status_code=201,
)
async def generate_suggestions(
    project_id: str,
    payload: SuggestionGenerateRequest,
    session: DbSession,
) -> SuggestionListResponse:
    try:
        return await suggestion_service.generate_suggestions(
            session=session,
            project_id=project_id,
            source_run_id=payload.source_run_id,
            notes=payload.notes,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_ACTIVE_CONFIG", "message": str(exc), "details": {}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "GENERATION_ERROR", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/suggestions/{suggestion_id}", response_model=SuggestionResponse)
async def get_suggestion(
    project_id: str,
    suggestion_id: str,
    session: DbSession,
) -> SuggestionResponse:
    try:
        return await suggestion_service.get_suggestion(
            session=session,
            project_id=project_id,
            suggestion_id=suggestion_id,
        )
    except SuggestionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SUGGESTION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.post(
    "/{project_id}/suggestions/{suggestion_id}/accept",
    response_model=SuggestionResponse,
)
async def accept_suggestion(
    project_id: str,
    suggestion_id: str,
    session: DbSession,
) -> SuggestionResponse:
    try:
        return await suggestion_service.accept_suggestion(
            session=session,
            project_id=project_id,
            suggestion_id=suggestion_id,
        )
    except SuggestionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SUGGESTION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_ACTIVE_CONFIG", "message": str(exc), "details": {}},
        ) from exc


@router.post(
    "/{project_id}/suggestions/{suggestion_id}/reject",
    response_model=SuggestionResponse,
)
async def reject_suggestion(
    project_id: str,
    suggestion_id: str,
    session: DbSession,
) -> SuggestionResponse:
    try:
        return await suggestion_service.reject_suggestion(
            session=session,
            project_id=project_id,
            suggestion_id=suggestion_id,
        )
    except SuggestionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SUGGESTION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
