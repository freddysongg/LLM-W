from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


async def test_list_projects_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_project(client: AsyncClient, tmp_path, monkeypatch) -> None:
    from app.core import config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    response = await client.post(
        "/api/v1/projects",
        json={"name": "test-project", "description": "A test project"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "test-project"
    assert body["description"] == "A test project"
    assert "id" in body
    assert "active_config_version_id" in body
    assert body["active_config_version_id"] is not None


async def test_create_project_name_conflict(client: AsyncClient, tmp_path, monkeypatch) -> None:
    from app.core import config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    await client.post("/api/v1/projects", json={"name": "dupe-project"})
    response = await client.post("/api/v1/projects", json={"name": "dupe-project"})
    assert response.status_code == 409


async def test_get_project(client: AsyncClient, tmp_path, monkeypatch) -> None:
    from app.core import config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    create_resp = await client.post(
        "/api/v1/projects", json={"name": "get-test"}
    )
    project_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["id"] == project_id


async def test_get_project_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects/nonexistent-id")
    assert response.status_code == 404


async def test_update_project(client: AsyncClient, tmp_path, monkeypatch) -> None:
    from app.core import config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    create_resp = await client.post(
        "/api/v1/projects", json={"name": "update-test", "description": "original"}
    )
    project_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"description": "updated description"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "updated description"


async def test_delete_project(client: AsyncClient, tmp_path, monkeypatch) -> None:
    from app.core import config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    create_resp = await client.post(
        "/api/v1/projects", json={"name": "delete-test"}
    )
    project_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/projects/{project_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/projects/{project_id}")
    assert get_resp.status_code == 404


async def test_get_project_storage(client: AsyncClient, tmp_path, monkeypatch) -> None:
    from app.core import config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    create_resp = await client.post(
        "/api/v1/projects", json={"name": "storage-test"}
    )
    project_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/projects/{project_id}/storage")
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert "total_bytes" in body
    assert "breakdown" in body
    assert "per_run" in body
    assert "retention_policy" in body
