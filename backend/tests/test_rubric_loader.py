from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.rubric import Rubric as RubricModel
from app.models.rubric_version import RubricVersion
from app.schemas.eval import EvaluationCase
from app.services.eval.rubric_loader import load_rubric_from_yaml


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        yield session

    await engine.dispose()


def _valid_rubric_payload(*, description: str = "measures faithfulness") -> dict:
    case = EvaluationCase(prompt="p", output="o").model_dump()
    example = {"input": case, "verdict": "pass", "reasoning": "matches reference"}
    fail_example = {"input": case, "verdict": "fail", "reasoning": "contradicts reference"}
    return {
        "id": "faithfulness",
        "version": "1.0.0",
        "description": description,
        "scale": "binary",
        "criteria": [
            {"name": "claims_supported", "description": "supported", "points": 2},
            {"name": "no_hallucination", "description": "no hallucination", "points": 3},
        ],
        "few_shot_examples": [
            example,
            example,
            fail_example,
            fail_example,
            example,
        ],
        "judge_model_pin": "gpt-4o-mini-2024-07-18",
        "research_basis": ["R1", "R3"],
    }


def _write_yaml(tmp_path: Path, payload: dict, filename: str = "rubric.yaml") -> Path:
    yaml_path = tmp_path / filename
    yaml_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return yaml_path


async def test_idempotent_load_returns_same_row(db_session: AsyncSession, tmp_path: Path) -> None:
    yaml_path = _write_yaml(tmp_path, _valid_rubric_payload())

    first = await load_rubric_from_yaml(yaml_path=yaml_path, session=db_session)
    second = await load_rubric_from_yaml(yaml_path=yaml_path, session=db_session)

    assert first.id == second.id
    assert first.is_new is True
    assert second.is_new is False
    assert first.version_number == 1
    assert second.version_number == 1

    count_result = await db_session.execute(select(func.count()).select_from(RubricVersion))
    assert count_result.scalar_one() == 1


async def test_modified_yaml_creates_second_version(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    first_path = _write_yaml(tmp_path, _valid_rubric_payload(description="a"), filename="v1.yaml")
    first = await load_rubric_from_yaml(yaml_path=first_path, session=db_session)
    assert first.version_number == 1
    assert first.diff_from_prev is None

    second_path = _write_yaml(tmp_path, _valid_rubric_payload(description="b"), filename="v2.yaml")
    second = await load_rubric_from_yaml(yaml_path=second_path, session=db_session)

    assert second.version_number == 2
    assert second.is_new is True
    assert second.diff_from_prev is not None
    assert "b" in second.diff_from_prev or "values_changed" in second.diff_from_prev

    count_result = await db_session.execute(select(func.count()).select_from(RubricVersion))
    assert count_result.scalar_one() == 2


async def test_invalid_yaml_propagates_and_leaves_db_empty(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    payload = _valid_rubric_payload()
    payload["judge_model_pin"] = "gpt-4o-latest"
    yaml_path = _write_yaml(tmp_path, payload)

    with pytest.raises(ValidationError):
        await load_rubric_from_yaml(yaml_path=yaml_path, session=db_session)

    rubric_count = await db_session.execute(select(func.count()).select_from(RubricModel))
    version_count = await db_session.execute(select(func.count()).select_from(RubricVersion))
    assert rubric_count.scalar_one() == 0
    assert version_count.scalar_one() == 0


async def test_two_distinct_rubrics_share_session(db_session: AsyncSession, tmp_path: Path) -> None:
    first_payload = _valid_rubric_payload()
    second_payload = _valid_rubric_payload()
    second_payload["id"] = "instruction_following"

    first_path = _write_yaml(tmp_path, first_payload, filename="a.yaml")
    second_path = _write_yaml(tmp_path, second_payload, filename="b.yaml")

    first = await load_rubric_from_yaml(yaml_path=first_path, session=db_session)
    second = await load_rubric_from_yaml(yaml_path=second_path, session=db_session)

    assert first.rubric_id != second.rubric_id
    assert first.version_number == 1
    assert second.version_number == 1

    rubric_count = await db_session.execute(select(func.count()).select_from(RubricModel))
    assert rubric_count.scalar_one() == 2
