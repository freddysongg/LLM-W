from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app

_TRAINER_DEPS_MISSING = (
    importlib.util.find_spec("transformers") is None
    or importlib.util.find_spec("torch") is None
)


@pytest.mark.skipif(_TRAINER_DEPS_MISSING, reason="transformers/torch not installed")
def test_emit_model_profile_walks_named_parameters(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import torch.nn as nn

    from app.services import trainer

    model = nn.Sequential(
        nn.Linear(10, 20),
        nn.Linear(20, 5),
    )

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_model_profile(model=model)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    profile = next(e for e in events if e["type"] == "model_profile")
    assert profile["total_params"] > 0
    assert profile["trainable_params"] > 0
    assert len(profile["layers"]) >= 2
    first_layer = profile["layers"][0]
    assert "name" in first_layer
    assert "shape" in first_layer
    assert "param_count" in first_layer
    assert first_layer["trainable"] in (True, False)
    assert first_layer["dtype"]


@pytest.mark.skipif(_TRAINER_DEPS_MISSING, reason="transformers/torch not installed")
def test_emit_model_profile_captures_frozen_layers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import torch.nn as nn

    from app.services import trainer

    model = nn.Linear(10, 5)
    for p in model.parameters():
        p.requires_grad = False

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_model_profile(model=model)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    profile = next(e for e in events if e["type"] == "model_profile")
    assert profile["trainable_params"] == 0
    assert all(layer["trainable"] is False for layer in profile["layers"])


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


async def test_model_profile_event_persists_layers_json(
    client: AsyncClient, db_session
) -> None:
    from sqlalchemy import select

    from app.models.model_profile import ModelProfile
    from app.services import orchestrator

    project = (
        await client.post("/api/v1/projects", json={"name": "mp", "description": ""})
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    await orchestrator._process_trainer_event(
        event={
            "type": "model_profile",
            "total_params": 100,
            "trainable_params": 50,
            "layers": [
                {
                    "name": "lin.weight",
                    "shape": [5, 10],
                    "param_count": 50,
                    "trainable": True,
                    "dtype": "float32",
                },
            ],
        },
        run_id=run["id"],
        project_id=project["id"],
        stage_start_times={},
        final_metrics={},
    )

    rows = (
        await db_session.execute(
            select(ModelProfile).where(ModelProfile.project_id == project["id"])
        )
    ).scalars().all()
    assert len(rows) >= 1
    assert rows[0].layers_json is not None
