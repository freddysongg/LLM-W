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
def test_emit_weight_stats_computes_per_layer_stats(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import torch.nn as nn

    from app.services import trainer

    model = nn.Linear(10, 5)

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_weight_stats(model=model, step=100)

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    event = next(e for e in events if e["type"] == "weight_stats")
    assert event["step"] == 100
    assert len(event["stats"]) >= 1
    first_layer_name = next(iter(event["stats"]))
    stats = event["stats"][first_layer_name]
    for key in ("mean", "std", "norm", "min", "max"):
        assert key in stats
        assert isinstance(stats[key], (int, float))


@pytest.mark.skipif(_TRAINER_DEPS_MISSING, reason="transformers/torch not installed")
def test_emit_weight_stats_handles_single_element_layer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import torch
    import torch.nn as nn

    from app.services import trainer

    class _SingleParamModule(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.scale = nn.Parameter(torch.tensor([3.14]))

    model = _SingleParamModule()

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_weight_stats(model=model, step=1)

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    event = next(e for e in events if e["type"] == "weight_stats")
    stats = event["stats"]["scale"]
    assert stats["std"] == 0.0


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


async def test_weight_stats_event_persists_rows(
    client: AsyncClient, db_session
) -> None:
    from sqlalchemy import select

    from app.models.weight_snapshot import WeightSnapshot
    from app.services import orchestrator

    project = (
        await client.post("/api/v1/projects", json={"name": "ws", "description": ""})
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    await orchestrator._process_trainer_event(
        event={
            "type": "weight_stats",
            "step": 100,
            "stats": {
                "layer1.weight": {
                    "mean": 0.1,
                    "std": 0.2,
                    "norm": 1.0,
                    "min": -0.3,
                    "max": 0.5,
                },
                "layer2.weight": {
                    "mean": 0.0,
                    "std": 0.1,
                    "norm": 0.5,
                    "min": -0.2,
                    "max": 0.2,
                },
            },
        },
        run_id=run["id"],
        project_id=project["id"],
        stage_start_times={},
        final_metrics={},
    )

    rows = (
        await db_session.execute(
            select(WeightSnapshot).where(WeightSnapshot.run_id == run["id"])
        )
    ).scalars().all()
    assert len(rows) == 2
    assert {r.layer_name for r in rows} == {"layer1.weight", "layer2.weight"}
