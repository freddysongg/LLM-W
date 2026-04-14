from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
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


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(_TRIGGER_NO_UPDATE))
        await conn.execute(text(_TRIGGER_NO_DELETE))

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        yield session

    await engine.dispose()


async def _seed_call(session: AsyncSession) -> EvalCall:
    rubric = Rubric(
        id="rubric-1",
        name="faithfulness",
        description="measures faithfulness",
        research_basis=None,
        created_at="2026-04-14T00:00:00Z",
    )
    rubric_version = RubricVersion(
        id="rv-1",
        rubric_id="rubric-1",
        version_number=1,
        yaml_blob="name: faithfulness\n",
        content_hash="a" * 64,
        diff_from_prev=None,
        calibration_metrics=None,
        calibration_status="uncalibrated",
        judge_model_pin="gpt-4o-mini-2024-07-18",
        created_at="2026-04-14T00:00:00Z",
    )
    eval_run = EvalRun(
        id="er-1",
        training_run_id=None,
        started_at="2026-04-14T00:00:00Z",
        completed_at=None,
        status="running",
        pass_rate=None,
        total_cost_usd=0.0,
        max_cost_usd=None,
    )
    eval_case = EvalCase(
        id="ec-1",
        eval_run_id="er-1",
        case_input='{"prompt":"hi","output":"hello"}',
        input_hash="b" * 64,
    )
    eval_call = EvalCall(
        id="call-1",
        eval_run_id="er-1",
        case_id="ec-1",
        rubric_version_id="rv-1",
        judge_model="gpt-4o-mini-2024-07-18",
        tier="tier1",
        verdict="pass",
        reasoning="the output is faithful to the reference",
        per_criterion=None,
        response_hash="c" * 64,
        cost_usd=0.001,
        latency_ms=120,
        replayed_from_id=None,
        created_at="2026-04-14T00:00:00Z",
    )
    session.add_all([rubric, rubric_version, eval_run, eval_case, eval_call])
    await session.commit()
    return eval_call


async def test_eval_call_insert_succeeds(db_session: AsyncSession) -> None:
    eval_call = await _seed_call(db_session)
    assert eval_call.id == "call-1"


async def test_eval_call_update_is_blocked(db_session: AsyncSession) -> None:
    await _seed_call(db_session)
    with pytest.raises(IntegrityError, match="eval_calls is append-only"):
        await db_session.execute(
            text("UPDATE eval_calls SET reasoning = 'tampered' WHERE id = :id"),
            {"id": "call-1"},
        )
        await db_session.commit()


async def test_eval_call_delete_is_blocked(db_session: AsyncSession) -> None:
    await _seed_call(db_session)
    with pytest.raises(IntegrityError, match="eval_calls is append-only"):
        await db_session.execute(
            text("DELETE FROM eval_calls WHERE id = :id"),
            {"id": "call-1"},
        )
        await db_session.commit()


async def test_rubric_roundtrip(db_session: AsyncSession) -> None:
    rubric = Rubric(
        id="rubric-roundtrip",
        name="instruction_following",
        description="measures instruction following",
        research_basis='["R1", "R3"]',
        created_at="2026-04-14T00:00:00Z",
    )
    db_session.add(rubric)
    await db_session.commit()

    fetched = await db_session.get(Rubric, "rubric-roundtrip")
    assert fetched is not None
    assert fetched.name == "instruction_following"
    assert fetched.research_basis == '["R1", "R3"]'
