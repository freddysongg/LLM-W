from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, get_db_session
from app.models.eval_call import EvalCall
from app.models.eval_case import EvalCase
from app.models.eval_run import EvalRun
from app.schemas.eval import (
    EvalCallRow,
    EvalCallsPageResponse,
    EvalCaseRow,
    EvalRunCreate,
    EvalRunDetailResponse,
    EvalRunListResponse,
    EvalRunSummary,
    EvaluationCasePayload,
)
from app.services.eval_runner import (
    RubricVersionNotFoundError,
    create_eval_run_row,
    schedule_eval_run,
)

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _eval_run_summary(*, eval_run: EvalRun) -> EvalRunSummary:
    return EvalRunSummary.model_validate(eval_run)


def _parse_per_criterion(*, blob: str | None) -> dict[str, bool] | None:
    if blob is None:
        return None
    parsed = json.loads(blob)
    if not isinstance(parsed, dict):
        return None
    return {str(k): bool(v) for k, v in parsed.items()}


def _parse_case_input(*, blob: str) -> EvaluationCasePayload:
    parsed = json.loads(blob)
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=500,
            detail={
                "code": "EVAL_CASE_CORRUPT",
                "message": "case_input blob is not a JSON object",
                "details": {},
            },
        )
    return EvaluationCasePayload.model_validate(parsed)


def _eval_call_row(*, call: EvalCall) -> EvalCallRow:
    return EvalCallRow(
        id=call.id,
        eval_run_id=call.eval_run_id,
        case_id=call.case_id,
        rubric_version_id=call.rubric_version_id,
        judge_model=call.judge_model,
        tier=call.tier,
        verdict=call.verdict,
        reasoning=call.reasoning,
        per_criterion=_parse_per_criterion(blob=call.per_criterion),
        response_hash=call.response_hash,
        cost_usd=call.cost_usd,
        latency_ms=call.latency_ms,
        replayed_from_id=call.replayed_from_id,
        created_at=call.created_at,
    )


def _eval_case_row(*, case: EvalCase) -> EvalCaseRow:
    return EvalCaseRow(
        id=case.id,
        eval_run_id=case.eval_run_id,
        case_input=_parse_case_input(blob=case.case_input),
        input_hash=case.input_hash,
    )


@router.post("/runs", response_model=EvalRunSummary, status_code=201)
async def create_eval_run(payload: EvalRunCreate, session: DbSession) -> EvalRunSummary:
    try:
        eval_run = await create_eval_run_row(
            session=session,
            training_run_id=payload.training_run_id,
            max_cost_usd=payload.max_cost_usd,
        )
    except RubricVersionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RUBRIC_VERSION_NOT_FOUND",
                "message": str(exc),
                "details": {},
            },
        ) from exc
    schedule_eval_run(
        session_factory=async_session_factory,
        project_id=payload.project_id,
        eval_run_id=eval_run.id,
        rubric_version_ids=list(payload.rubric_version_ids),
        max_cost_usd=payload.max_cost_usd,
    )
    return _eval_run_summary(eval_run=eval_run)


@router.get("/runs", response_model=EvalRunListResponse)
async def list_eval_runs(
    session: DbSession,
    training_run_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EvalRunListResponse:
    count_stmt = select(func.count(EvalRun.id))
    query_stmt = select(EvalRun)
    if training_run_id is not None:
        count_stmt = count_stmt.where(EvalRun.training_run_id == training_run_id)
        query_stmt = query_stmt.where(EvalRun.training_run_id == training_run_id)
    total_result = await session.execute(count_stmt)
    total = int(total_result.scalar_one() or 0)
    rows_result = await session.execute(
        query_stmt.order_by(EvalRun.started_at.desc()).limit(limit).offset(offset)
    )
    rows = rows_result.scalars().all()
    return EvalRunListResponse(
        items=[_eval_run_summary(eval_run=row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{eval_run_id}", response_model=EvalRunDetailResponse)
async def get_eval_run(eval_run_id: str, session: DbSession) -> EvalRunDetailResponse:
    eval_run = await session.get(EvalRun, eval_run_id)
    if eval_run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "EVAL_RUN_NOT_FOUND",
                "message": f"eval_run not found: {eval_run_id}",
                "details": {},
            },
        )
    cases_result = await session.execute(
        select(EvalCase).where(EvalCase.eval_run_id == eval_run_id)
    )
    cases = cases_result.scalars().all()
    calls_result = await session.execute(
        select(EvalCall).where(EvalCall.eval_run_id == eval_run_id).order_by(EvalCall.created_at)
    )
    calls = calls_result.scalars().all()
    return EvalRunDetailResponse(
        run=_eval_run_summary(eval_run=eval_run),
        cases=[_eval_case_row(case=case) for case in cases],
        calls=[_eval_call_row(call=call) for call in calls],
    )


@router.get("/runs/{eval_run_id}/calls", response_model=EvalCallsPageResponse)
async def list_eval_run_calls(
    eval_run_id: str,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> EvalCallsPageResponse:
    eval_run = await session.get(EvalRun, eval_run_id)
    if eval_run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "EVAL_RUN_NOT_FOUND",
                "message": f"eval_run not found: {eval_run_id}",
                "details": {},
            },
        )
    count_result = await session.execute(
        select(func.count(EvalCall.id)).where(EvalCall.eval_run_id == eval_run_id)
    )
    total = int(count_result.scalar_one() or 0)
    rows_result = await session.execute(
        select(EvalCall)
        .where(EvalCall.eval_run_id == eval_run_id)
        .order_by(EvalCall.created_at)
        .limit(limit)
        .offset(offset)
    )
    rows = rows_result.scalars().all()
    return EvalCallsPageResponse(
        items=[_eval_call_row(call=row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
