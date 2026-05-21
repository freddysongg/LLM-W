from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.project import Project
from app.models.run import Run


@pytest.fixture
async def db_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[async_sessionmaker[Any]]:
    db_path = tmp_path / "workbench.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session() -> AsyncIterator[Any]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.fixture
async def client(db_session: async_sessionmaker[Any]) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _seed_projects_and_runs(
    *,
    factory: async_sessionmaker[Any],
    project_count: int,
    runs_per_project: int,
) -> None:
    """Seed N projects each with M runs at successive timestamps.

    Run IDs encode `pX-rY-T{ts}` for predictable cross-project ordering.
    """
    async with factory() as session:
        global_index = 0
        for project_index in range(project_count):
            project_id = f"p{project_index}"
            session.add(
                Project(
                    id=project_id,
                    name=f"project-{project_index}",
                    directory_path=f"/tmp/{project_id}",
                    created_at="2026-05-19T00:00:00+00:00",
                    updated_at="2026-05-19T00:00:00+00:00",
                )
            )
            for run_index in range(runs_per_project):
                created_at = f"2026-05-19T12:{global_index:02d}:00+00:00"
                session.add(
                    Run(
                        id=f"{project_id}-r{run_index}",
                        project_id=project_id,
                        config_version_id=f"cv-{project_id}-{run_index}",
                        status="completed" if run_index % 2 == 0 else "running",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                global_index += 1
        await session.commit()


async def test_list_runs_global_returns_empty_when_no_runs(client: AsyncClient) -> None:
    response = await client.get("/api/v1/runs")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 10
    assert body["offset"] == 0


async def test_list_runs_global_returns_runs_across_projects_sorted_by_created_at_desc(
    client: AsyncClient, db_session: async_sessionmaker[Any]
) -> None:
    """The endpoint must return runs from every project, newest first."""
    await _seed_projects_and_runs(factory=db_session, project_count=2, runs_per_project=3)

    response = await client.get("/api/v1/runs")
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert len(ids) == 6
    # Last seed iteration had the highest timestamp; reverse-chrono means it's first.
    assert ids[0] == "p1-r2"
    assert ids[-1] == "p0-r0"
    project_ids = {item["project_id"] for item in body["items"]}
    assert project_ids == {"p0", "p1"}


async def test_list_runs_global_respects_limit_query_param(
    client: AsyncClient, db_session: async_sessionmaker[Any]
) -> None:
    await _seed_projects_and_runs(factory=db_session, project_count=2, runs_per_project=10)
    response = await client.get("/api/v1/runs?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 5
    assert body["limit"] == 5


async def test_list_runs_global_clamps_out_of_range_limit(
    client: AsyncClient, db_session: async_sessionmaker[Any]
) -> None:
    """limit must be clamped to [1, 100]; 0 → 1, 9999 → 100."""
    await _seed_projects_and_runs(factory=db_session, project_count=2, runs_per_project=60)

    low = await client.get("/api/v1/runs?limit=0")
    assert low.status_code == 200
    assert low.json()["limit"] == 1
    assert len(low.json()["items"]) == 1

    high = await client.get("/api/v1/runs?limit=9999")
    assert high.status_code == 200
    assert high.json()["limit"] == 100
    assert len(high.json()["items"]) == 100
