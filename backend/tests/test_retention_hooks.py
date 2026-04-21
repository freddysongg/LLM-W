from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app


@pytest.fixture
async def _test_engine_and_factory():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        yield (engine, factory)
        await engine.dispose()


@pytest.fixture
async def db_session(_test_engine_and_factory):
    _, factory = _test_engine_and_factory
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_session, _test_engine_and_factory, tmp_path, monkeypatch):
    _, factory = _test_engine_and_factory
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


async def test_apply_retention_after_checkpoint_keeps_last_n(
    client: AsyncClient,
    db_session,
    tmp_path: Path,
) -> None:
    from sqlalchemy import select

    from app.models.artifact import Artifact
    from app.services.storage_manager import apply_retention_after_checkpoint

    project = (
        await client.post("/api/v1/projects", json={"name": "ret", "description": ""})
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    project_dir = tmp_path / project["id"]
    for step in (10, 20, 30, 40, 50):
        ckpt_path = project_dir / "runs" / run["id"] / f"checkpoint-{step}"
        ckpt_path.mkdir(parents=True, exist_ok=True)
        (ckpt_path / "marker.txt").write_text("x")
        db_session.add(
            Artifact(
                id=str(uuid.uuid4()),
                run_id=run["id"],
                project_id=project["id"],
                artifact_type="checkpoint",
                file_path=str(ckpt_path),
                file_size_bytes=10,
                is_retained=1,
                is_best=0,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    await db_session.commit()

    result = await apply_retention_after_checkpoint(
        session=db_session,
        run_id=run["id"],
    )

    rows = (
        (
            await db_session.execute(
                select(Artifact).where(
                    Artifact.run_id == run["id"],
                    Artifact.artifact_type == "checkpoint",
                )
            )
        )
        .scalars()
        .all()
    )
    retained = [r for r in rows if r.is_retained == 1]
    assert len(retained) == 3
    assert "kept" in result
    assert "pruned" in result


def test_trainer_best_eval_tracker_prefers_lower_loss() -> None:
    from app.services import trainer

    tracker = trainer._BestEvalTracker()
    assert tracker.update(step=10, eval_loss=0.9) is True
    assert tracker.update(step=20, eval_loss=1.0) is False
    assert tracker.update(step=30, eval_loss=0.5) is True
    assert tracker.best_step == 30
    assert tracker.best_loss == 0.5


def test_emit_checkpoint_with_is_best_eval_flag(capsys) -> None:
    import json
    from unittest.mock import patch

    from app.services import trainer

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_checkpoint(
            step=30,
            path="/tmp/ckpt",
            size_bytes=1024,
            is_best_eval=True,
        )

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    ckpt = next(e for e in events if e["type"] == "checkpoint")
    assert ckpt["is_best_eval"] is True


def test_emit_checkpoint_defaults_is_best_eval_false(capsys) -> None:
    import json
    from unittest.mock import patch

    from app.services import trainer

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_checkpoint(step=30, path="/tmp/ckpt", size_bytes=1024)

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    ckpt = next(e for e in events if e["type"] == "checkpoint")
    assert ckpt.get("is_best_eval", False) is False
