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


def test_downsample_returns_original_when_smaller() -> None:
    from app.services.metrics_service import downsample_to_n

    result = downsample_to_n(points=[1.0, 2.0, 3.0], n=40)
    assert result == [1.0, 2.0, 3.0]


def test_downsample_averages_buckets_when_larger() -> None:
    from app.services.metrics_service import downsample_to_n

    result = downsample_to_n(points=[float(i) for i in range(100)], n=10)
    assert len(result) == 10
    assert result[0] < result[-1]


def test_downsample_zero_n_returns_empty() -> None:
    from app.services.metrics_service import downsample_to_n

    assert downsample_to_n(points=[1.0], n=0) == []


@pytest.fixture
async def test_engine():
    with tempfile.TemporaryDirectory(prefix="run-summary-test-") as tmp_dir:
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


async def test_run_summary_batch_returns_per_run_entries(
    client: AsyncClient, db_session
) -> None:
    project = (
        await client.post("/api/v1/projects", json={"name": "s", "description": ""})
    ).json()
    run_a = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "a"},
        )
    ).json()
    run_b = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "b"},
        )
    ).json()

    for run, loss in ((run_a, 0.5), (run_b, 0.3)):
        for step in range(0, 100, 10):
            db_session.add(
                MetricPoint(
                    id=str(uuid.uuid4()),
                    run_id=run["id"],
                    step=step,
                    epoch=0.0,
                    metric_name="train_loss",
                    metric_value=loss,
                    stage_name=None,
                    recorded_at=datetime.now(UTC).isoformat(),
                )
            )
    await db_session.commit()

    ids = f"{run_a['id']},{run_b['id']}"
    resp = await client.get(
        f"/api/v1/projects/{project['id']}/runs/summary?ids={ids}"
    )
    assert resp.status_code == 200
    body = resp.json()
    run_ids = {r["run_id"] for r in body["runs"]}
    assert run_ids == {run_a["id"], run_b["id"]}
    for entry in body["runs"]:
        assert "final_train_loss" in entry
        assert "train_loss_sparkline" in entry
        assert len(entry["train_loss_sparkline"]) <= 40
