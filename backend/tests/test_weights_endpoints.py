from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app


@pytest.fixture
async def _engine_and_factory():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        yield (engine, factory)
        await engine.dispose()


@pytest.fixture
async def db_session(_engine_and_factory):
    _, factory = _engine_and_factory
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_session, _engine_and_factory, tmp_path, monkeypatch):
    _, factory = _engine_and_factory
    from app.core import config as cfg_module
    from app.services import orchestrator as orchestrator_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    monkeypatch.setattr(orchestrator_module, "async_session_factory", factory)

    async def _noop_trainer(*args, **kwargs):
        return None

    monkeypatch.setattr(orchestrator_module, "_run_trainer_subprocess", _noop_trainer)

    async def override_db():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_get_model_profile_404_when_absent(client: AsyncClient) -> None:
    project = (await client.post("/api/v1/projects", json={"name": "mp", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    resp = await client.get(f"/api/v1/projects/{project['id']}/runs/{run['id']}/model-profile")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"


async def test_get_weight_snapshots_empty_for_new_run(client: AsyncClient) -> None:
    project = (await client.post("/api/v1/projects", json={"name": "ws", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    resp = await client.get(f"/api/v1/projects/{project['id']}/runs/{run['id']}/weight-snapshots")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run["id"]
    assert body["snapshots_by_layer"] == {}


async def test_get_weight_snapshots_filtered_by_layer(client: AsyncClient, db_session) -> None:
    from app.models.weight_snapshot import WeightSnapshot

    project = (
        await client.post("/api/v1/projects", json={"name": "wsl", "description": ""})
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    for step in (1, 10, 20):
        db_session.add(
            WeightSnapshot(
                run_id=run["id"],
                step=step,
                layer_name="lin.weight",
                mean=0.0,
                std=0.1,
                norm=1.0,
                min_val=-0.1,
                max_val=0.1,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}/weight-snapshots?layer=lin.weight"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["layer_name"] == "lin.weight"
    assert len(body["points"]) == 3
    assert [p["step"] for p in body["points"]] == [1, 10, 20]
