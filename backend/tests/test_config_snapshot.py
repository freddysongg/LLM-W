from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import config as cfg_module
from app.core.database import Base, get_db_session
from app.core.exceptions import ConfigValidationError
from app.main import app
from app.models.artifact import Artifact
from app.services import orchestrator as orchestrator_module
from app.services.config_service import (
    compute_config_diff,
    serialize_config_yaml_snapshot,
)

_BASE_YAML = """\
project:
  name: p
  mode: single_user_local
training:
  learning_rate: 0.0002
  batch_size: 4
"""

_CHANGED_YAML = """\
project:
  name: p
  mode: single_user_local
training:
  learning_rate: 0.0003
  batch_size: 4
  epochs: 3
"""


def test_compute_config_diff_reports_changed_and_added() -> None:
    diff = compute_config_diff(old_yaml=_BASE_YAML, new_yaml=_CHANGED_YAML)
    assert diff["changed"]["training.learning_rate"] == {"old": 0.0002, "new": 0.0003}
    assert diff["added"]["training.epochs"] == 3
    assert diff["removed"] == {}


def test_compute_config_diff_handles_identical_yaml() -> None:
    diff = compute_config_diff(old_yaml=_BASE_YAML, new_yaml=_BASE_YAML)
    assert diff == {"changed": {}, "added": {}, "removed": {}}


def test_compute_config_diff_reports_removed_keys() -> None:
    diff = compute_config_diff(old_yaml=_CHANGED_YAML, new_yaml=_BASE_YAML)
    assert diff["removed"]["training.epochs"] == 3
    assert diff["changed"]["training.learning_rate"] == {"old": 0.0003, "new": 0.0002}


def test_compute_config_diff_accepts_empty_input() -> None:
    diff = compute_config_diff(old_yaml="", new_yaml=_BASE_YAML)
    assert "project.name" in diff["added"]
    assert diff["changed"] == {}
    assert diff["removed"] == {}


def test_serialize_config_yaml_snapshot_round_trips() -> None:
    out = serialize_config_yaml_snapshot(raw_yaml=_BASE_YAML)
    assert "project:" in out
    assert "learning_rate: 0.0002" in out


def test_serialize_config_yaml_snapshot_rejects_non_mapping() -> None:
    with pytest.raises(ConfigValidationError):
        serialize_config_yaml_snapshot(raw_yaml="- just\n- a\n- list\n")


def test_serialize_config_yaml_snapshot_wraps_yaml_parse_errors() -> None:
    with pytest.raises(ConfigValidationError):
        serialize_config_yaml_snapshot(raw_yaml=": :: : bad")


@pytest.fixture
async def test_engine():
    # Shared file-backed SQLite so the request-scoped session and the helper's
    # internally-opened session both observe the same schema and data.
    with tempfile.TemporaryDirectory(prefix="snapshot-test-") as tmp_dir:
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
async def client(test_engine, db_session, tmp_path, monkeypatch):
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


async def test_create_run_writes_config_snapshot_artifact(
    client: AsyncClient,
    db_session,
) -> None:
    project_response = await client.post(
        "/api/v1/projects", json={"name": "snap", "description": ""}
    )
    project = project_response.json()
    run_response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"config_version_id": project["active_config_version_id"], "name": "r"},
    )
    run = run_response.json()

    rows = (
        (
            await db_session.execute(
                select(Artifact).where(
                    Artifact.run_id == run["id"],
                    Artifact.artifact_type == "config_snapshot",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    snapshot_path = Path(rows[0].file_path)
    assert snapshot_path.exists()
    assert snapshot_path.parent.name == run["id"]
    assert snapshot_path.parent.parent.name == "runs"
    assert snapshot_path.parent.parent.parent == Path(project["directory_path"])
    assert rows[0].is_retained == 1


async def test_get_config_snapshot_returns_yaml_and_diff(client: AsyncClient) -> None:
    project = (
        await client.post(
            "/api/v1/projects", json={"name": "d", "description": ""}
        )
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={
                "config_version_id": project["active_config_version_id"],
                "name": "r",
            },
        )
    ).json()

    resp = await client.get(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}/config-snapshot"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run["id"]
    assert body["parent_config_version_id"] == project["active_config_version_id"]
    assert "project:" in body["yaml"]
    assert "changed" in body["diff"]
    assert "added" in body["diff"]
    assert "removed" in body["diff"]


async def test_get_config_snapshot_404_for_missing_run(client: AsyncClient) -> None:
    project = (
        await client.post(
            "/api/v1/projects", json={"name": "n", "description": ""}
        )
    ).json()
    resp = await client.get(
        f"/api/v1/projects/{project['id']}/runs/bogus/config-snapshot"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"
