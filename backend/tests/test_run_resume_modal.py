from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.config_version import ConfigVersion
from app.models.project import Project
from app.models.run import Run

_NOW = "2026-05-20T12:00:00+00:00"


def _yaml_blob(*, environment: str) -> str:
    return yaml.safe_dump(
        {
            "execution": {
                "environment": environment,
                "device": "cuda" if environment == "modal" else "cpu",
                "modal_gpu_type": "a10",
                "data_policy": "sanitized_cloud" if environment == "modal" else "local_raw",
            }
        }
    )


@pytest.fixture
async def db_engine_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    db_path = tmp_path / "workbench.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
async def client(
    db_engine_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with db_engine_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _seed_paused_run(
    *,
    factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    environment: str,
) -> None:
    project_dir = tmp_path / "p1"
    (project_dir / "runs" / "r1" / "checkpoints").mkdir(parents=True, exist_ok=True)
    checkpoint_dir = project_dir / "runs" / "r1" / "checkpoints" / "checkpoint-500"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    async with factory() as session:
        session.add(
            Project(
                id="p1",
                name="p1",
                directory_path=str(project_dir),
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        session.add(
            ConfigVersion(
                id="cv-modal",
                project_id="p1",
                version_number=1,
                yaml_blob=_yaml_blob(environment=environment),
                yaml_hash="hash",
                source_tag="user",
                created_at=_NOW,
            )
        )
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv-modal",
                status="completed",
                last_checkpoint_path=str(checkpoint_dir),
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        await session.commit()


async def test_resume_modal_trained_run_returns_422(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed_paused_run(
        factory=db_engine_factory, tmp_path=tmp_path, environment="modal"
    )

    response = await client.post("/api/v1/projects/p1/runs/r1/resume")
    body = response.json()
    assert response.status_code == 422, body
    assert body["error"]["code"] == "MODAL_RESUME_UNSUPPORTED"
    assert body["error"]["details"]["run_id"] == "r1"


async def test_resume_local_trained_run_proceeds(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed_paused_run(
        factory=db_engine_factory, tmp_path=tmp_path, environment="local"
    )

    response = await client.post("/api/v1/projects/p1/runs/r1/resume")
    body = response.json()
    assert response.status_code == 200, body
    assert body["parent_run_id"] == "r1"
    assert body["resume_from_step"] == 500
    assert body["status"] == "pending"
