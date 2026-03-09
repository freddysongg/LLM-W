from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import (
    ConfigVersionNotFoundError,
    NoCheckpointError,
    ProjectNotFoundError,
    RunNotFoundError,
    RunStateError,
)
from app.schemas.metric import MetricPointResponse
from app.schemas.run import (
    RunCompareResponse,
    RunCreate,
    RunListResponse,
    RunLogsResponse,
    RunResponse,
    RunResumeResponse,
    RunStageResponse,
)
from app.services import orchestrator, run_service
from app.services.project_service import get_project

router = APIRouter(prefix="/api/v1/projects", tags=["runs"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/{project_id}/runs", response_model=RunListResponse)
async def list_runs(
    project_id: str,
    session: DbSession,
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RunListResponse:
    return await run_service.list_runs(
        session=session,
        project_id=project_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/{project_id}/runs", response_model=RunResponse, status_code=201)
async def create_run(
    project_id: str,
    payload: RunCreate,
    session: DbSession,
) -> RunResponse:
    try:
        run = await orchestrator.create_run(
            session=session,
            project_id=project_id,
            payload=payload,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONFIG_VERSION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    return RunResponse.model_validate(run)


# /compare must be registered before /{run_id} to avoid path conflicts
@router.get("/{project_id}/runs/compare", response_model=RunCompareResponse)
async def compare_runs(
    project_id: str,
    session: DbSession,
    run_ids: str = Query(..., description="Comma-separated list of run IDs to compare"),
) -> RunCompareResponse:
    id_list = [rid.strip() for rid in run_ids.split(",") if rid.strip()]
    if len(id_list) < 2:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PARAMS",
                "message": "At least 2 run IDs required for comparison",
                "details": {},
            },
        )
    try:
        return await run_service.compare_runs(
            session=session,
            project_id=project_id,
            run_ids=id_list,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/runs/{run_id}", response_model=RunResponse)
async def get_run(
    project_id: str,
    run_id: str,
    session: DbSession,
) -> RunResponse:
    try:
        run = await run_service.get_run(
            session=session,
            run_id=run_id,
            project_id=project_id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    return RunResponse.model_validate(run)


@router.post("/{project_id}/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    project_id: str,
    run_id: str,
    session: DbSession,
) -> RunResponse:
    try:
        run = await run_service.cancel_run(
            session=session,
            run_id=run_id,
            project_id=project_id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except RunStateError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "RUN_STATE_ERROR", "message": str(exc), "details": {}},
        ) from exc
    return RunResponse.model_validate(run)


@router.post("/{project_id}/runs/{run_id}/pause", response_model=RunResponse)
async def pause_run(
    project_id: str,
    run_id: str,
    session: DbSession,
) -> RunResponse:
    try:
        run = await run_service.pause_run(
            session=session,
            run_id=run_id,
            project_id=project_id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except RunStateError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "RUN_STATE_ERROR", "message": str(exc), "details": {}},
        ) from exc
    return RunResponse.model_validate(run)


@router.post("/{project_id}/runs/{run_id}/resume", response_model=RunResumeResponse)
async def resume_run(
    project_id: str,
    run_id: str,
    session: DbSession,
) -> RunResumeResponse:
    try:
        return await run_service.resume_run(
            session=session,
            run_id=run_id,
            project_id=project_id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except RunStateError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "RUN_STATE_ERROR", "message": str(exc), "details": {}},
        ) from exc
    except NoCheckpointError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_CHECKPOINT", "message": str(exc), "details": {}},
        ) from exc


@router.get("/{project_id}/runs/{run_id}/stages", response_model=list[RunStageResponse])
async def get_run_stages(
    project_id: str,
    run_id: str,
    session: DbSession,
) -> list[RunStageResponse]:
    try:
        await run_service.get_run(session=session, run_id=run_id, project_id=project_id)
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    return await run_service.get_run_stages(session=session, run_id=run_id)


@router.get("/{project_id}/runs/{run_id}/metrics", response_model=list[MetricPointResponse])
async def get_run_metrics(
    project_id: str,
    run_id: str,
    session: DbSession,
    metric_name: str | None = Query(default=None),
    step_min: int | None = Query(default=None),
    step_max: int | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> list[MetricPointResponse]:
    try:
        await run_service.get_run(session=session, run_id=run_id, project_id=project_id)
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    metric_points = await run_service.get_run_metrics(
        session=session,
        run_id=run_id,
        metric_name=metric_name,
        step_min=step_min,
        step_max=step_max,
        limit=limit,
    )
    return [MetricPointResponse.model_validate(mp) for mp in metric_points]


@router.get("/{project_id}/runs/{run_id}/logs", response_model=RunLogsResponse)
async def get_run_logs(
    project_id: str,
    run_id: str,
    session: DbSession,
    severity: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> RunLogsResponse:
    try:
        project = await get_project(session=session, project_id=project_id)
        await run_service.get_run(session=session, run_id=run_id, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    return run_service.get_run_logs(
        run_id=run_id,
        project_directory=project.directory_path,
        severity=severity,
        stage=stage,
        limit=limit,
        offset=offset,
    )
