from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.config_version import ConfigVersion
from app.models.merged_model import MergedModel
from app.models.project import Project
from app.models.run import Run


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_config_yaml(*, base_model_id: str | None = "Qwen/Qwen2.5-1.5B") -> str:
    payload: dict[str, Any] = {
        "project": {"name": "p", "mode": "single_user_local"},
        "model": {
            "source": "huggingface",
            "family": "causal_lm",
        },
        "dataset": {"source": "huggingface", "dataset_id": "x"},
        "preprocessing": {},
        "training": {},
        "optimization": {},
        "adapters": {},
        "quantization": {},
        "observability": {},
        "ai_assistant": {},
        "execution": {},
        "checkpoint_retention": {},
        "introspection": {},
    }
    if base_model_id is not None:
        payload["model"]["model_id"] = base_model_id
    return yaml.safe_dump(payload)


async def _seed_project(
    session: AsyncSession,
    *,
    tmp_path: Path,
    base_model_id: str | None = "Qwen/Qwen2.5-1.5B",
) -> str:
    import uuid

    project_id = str(uuid.uuid4())
    config_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name=f"proj-{project_id[:6]}",
        directory_path=str(tmp_path),
        active_config_version_id=config_id,
        created_at="2026-05-19T11:00:00+00:00",
        updated_at="2026-05-19T11:00:00+00:00",
    )
    config = ConfigVersion(
        id=config_id,
        project_id=project_id,
        version_number=1,
        yaml_blob=_make_config_yaml(base_model_id=base_model_id),
        yaml_hash="hash",
        source_tag="user",
        created_at="2026-05-19T11:00:00+00:00",
    )
    session.add(project)
    session.add(config)
    await session.commit()
    return project_id


async def _seed_run(
    session: AsyncSession,
    *,
    project_id: str,
    last_checkpoint_path: str | None,
    current_step: int = 100,
) -> str:
    import uuid

    config_result = await session.execute(
        select(ConfigVersion).where(ConfigVersion.project_id == project_id)
    )
    config = config_result.scalar_one()
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id=project_id,
        config_version_id=config.id,
        status="completed",
        current_step=current_step,
        progress_pct=1.0,
        last_checkpoint_path=last_checkpoint_path,
        run_type="training",
        created_at="2026-05-19T11:00:00+00:00",
        updated_at="2026-05-19T11:00:00+00:00",
    )
    session.add(run)
    await session.commit()
    return run_id


