from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.eval_call import EvalCall
from app.models.eval_case import EvalCase
from app.models.eval_run import EvalRun
from app.models.rubric import Rubric
from app.models.rubric_version import RubricVersion

_TRIGGER_NO_UPDATE = """
CREATE TRIGGER eval_calls_no_update
BEFORE UPDATE ON eval_calls
BEGIN
  SELECT RAISE(ABORT, 'eval_calls is append-only');
END
"""

_TRIGGER_NO_DELETE = """
CREATE TRIGGER eval_calls_no_delete
BEFORE DELETE ON eval_calls
BEGIN
  SELECT RAISE(ABORT, 'eval_calls is append-only');
END
"""

_JUDGE_MODEL = "gpt-4o-mini-2024-07-18"
_RUBRIC_ID = "rubric-seed"
_RUBRIC_VERSION_ID = "rv-seed"
_PROJECT_ID = "proj-seed"


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(_TRIGGER_NO_UPDATE))
        await conn.execute(text(_TRIGGER_NO_DELETE))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_rubric(*, session: AsyncSession) -> None:
    rubric = Rubric(
        id=_RUBRIC_ID,
        name="faithfulness-seed",
        description="seeded rubric for route tests",
        research_basis=None,
        created_at="2026-04-14T00:00:00+00:00",
    )
    rubric_version = RubricVersion(
        id=_RUBRIC_VERSION_ID,
        rubric_id=_RUBRIC_ID,
        version_number=1,
        yaml_blob="id: faithfulness\n",
        content_hash="a" * 64,
        diff_from_prev=None,
        calibration_metrics=None,
        calibration_status="uncalibrated",
        judge_model_pin=_JUDGE_MODEL,
        created_at="2026-04-14T00:00:00+00:00",
    )
    session.add_all([rubric, rubric_version])
    await session.commit()


async def _seed_eval_run_with_call(
    *,
    session: AsyncSession,
    eval_run_id: str,
    training_run_id: str | None = None,
) -> None:
    await _seed_rubric(session=session)
    eval_run = EvalRun(
        id=eval_run_id,
        training_run_id=training_run_id,
        started_at="2026-04-14T00:00:00+00:00",
        completed_at="2026-04-14T00:05:00+00:00",
        status="completed",
        pass_rate=1.0,
        total_cost_usd=0.0025,
        max_cost_usd=0.5,
    )
    eval_case = EvalCase(
        id="ec-seed",
        eval_run_id=eval_run_id,
        case_input=json.dumps({"prompt": "hi", "output": "hello", "metadata": {}}, sort_keys=True),
        input_hash="b" * 64,
    )
    eval_call = EvalCall(
        id="call-seed",
        eval_run_id=eval_run_id,
        case_id="ec-seed",
        rubric_version_id=_RUBRIC_VERSION_ID,
        judge_model=_JUDGE_MODEL,
        tier="llm",
        verdict="pass",
        reasoning="seeded reasoning",
        per_criterion=json.dumps({"claims_supported": True}, sort_keys=True),
        response_hash="c" * 64,
        cost_usd=0.0025,
        latency_ms=120,
        replayed_from_id=None,
        created_at="2026-04-14T00:01:00+00:00",
    )
    session.add_all([eval_run, eval_case, eval_call])
    await session.commit()


async def test_list_rubrics_returns_seeded_rubric(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_rubric(session=db_session)
    http_response = await client.get("/api/v1/rubrics")
    assert http_response.status_code == 200
    body = http_response.json()
    assert len(body) == 1
    entry = body[0]
    assert entry["id"] == _RUBRIC_ID
    assert entry["versions"][0]["id"] == _RUBRIC_VERSION_ID
    assert entry["versions"][0]["calibration_status"] == "uncalibrated"


async def test_list_eval_runs_empty(client: AsyncClient) -> None:
    http_response = await client.get("/api/v1/eval/runs")
    assert http_response.status_code == 200
    body = http_response.json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


async def test_list_eval_runs_filters_by_training_run_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_eval_run_with_call(session=db_session, eval_run_id="er-tr", training_run_id=None)
    http_response = await client.get("/api/v1/eval/runs", params={"training_run_id": "missing"})
    assert http_response.status_code == 200
    assert http_response.json()["total"] == 0

    http_response_all = await client.get("/api/v1/eval/runs")
    assert http_response_all.json()["total"] == 1


async def test_get_eval_run_detail_returns_cases_and_calls(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_eval_run_with_call(session=db_session, eval_run_id="er-detail")
    http_response = await client.get("/api/v1/eval/runs/er-detail")
    assert http_response.status_code == 200
    body = http_response.json()
    assert body["run"]["id"] == "er-detail"
    assert len(body["cases"]) == 1
    assert body["cases"][0]["case_input"]["prompt"] == "hi"
    assert len(body["calls"]) == 1
    assert body["calls"][0]["verdict"] == "pass"
    assert body["calls"][0]["per_criterion"] == {"claims_supported": True}


async def test_get_eval_run_detail_404(client: AsyncClient) -> None:
    http_response = await client.get("/api/v1/eval/runs/does-not-exist")
    assert http_response.status_code == 404


async def test_list_eval_run_calls_paginates(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_eval_run_with_call(session=db_session, eval_run_id="er-calls")
    http_response = await client.get(
        "/api/v1/eval/runs/er-calls/calls",
        params={"limit": 10, "offset": 0},
    )
    assert http_response.status_code == 200
    body = http_response.json()
    assert body["total"] == 1
    assert body["limit"] == 10
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["response_hash"] == "c" * 64


async def test_list_eval_run_calls_404(client: AsyncClient) -> None:
    http_response = await client.get("/api/v1/eval/runs/missing/calls")
    assert http_response.status_code == 404


async def test_create_eval_run_persists_pending_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_rubric(session=db_session)
    http_response = await client.post(
        "/api/v1/eval/runs",
        json={
            "project_id": _PROJECT_ID,
            "training_run_id": None,
            "rubric_version_ids": [_RUBRIC_VERSION_ID],
            "max_cost_usd": 0.1,
        },
    )
    assert http_response.status_code == 201
    body = http_response.json()
    assert body["status"] == "pending"
    assert body["training_run_id"] is None
    assert body["max_cost_usd"] == 0.1


async def test_create_eval_run_rejects_missing_rubrics(client: AsyncClient) -> None:
    http_response = await client.post(
        "/api/v1/eval/runs",
        json={
            "project_id": _PROJECT_ID,
            "training_run_id": None,
            "rubric_version_ids": [],
            "max_cost_usd": None,
        },
    )
    assert http_response.status_code == 422


async def test_create_eval_run_returns_404_for_unknown_rubric_version(
    client: AsyncClient,
) -> None:
    http_response = await client.post(
        "/api/v1/eval/runs",
        json={
            "project_id": _PROJECT_ID,
            "training_run_id": None,
            "rubric_version_ids": ["rv-does-not-exist"],
            "max_cost_usd": None,
        },
    )
    assert http_response.status_code == 404
    body = http_response.json()
    assert body["error"]["code"] == "RUBRIC_VERSION_NOT_FOUND"
    assert body["error"]["details"]["rubric_version_id"] == "rv-does-not-exist"
