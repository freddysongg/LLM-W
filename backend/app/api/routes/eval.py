from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, get_db_session
from app.schemas.eval import (
    EvalCallsPageResponse,
    EvalRunCreate,
    EvalRunDetailResponse,
    EvalRunListResponse,
    EvalRunSummary,
)
from app.services.eval_runner import (
    EvalCallCorruptError,
    EvalCaseCorruptError,
    EvalRunNotFoundError,
    RubricVersionNotFoundError,
    create_eval_run_row,
    get_run,
    list_calls,
    list_runs,
    schedule_eval_run,
)

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _rubric_not_found(exc: RubricVersionNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": "RUBRIC_VERSION_NOT_FOUND",
            "message": str(exc),
            "details": {"rubric_version_id": exc.rubric_version_id},
        },
    )


def _eval_run_not_found(exc: EvalRunNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": "EVAL_RUN_NOT_FOUND",
            "message": str(exc),
            "details": {"eval_run_id": exc.eval_run_id},
        },
    )


def _eval_case_corrupt(exc: EvalCaseCorruptError) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "code": "EVAL_CASE_CORRUPT",
            "message": str(exc),
            "details": {"case_id": exc.case_id},
        },
    )


def _eval_call_corrupt(exc: EvalCallCorruptError) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "code": "EVAL_CALL_CORRUPT",
            "message": str(exc),
            "details": {"call_id": exc.call_id, "field": exc.field_name},
        },
    )


@router.post("/runs", response_model=EvalRunSummary, status_code=201)
async def create_eval_run(payload: EvalRunCreate, session: DbSession) -> EvalRunSummary:
    try:
        eval_run = await create_eval_run_row(
            session=session,
            training_run_id=payload.training_run_id,
            max_cost_usd=payload.max_cost_usd,
            rubric_version_ids=list(payload.rubric_version_ids),
        )
    except RubricVersionNotFoundError as exc:
        raise _rubric_not_found(exc) from exc
    schedule_eval_run(
        session_factory=async_session_factory,
        project_id=payload.project_id,
        eval_run_id=eval_run.id,
        rubric_version_ids=list(payload.rubric_version_ids),
        max_cost_usd=payload.max_cost_usd,
    )
    return EvalRunSummary.model_validate(eval_run)


@router.get("/runs", response_model=EvalRunListResponse)
async def list_eval_runs(
    session: DbSession,
    training_run_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EvalRunListResponse:
    return await list_runs(
        session=session, training_run_id=training_run_id, limit=limit, offset=offset
    )


@router.get("/runs/{eval_run_id}", response_model=EvalRunDetailResponse)
async def get_eval_run(eval_run_id: str, session: DbSession) -> EvalRunDetailResponse:
    try:
        return await get_run(session=session, eval_run_id=eval_run_id)
    except EvalRunNotFoundError as exc:
        raise _eval_run_not_found(exc) from exc
    except EvalCaseCorruptError as exc:
        raise _eval_case_corrupt(exc) from exc
    except EvalCallCorruptError as exc:
        raise _eval_call_corrupt(exc) from exc


@router.get("/runs/{eval_run_id}/calls", response_model=EvalCallsPageResponse)
async def list_eval_run_calls(
    eval_run_id: str,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> EvalCallsPageResponse:
    try:
        return await list_calls(
            session=session, eval_run_id=eval_run_id, limit=limit, offset=offset
        )
    except EvalRunNotFoundError as exc:
        raise _eval_run_not_found(exc) from exc
    except EvalCallCorruptError as exc:
        raise _eval_call_corrupt(exc) from exc
