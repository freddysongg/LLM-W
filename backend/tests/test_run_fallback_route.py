from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.config_version import ConfigVersion
from app.models.project import Project
from app.models.run import Run
from app.models.run_attempt import RunAttempt
from app.services import orchestrator, settings_service


@pytest.fixture(autouse=True)
def reset_overrides() -> None:
    settings_service._overrides.clear()
    yield
    settings_service._overrides.clear()


@pytest.fixture
async def db_engine_factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    db_path = tmp_path / "workbench.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(orchestrator, "async_session_factory", factory)
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


def _yaml_blob(*, gpu_type: str = "l40s", max_run_minutes: int = 30) -> str:
    return yaml.safe_dump(
        {
            "execution": {
                "environment": "modal",
                "modal_gpu_type": gpu_type,
                "device": "cuda",
                "data_policy": "sanitized_cloud",
                "max_estimated_cost_usd": 2.0,
                "max_run_minutes": max_run_minutes,
                "modal_oom_fallback": {
                    "chain": ["l40s", "a100-40gb", "a100-80gb"],
                    "strategy": "ask",
                },
            }
        }
    )


async def _seed_pending_run(
    *,
    factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    gpu_type: str = "l40s",
    max_run_minutes: int = 30,
) -> str:
    project_dir = tmp_path / "p1"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "configs").mkdir(exist_ok=True)
    (project_dir / "datasets").mkdir(exist_ok=True)
    (project_dir / "datasets" / "sanitized.jsonl").write_text(
        '{"prompt":"x","response":"y"}\n'
    )

    now = "2026-05-19T12:00:00+00:00"
    async with factory() as session:
        session.add(
            Project(
                id="p1",
                name="p1",
                directory_path=str(project_dir),
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            ConfigVersion(
                id="cv1",
                project_id="p1",
                version_number=1,
                yaml_blob=_yaml_blob(gpu_type=gpu_type, max_run_minutes=max_run_minutes),
                yaml_hash="hash",
                source_tag="user",
                created_at=now,
            )
        )
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="fallback_pending",
                modal_gpu_type=gpu_type,
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RunAttempt(
                id="a0",
                run_id="r1",
                attempt_index=0,
                gpu_type=gpu_type,
                device="cuda",
                started_at=now,
                ended_at=now,
                exit_reason="oom",
                created_at=now,
            )
        )
        await session.commit()
    return "r1"


async def test_post_fallback_accept_valid_gpu_returns_200(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    async def _stub_dispatch(**_: object) -> Any:
        return None

    monkeypatch.setattr(orchestrator, "dispatch_training", _stub_dispatch)

    await _seed_pending_run(factory=db_engine_factory, tmp_path=tmp_path)

    response = await client.post(
        "/api/v1/projects/p1/runs/r1/fallback",
        json={"action": "accept", "gpu_type": "a100-40gb"},
    )
    body = response.json()
    assert response.status_code == 200, body
    assert body["modal_gpu_type"] == "a100-40gb"
    assert body["status"] == "running"


async def test_post_fallback_accept_invalid_gpu_returns_400(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    await _seed_pending_run(factory=db_engine_factory, tmp_path=tmp_path)

    response = await client.post(
        "/api/v1/projects/p1/runs/r1/fallback",
        json={"action": "accept", "gpu_type": "nvidia-3090"},
    )
    body = response.json()
    assert response.status_code == 400, body
    assert body["error"]["code"] == "FALLBACK_REJECTED"


async def test_post_fallback_accept_over_cap_returns_400(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    # max_run_minutes=90 → h100 worst-case ≈ $5.19 → over cap.
    await _seed_pending_run(
        factory=db_engine_factory, tmp_path=tmp_path, max_run_minutes=90
    )

    response = await client.post(
        "/api/v1/projects/p1/runs/r1/fallback",
        json={"action": "accept", "gpu_type": "h100"},
    )
    body = response.json()
    assert response.status_code == 400, body
    assert body["error"]["code"] == "FALLBACK_REJECTED"
    assert "hard cap" in body["error"]["message"]


async def test_post_fallback_cancel_returns_200(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    await _seed_pending_run(factory=db_engine_factory, tmp_path=tmp_path)

    response = await client.post(
        "/api/v1/projects/p1/runs/r1/fallback",
        json={"action": "cancel"},
    )
    body = response.json()
    assert response.status_code == 200, body
    assert body["status"] == "failed"
    assert body["failure_reason"] == "oom_user_cancelled"


async def test_post_fallback_when_not_pending_returns_409(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    project_dir = tmp_path / "p1"
    project_dir.mkdir()
    (project_dir / "datasets").mkdir()
    (project_dir / "datasets" / "sanitized.jsonl").write_text("{}")

    now = "2026-05-19T12:00:00+00:00"
    async with db_engine_factory() as session:
        session.add(
            Project(
                id="p1",
                name="p1",
                directory_path=str(project_dir),
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            ConfigVersion(
                id="cv1",
                project_id="p1",
                version_number=1,
                yaml_blob=_yaml_blob(),
                yaml_hash="hash",
                source_tag="user",
                created_at=now,
            )
        )
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                modal_gpu_type="l40s",
                environment="modal",
                device="cuda",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    response = await client.post(
        "/api/v1/projects/p1/runs/r1/fallback",
        json={"action": "cancel"},
    )
    body = response.json()
    assert response.status_code == 409, body
    assert body["error"]["code"] == "RUN_STATE_ERROR"


async def test_post_fallback_accept_missing_gpu_type_returns_400(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    await _seed_pending_run(factory=db_engine_factory, tmp_path=tmp_path)

    response = await client.post(
        "/api/v1/projects/p1/runs/r1/fallback",
        json={"action": "accept"},
    )
    body = response.json()
    assert response.status_code == 400, body
    assert body["error"]["code"] == "MISSING_GPU_TYPE"
