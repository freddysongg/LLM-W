from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import config as cfg_module
from app.core.database import Base, get_db_session
from app.main import app
from app.models.metric_point import MetricPoint
from app.services import orchestrator as orchestrator_module


@pytest.fixture
async def test_engine():
    with tempfile.TemporaryDirectory(prefix="metric-names-test-") as tmp_dir:
        db_path = Path(tmp_dir) / "workbench.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        try:
            yield engine
        finally:
            await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    async def _noop_trainer(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(orchestrator_module, "_run_trainer_subprocess", _noop_trainer)

    shared_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(orchestrator_module, "async_session_factory", shared_factory)

    async def override_db():
        async with shared_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _make_run(client: AsyncClient) -> tuple[str, str]:
    project = (
        await client.post("/api/v1/projects", json={"name": "m", "description": ""})
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()
    return project["id"], run["id"]


async def test_metric_names_returns_distinct(
    client: AsyncClient, db_session
) -> None:
    project_id, run_id = await _make_run(client)

    for name in ["train_loss", "train_loss", "eval_loss", "custom_metric"]:
        db_session.add(
            MetricPoint(
                id=str(uuid.uuid4()),
                run_id=run_id,
                step=1,
                epoch=0.0,
                metric_name=name,
                metric_value=0.1,
                stage_name=None,
                recorded_at=datetime.now(UTC).isoformat(),
            )
        )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/projects/{project_id}/runs/{run_id}/metrics/names"
    )
    assert resp.status_code == 200
    names = resp.json()["metric_names"]
    assert set(names) == {"train_loss", "eval_loss", "custom_metric"}


async def test_metric_names_empty_for_new_run(client: AsyncClient) -> None:
    project_id, run_id = await _make_run(client)
    resp = await client.get(
        f"/api/v1/projects/{project_id}/runs/{run_id}/metrics/names"
    )
    assert resp.status_code == 200
    assert resp.json()["metric_names"] == []


async def test_metric_names_404_for_missing_run(client: AsyncClient) -> None:
    project = (
        await client.post("/api/v1/projects", json={"name": "x", "description": ""})
    ).json()
    resp = await client.get(
        f"/api/v1/projects/{project['id']}/runs/bogus/metrics/names"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"
