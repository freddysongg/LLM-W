from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.project import Project
from app.schemas.ai_rule_settings import RULE_NAMES, AIRuleConfig, AIRuleSettings
from app.services import ai_rule_settings_service
from app.services.rule_engine import evaluate_rules

_NOW = "2026-05-20T12:00:00+00:00"


@pytest.fixture
async def db_engine_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    db_path = tmp_path / "workbench.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
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


async def _seed_project(
    *, factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> Path:
    project_dir = tmp_path / "p1"
    project_dir.mkdir(parents=True, exist_ok=True)
    async with factory() as session:
        session.add(
            Project(
                id="p1",
                name="p1",
                directory_path=str(project_dir),
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        await session.commit()
    return project_dir


async def test_get_returns_defaults_when_no_settings_file_exists(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed_project(factory=db_engine_factory, tmp_path=tmp_path)
    response = await client.get("/api/v1/projects/p1/ai-rule-settings")
    body = response.json()
    assert response.status_code == 200, body
    for name in RULE_NAMES:
        assert body[name]["enabled"] is True


async def test_put_persists_disabled_rules_to_yaml(
    client: AsyncClient,
    db_engine_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    project_dir = await _seed_project(factory=db_engine_factory, tmp_path=tmp_path)
    payload = {name: {"enabled": True} for name in RULE_NAMES}
    payload["loss_plateau"] = {"enabled": False}
    payload["memory_limit"] = {"enabled": False}

    response = await client.put("/api/v1/projects/p1/ai-rule-settings", json=payload)
    body = response.json()
    assert response.status_code == 200, body
    assert body["loss_plateau"]["enabled"] is False
    assert body["memory_limit"]["enabled"] is False

    settings_file = project_dir / "ai_rule_settings.yaml"
    assert settings_file.exists()

    follow_up = await client.get("/api/v1/projects/p1/ai-rule-settings")
    follow_up_body = follow_up.json()
    assert follow_up_body["loss_plateau"]["enabled"] is False


async def test_get_unknown_project_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects/does-not-exist/ai-rule-settings")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "PROJECT_NOT_FOUND"


def test_disabled_rule_names_helper_lists_only_off_rules() -> None:
    settings = AIRuleSettings(
        **{rule_name: AIRuleConfig(enabled=True) for rule_name in RULE_NAMES}
    )
    settings.loss_spike = AIRuleConfig(enabled=False)
    settings.high_truncation = AIRuleConfig(enabled=False)
    assert ai_rule_settings_service.disabled_rule_names(settings) == {
        "loss_spike",
        "high_truncation",
    }


def test_evaluate_rules_skips_disabled_loss_plateau() -> None:
    metrics = [
        {"metric_name": "eval_loss", "step": i, "value": 1.0} for i in range(1, 6)
    ]
    config = {"training": {"learning_rate": 2e-4}}
    enabled_suggestions = evaluate_rules(metrics=metrics, config=config)
    assert any(
        "training.learning_rate" in s.config_diff for s in enabled_suggestions
    ), "loss_plateau rule should fire when learning rate is in play and loss is flat"

    disabled_suggestions = evaluate_rules(
        metrics=metrics, config=config, disabled_rules={"loss_plateau"}
    )
    assert disabled_suggestions == []