def _stub_perform_merge(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Replace _perform_merge with a stub that writes a deterministic file set.

    Returns the list of destination paths the stub wrote to so callers can
    assert on what would have been streamed to disk.
    """
    from app.services import merged_models_service

    written: list[Path] = []

    def _fake_merge(*, base_model_id: str, adapter_path: Path, output_path: Path) -> None:
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "config.json").write_text(
            f'{{"base": "{base_model_id}"}}', encoding="utf-8"
        )
        (output_path / "model.safetensors").write_bytes(b"\x00" * 1024)
        (output_path / "tokenizer.json").write_text("{}", encoding="utf-8")
        written.append(output_path)

    monkeypatch.setattr(merged_models_service, "_perform_merge", _fake_merge)
    return written


async def test_list_returns_empty_for_new_project(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    project_id = await _seed_project(db_session, tmp_path=tmp_path)

    resp = await client.get(f"/api/v1/projects/{project_id}/merged-models")
    body = resp.json()
    assert resp.status_code == 200, body
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_returns_404_for_unknown_project(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/projects/missing/merged-models")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


async def test_create_merges_writes_disk_and_persists_row(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written = _stub_perform_merge(monkeypatch)
    project_id = await _seed_project(db_session, tmp_path=tmp_path)
    checkpoint = tmp_path / "runs" / "r1" / "checkpoint-final"
    checkpoint.mkdir(parents=True)
    run_id = await _seed_run(
        db_session,
        project_id=project_id,
        last_checkpoint_path=str(checkpoint),
        current_step=2800,
    )

    resp = await client.post(
        f"/api/v1/projects/{project_id}/merged-models",
        json={"source_run_id": run_id},
    )
    body = resp.json()
    assert resp.status_code == 201, body
    assert body["project_id"] == project_id
    assert body["base_model_id"] == "Qwen/Qwen2.5-1.5B"
    assert body["source_run_id"] == run_id
    assert body["adapter_step"] == 2800
    assert body["file_size_bytes"] > 0
    assert len(written) == 1
    assert Path(body["file_path"]) == written[0]
    assert written[0].parent == tmp_path / "merged"

    rows = list((await db_session.execute(select(MergedModel))).scalars().all())
    assert len(rows) == 1
    assert rows[0].file_path == body["file_path"]


async def test_create_returns_422_when_run_has_no_checkpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_perform_merge(monkeypatch)
    project_id = await _seed_project(db_session, tmp_path=tmp_path)
    run_id = await _seed_run(
        db_session, project_id=project_id, last_checkpoint_path=None
    )

    resp = await client.post(
        f"/api/v1/projects/{project_id}/merged-models",
        json={"source_run_id": run_id},
    )
    body = resp.json()
    assert resp.status_code == 422, body
    assert body["error"]["code"] == "NO_CHECKPOINT_FOR_MERGE"


async def test_create_returns_422_when_active_config_has_no_model_id(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_perform_merge(monkeypatch)
    project_id = await _seed_project(db_session, tmp_path=tmp_path, base_model_id=None)
    checkpoint = tmp_path / "runs" / "r1" / "checkpoint-final"
    checkpoint.mkdir(parents=True)
    run_id = await _seed_run(
        db_session,
        project_id=project_id,
        last_checkpoint_path=str(checkpoint),
    )

    resp = await client.post(
        f"/api/v1/projects/{project_id}/merged-models",
        json={"source_run_id": run_id},
    )
    body = resp.json()
    assert resp.status_code == 422, body
    assert body["error"]["code"] == "MISSING_BASE_MODEL"


async def test_create_returns_404_for_unknown_run(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_perform_merge(monkeypatch)
    project_id = await _seed_project(db_session, tmp_path=tmp_path)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/merged-models",
        json={"source_run_id": "run-does-not-exist"},
    )
    body = resp.json()
    assert resp.status_code == 404, body
    assert body["error"]["code"] == "RUN_NOT_FOUND"


async def test_create_cleans_up_partial_output_on_merge_failure(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import merged_models_service

    def _raises(*, base_model_id: str, adapter_path: Path, output_path: Path) -> None:
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "partial.bin").write_bytes(b"half-written")
        raise RuntimeError("simulated merge failure")

    monkeypatch.setattr(merged_models_service, "_perform_merge", _raises)
    project_id = await _seed_project(db_session, tmp_path=tmp_path)
    checkpoint = tmp_path / "runs" / "r1" / "checkpoint-final"
    checkpoint.mkdir(parents=True)
    run_id = await _seed_run(
        db_session, project_id=project_id, last_checkpoint_path=str(checkpoint)
    )

    resp = await client.post(
        f"/api/v1/projects/{project_id}/merged-models",
        json={"source_run_id": run_id},
    )
    assert resp.status_code == 500
    merged_root = tmp_path / "merged"
    if merged_root.exists():
        assert list(merged_root.iterdir()) == []


async def test_get_returns_persisted_row(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_perform_merge(monkeypatch)
    project_id = await _seed_project(db_session, tmp_path=tmp_path)
    checkpoint = tmp_path / "runs" / "r1" / "checkpoint-final"
    checkpoint.mkdir(parents=True)
    run_id = await _seed_run(
        db_session, project_id=project_id, last_checkpoint_path=str(checkpoint)
    )

    create_resp = await client.post(
        f"/api/v1/projects/{project_id}/merged-models",
        json={"source_run_id": run_id},
    )
    merged_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/api/v1/projects/{project_id}/merged-models/{merged_id}"
    )
    body = get_resp.json()
    assert get_resp.status_code == 200, body
    assert body["id"] == merged_id


async def test_get_returns_404_for_unknown_merged_id(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    project_id = await _seed_project(db_session, tmp_path=tmp_path)

    resp = await client.get(
        f"/api/v1/projects/{project_id}/merged-models/does-not-exist"
    )
    body = resp.json()
    assert resp.status_code == 404, body
    assert body["error"]["code"] == "MERGED_MODEL_NOT_FOUND"


async def test_delete_removes_row_and_dir(
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_perform_merge(monkeypatch)
    project_id = await _seed_project(db_session, tmp_path=tmp_path)
    checkpoint = tmp_path / "runs" / "r1" / "checkpoint-final"
    checkpoint.mkdir(parents=True)
    run_id = await _seed_run(
        db_session, project_id=project_id, last_checkpoint_path=str(checkpoint)
    )

    create_resp = await client.post(
        f"/api/v1/projects/{project_id}/merged-models",
        json={"source_run_id": run_id},
    )
    merged_id = create_resp.json()["id"]
    merged_dir = Path(create_resp.json()["file_path"])
    assert merged_dir.is_dir()

    delete_resp = await client.delete(
        f"/api/v1/projects/{project_id}/merged-models/{merged_id}"
    )
    assert delete_resp.status_code == 204
    assert not merged_dir.exists()

    rows = list((await db_session.execute(select(MergedModel))).scalars().all())
    assert rows == []


async def test_delete_returns_404_for_unknown_merged_id(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    project_id = await _seed_project(db_session, tmp_path=tmp_path)

    resp = await client.delete(
        f"/api/v1/projects/{project_id}/merged-models/does-not-exist"
    )
    body = resp.json()
    assert resp.status_code == 404, body
    assert body["error"]["code"] == "MERGED_MODEL_NOT_FOUND"


def test_perform_merge_does_not_eagerly_import_peft_or_transformers() -> None:
    """Pins the lazy-import contract on merged_models_service.

    Importing the service must not pull in peft or transformers — both live
    behind the `training` optional extra and aren't installed on base/local
    installs that only want to read merged-model metadata.
    """
    import sys

    import app.services.merged_models_service as ms

    assert "peft" not in ms.__dict__
    assert "transformers" not in ms.__dict__
    assert "peft" not in sys.modules
    assert "transformers" not in sys.modules
