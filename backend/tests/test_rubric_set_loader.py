from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.rubric import Rubric as RubricModel
from app.models.rubric_version import RubricVersion
from app.services.eval.rubric_loader import load_rubric_from_yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUBRICS_DIR = _REPO_ROOT / "rubrics"
_EXPECTED_STEMS = ("faithfulness", "hallucination", "instruction_following", "safety")


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


async def test_seed_rubrics_loads_all_four_into_db(db_session: AsyncSession) -> None:
    yaml_paths = sorted(_RUBRICS_DIR.glob("*.yaml"))
    discovered_stems = tuple(path.stem for path in yaml_paths)
    assert discovered_stems == _EXPECTED_STEMS

    first_pass_records = [
        await load_rubric_from_yaml(yaml_path=path, session=db_session) for path in yaml_paths
    ]
    for record in first_pass_records:
        assert record.is_new is True
        assert record.version_number == 1
        assert record.calibration_status == "uncalibrated"
        assert record.judge_model_pin == "gpt-4o-mini-2024-07-18"

    second_pass_records = [
        await load_rubric_from_yaml(yaml_path=path, session=db_session) for path in yaml_paths
    ]
    for record in second_pass_records:
        assert record.is_new is False
        assert record.version_number == 1

    for first, second in zip(first_pass_records, second_pass_records, strict=True):
        assert first.id == second.id
        assert first.content_hash == second.content_hash

    rubric_count = await db_session.execute(select(func.count()).select_from(RubricModel))
    version_count = await db_session.execute(select(func.count()).select_from(RubricVersion))
    assert rubric_count.scalar_one() == len(_EXPECTED_STEMS)
    assert version_count.scalar_one() == len(_EXPECTED_STEMS)


async def test_seeded_rubric_names_match_yaml_stems(db_session: AsyncSession) -> None:
    yaml_paths = sorted(_RUBRICS_DIR.glob("*.yaml"))
    for path in yaml_paths:
        await load_rubric_from_yaml(yaml_path=path, session=db_session)

    result = await db_session.execute(select(RubricModel.name))
    persisted_names = {row[0] for row in result.all()}
    assert persisted_names == set(_EXPECTED_STEMS)
