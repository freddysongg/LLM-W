from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.core.modal_catalog import is_valid_modal_gpu_type
from app.main import app
from app.models.run import Run
from app.schemas.workbench_config import ExecutionConfig
from app.services import orchestrator, settings_service
from app.services.training_dispatcher import (
    ModalCredentialsMissingError,
    UnsupportedEnvironmentError,
    dispatch_training,
)


@pytest.fixture(autouse=True)
def reset_settings_overrides() -> None:
    settings_service._overrides.clear()
    yield
    settings_service._overrides.clear()


@pytest.fixture
async def db_session() -> AsyncSession:
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


def test_execution_config_accepts_l40s_and_new_fields() -> None:
    cfg = ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "modal_gpu_type": "l40s",
            "max_run_minutes": 60,
            "max_estimated_cost_usd": 2.5,
            "data_policy": "sanitized_cloud",
        }
    )
    assert cfg.environment == "modal"
    assert cfg.modal_gpu_type == "l40s"
    assert cfg.max_run_minutes == 60
    assert cfg.max_estimated_cost_usd == 2.5
    assert cfg.data_policy == "sanitized_cloud"


def test_execution_config_defaults() -> None:
    cfg = ExecutionConfig.model_validate({})
    # Plan-mandated defaults: A10 GPU, 90-minute wall time, $3 budget, raw-local policy.
    assert cfg.environment == "local"
    assert cfg.modal_gpu_type == "a10"
    assert cfg.max_run_minutes == 90
    assert cfg.max_estimated_cost_usd == 3.0
    assert cfg.data_policy == "local_raw"


def test_execution_config_rejects_unknown_gpu_type() -> None:
    with pytest.raises(ValueError):
        ExecutionConfig.model_validate({"modal_gpu_type": "nvidia-3090"})


def test_modal_gpu_type_validity_helper() -> None:
    assert is_valid_modal_gpu_type("a10") is True
    assert is_valid_modal_gpu_type("l40s") is True
    assert is_valid_modal_gpu_type("h100") is True
    assert is_valid_modal_gpu_type("unknown") is False


def test_modal_catalog_source_has_no_modal_import() -> None:
    """`app.core.modal_catalog` must stay source-clean of the optional `modal` SDK.

    `settings_service.test_modal_connection` validates a candidate GPU type
    before contacting Modal. That validation runs on base installs without the
    `cloud` extra, so the catalog module — which owns the workbench→Modal GPU
    spec map — must not contain `import modal` anywhere or the validation path
    would raise ImportError instead of returning the intended ModalTestResponse.
    """
    import inspect

    import app.core.modal_catalog

    source = inspect.getsource(app.core.modal_catalog)
    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        assert not stripped.startswith("import modal"), stripped
        assert not stripped.startswith("from modal"), stripped


def test_validate_execution_rejects_local_raw_for_modal() -> None:
    cfg = ExecutionConfig.model_validate({"environment": "modal", "data_policy": "local_raw"})
    with pytest.raises(UnsupportedEnvironmentError, match="data_policy"):
        orchestrator._validate_execution_for_run(execution=cfg)


def test_validate_execution_rejects_over_cap_cost() -> None:
    cfg = ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "data_policy": "sanitized_cloud",
            "max_estimated_cost_usd": 99.0,
        }
    )
    with pytest.raises(UnsupportedEnvironmentError, match="hard cap"):
        orchestrator._validate_execution_for_run(execution=cfg)


def test_validate_execution_rejects_worst_case_over_cap_even_when_estimate_under() -> None:
    # The user's claimed budget is $2 (under the $5 cap), but they paired an H100
    # with a 359-minute timeout. Worst-case spend = 359 * 60 * 0.001442 ≈ $31, far
    # over the cap. The validator must reject this combination on the actual
    # ceiling, not the user-claimed estimate.
    settings_service._overrides["modal_token_id"] = "ak-test"
    settings_service._overrides["modal_token_secret"] = "as-test"
    cfg = ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "modal_gpu_type": "h100",
            "data_policy": "sanitized_cloud",
            "max_estimated_cost_usd": 2.0,
            "max_run_minutes": 359,
        }
    )
    with pytest.raises(UnsupportedEnvironmentError, match=r"[Ww]orst-case"):
        orchestrator._validate_execution_for_run(execution=cfg)


def test_validate_execution_allows_modal_when_worst_case_under_cap() -> None:
    # A 30-minute A10 run has worst-case = 30 * 60 * 0.000306 ≈ $0.55, well under
    # the cap, so a reasonable budget must pass.
    settings_service._overrides["modal_token_id"] = "ak-test"
    settings_service._overrides["modal_token_secret"] = "as-test"
    cfg = ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "modal_gpu_type": "a10",
            "data_policy": "sanitized_cloud",
            "max_estimated_cost_usd": 2.0,
            "max_run_minutes": 30,
        }
    )
    orchestrator._validate_execution_for_run(execution=cfg)


def test_require_sanitized_artifact_raises_when_file_missing(tmp_path: Path) -> None:
    project_dir = tmp_path / "p1"
    (project_dir / "datasets").mkdir(parents=True)
    with pytest.raises(UnsupportedEnvironmentError, match="sanitized"):
        orchestrator._require_sanitized_artifact(project_dir=project_dir)


def test_require_sanitized_artifact_passes_when_file_present(tmp_path: Path) -> None:
    project_dir = tmp_path / "p1"
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"prompt":"x","response":"y"}\n')
    orchestrator._require_sanitized_artifact(project_dir=project_dir)


def test_build_modal_upload_plan_raises_without_sanitized_artifact(tmp_path: Path) -> None:
    from app.services.cloud.modal_adapter import (
        SanitizedArtifactMissingError,
        build_modal_upload_plan,
    )

    project_dir = tmp_path / "p1"
    (project_dir / "datasets").mkdir(parents=True)
    config_path = project_dir / "config.yaml"
    config_path.write_text("execution:\n  environment: modal\n")
    with pytest.raises(SanitizedArtifactMissingError):
        build_modal_upload_plan(project_dir=project_dir, config_path=config_path)


def test_build_modal_upload_plan_emits_only_sanitized_file_under_datasets(
    tmp_path: Path,
) -> None:
    """The plan must NOT include any file from the raw datasets/ directory.

    This is the defense-in-depth contract: even if someone bypassed the
    orchestrator's pre-flight check, the adapter still refuses to send the
    raw `datasets/` directory and instead uploads only `sanitized.jsonl`.
    """
    from app.services.cloud.modal_adapter import build_modal_upload_plan

    project_dir = tmp_path / "p1"
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"text":"safe"}\n')
    (datasets_dir / "raw_dump.csv").write_text("name,email\nalice,alice@example.com\n")
    (datasets_dir / "secrets.json").write_text('{"customer_id": "abc"}')
    config_path = project_dir / "config.yaml"
    config_path.write_text("execution:\n  environment: modal\n")

    plan = build_modal_upload_plan(project_dir=project_dir, config_path=config_path)

    uploaded_remote_paths = [remote for _, remote in plan.files]
    assert any("sanitized.jsonl" in path for path in uploaded_remote_paths)
    assert not any("raw_dump.csv" in path for path in uploaded_remote_paths)
    assert not any("secrets.json" in path for path in uploaded_remote_paths)
    # The plan's directory uploads must not include the raw datasets dir.
    for _, remote_dir in plan.directories:
        assert "datasets" not in remote_dir or remote_dir.endswith("configs")


def test_build_modal_upload_plan_includes_manifest_when_present(tmp_path: Path) -> None:
    from app.services.cloud.modal_adapter import build_modal_upload_plan

    project_dir = tmp_path / "p1"
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"text":"x"}\n')
    (datasets_dir / "sanitized.meta.json").write_text('{"content_hash": "abc"}')
    config_path = project_dir / "config.yaml"
    config_path.write_text("execution:\n  environment: modal\n")

    plan = build_modal_upload_plan(project_dir=project_dir, config_path=config_path)

    uploaded_remote_paths = [remote for _, remote in plan.files]
    assert any("sanitized.meta.json" in path for path in uploaded_remote_paths)


def test_build_modal_upload_plan_uploads_rewritten_config_pointing_at_sanitized(
    tmp_path: Path,
) -> None:
    """The uploaded config must replace the host's dataset.source / dataset_id
    with the path of the uploaded sanitized artifact so the remote trainer
    doesn't try to load host paths or bypass sanitized_cloud by fetching HF.

    Uses normalize=false because the trainer-side tokenization stage does not
    yet handle the OpenAI messages shape that normalize=true produces — the
    upload planner refuses that combination explicitly in a separate test.
    """
    import yaml as _yaml

    from app.services.cloud.modal_adapter import build_modal_upload_plan

    project_dir = tmp_path / "p1"
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"prompt":"hi","response":"yo"}\n')
    (datasets_dir / "sanitized.meta.json").write_text(
        '{"content_hash": "abc", "normalized": false}', encoding="utf-8"
    )

    configs_dir = project_dir / "configs"
    configs_dir.mkdir(parents=True)
    config_path = configs_dir / "run-foo.yaml"
    config_path.write_text(
        _yaml.safe_dump(
            {
                "project": {"name": "demo"},
                "dataset": {
                    "source": "huggingface",
                    "dataset_id": "HuggingFaceH4/ultrachat_200k",
                    "format": "sharegpt",
                },
                "execution": {"environment": "modal"},
            }
        ),
        encoding="utf-8",
    )

    plan = build_modal_upload_plan(project_dir=project_dir, config_path=config_path)

    config_entry = next(
        (local, remote)
        for local, remote in plan.files
        if remote.endswith(f"/{config_path.name}")
    )
    uploaded_path, remote_target = config_entry
    # The local source must be the staged rewrite, not the host's raw config.
    assert ".modal-uploads" in str(uploaded_path)
    assert uploaded_path.is_file()
    # The remote target name still matches the trainer's --config-path argument.
    assert remote_target.endswith(f"/{config_path.name}")

    rewritten = _yaml.safe_load(uploaded_path.read_text(encoding="utf-8"))
    assert rewritten["dataset"]["source"] == "local_jsonl"
    assert rewritten["dataset"]["dataset_id"] == "/workspace/datasets/sanitized.jsonl"
    # normalize=false → the original dataset format must be preserved so the
    # trainer reads input_field/target_field against the source schema.
    assert rewritten["dataset"]["format"] == "sharegpt"
    # The user's other config sections must survive the rewrite intact.
    assert rewritten["project"]["name"] == "demo"
    assert rewritten["execution"]["environment"] == "modal"


def test_build_modal_upload_plan_rejects_normalized_artifact(tmp_path: Path) -> None:
    """A normalized sanitized artifact pairs with messages-only rows that the
    trainer's tokenization stage cannot consume. Surfacing the incompatibility
    here fails fast with an actionable message instead of letting the run die
    mid-tokenization on the remote side."""
    import yaml as _yaml

    from app.services.cloud.modal_adapter import (
        NormalizedArtifactUnsupportedError,
        build_modal_upload_plan,
    )

    project_dir = tmp_path / "p1"
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"messages":[]}\n')
    (datasets_dir / "sanitized.meta.json").write_text(
        '{"content_hash": "abc", "normalized": true}', encoding="utf-8"
    )

    configs_dir = project_dir / "configs"
    configs_dir.mkdir(parents=True)
    config_path = configs_dir / "run-foo.yaml"
    config_path.write_text(
        _yaml.safe_dump(
            {
                "dataset": {"source": "huggingface", "dataset_id": "x"},
                "execution": {"environment": "modal"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(NormalizedArtifactUnsupportedError, match="normalize=false"):
        build_modal_upload_plan(project_dir=project_dir, config_path=config_path)


def test_build_modal_upload_plan_does_not_upload_configs_directory(tmp_path: Path) -> None:
    """Uploading the configs/ directory would clobber the rewritten config."""
    import yaml as _yaml

    from app.services.cloud.modal_adapter import build_modal_upload_plan

    project_dir = tmp_path / "p1"
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"messages":[]}\n')

    configs_dir = project_dir / "configs"
    configs_dir.mkdir(parents=True)
    config_path = configs_dir / "run-foo.yaml"
    config_path.write_text(
        _yaml.safe_dump({"dataset": {"source": "local_jsonl", "dataset_id": "/host/x.jsonl"}}),
        encoding="utf-8",
    )
    (configs_dir / "stale.yaml").write_text("ignored: true\n", encoding="utf-8")

    plan = build_modal_upload_plan(project_dir=project_dir, config_path=config_path)

    assert plan.directories == ()


def test_rewrite_config_for_modal_upload_handles_missing_dataset_section(
    tmp_path: Path,
) -> None:
    """A config that lacks a dataset section should still be rewritten without raising."""
    import yaml as _yaml

    from app.services.cloud.modal_adapter import _rewrite_config_for_modal_upload

    src = tmp_path / "src.yaml"
    src.write_text("project:\n  name: demo\n", encoding="utf-8")
    dst = tmp_path / "out" / "src.yaml"

    _rewrite_config_for_modal_upload(src_config_path=src, dst_path=dst)

    rewritten = _yaml.safe_load(dst.read_text(encoding="utf-8"))
    assert rewritten["dataset"]["source"] == "local_jsonl"
    assert rewritten["project"]["name"] == "demo"


def _write_modal_rewrite_fixture(
    *,
    project_dir: Path,
    manifest_payload: str | None,
    original_format: str = "sharegpt",
) -> Path:
    """Helper: set up a project with a sanitized artifact, optional manifest, and
    a HuggingFace-source config; return the config path. Used by the four
    manifest-driven rewrite tests below."""
    import yaml as _yaml

    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "sanitized.jsonl").write_text('{"messages":[]}\n', encoding="utf-8")
    if manifest_payload is not None:
        (datasets_dir / "sanitized.meta.json").write_text(manifest_payload, encoding="utf-8")

    configs_dir = project_dir / "configs"
    configs_dir.mkdir(parents=True)
    config_path = configs_dir / "run.yaml"
    config_path.write_text(
        _yaml.safe_dump(
            {
                "dataset": {
                    "source": "huggingface",
                    "dataset_id": "HuggingFaceH4/ultrachat_200k",
                    "format": original_format,
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _read_rewritten_dataset(*, plan_files: tuple[tuple[Path, str], ...]) -> dict[str, object]:
    import yaml as _yaml

    staged_path, _ = next(
        (local, remote) for local, remote in plan_files if ".modal-uploads" in str(local)
    )
    parsed = _yaml.safe_load(staged_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    dataset = parsed["dataset"]
    assert isinstance(dataset, dict)
    return dataset


def test_rewrite_preserves_original_format_when_manifest_says_not_normalized(
    tmp_path: Path,
) -> None:
    """normalized=false means the sanitizer left rows in the source schema, so
    the rewrite must preserve the user's original `dataset.format` value."""
    from app.services.cloud.modal_adapter import build_modal_upload_plan

    project_dir = tmp_path / "p1"
    config_path = _write_modal_rewrite_fixture(
        project_dir=project_dir,
        manifest_payload='{"content_hash": "abc", "normalized": false}',
    )

    plan = build_modal_upload_plan(project_dir=project_dir, config_path=config_path)
    dataset = _read_rewritten_dataset(plan_files=plan.files)
    assert dataset["format"] == "sharegpt"


def test_rewrite_preserves_original_format_when_manifest_missing(tmp_path: Path) -> None:
    """No manifest at all → conservative fallback preserves the original format."""
    from app.services.cloud.modal_adapter import build_modal_upload_plan

    project_dir = tmp_path / "p1"
    config_path = _write_modal_rewrite_fixture(project_dir=project_dir, manifest_payload=None)

    plan = build_modal_upload_plan(project_dir=project_dir, config_path=config_path)
    dataset = _read_rewritten_dataset(plan_files=plan.files)
    assert dataset["format"] == "sharegpt"


def test_rewrite_preserves_original_format_when_normalized_key_absent(tmp_path: Path) -> None:
    """A manifest without the normalized key (older sanitizer output) must not
    silently force openai — fall back to preserving the original format."""
    from app.services.cloud.modal_adapter import build_modal_upload_plan

    project_dir = tmp_path / "p1"
    config_path = _write_modal_rewrite_fixture(
        project_dir=project_dir,
        manifest_payload='{"content_hash": "abc"}',
    )

    plan = build_modal_upload_plan(project_dir=project_dir, config_path=config_path)
    dataset = _read_rewritten_dataset(plan_files=plan.files)
    assert dataset["format"] == "sharegpt"


def test_rewrite_preserves_train_eval_split_and_ratios(tmp_path: Path) -> None:
    """Split selectors and ratios must survive the rewrite.

    The trainer's local_jsonl loader applies these as-is. A future refactor
    that strips them on the assumption "local_jsonl ignores splits" would
    silently change the dataset partition — pin the behavior with a test.
    """
    import yaml as _yaml

    from app.services.cloud.modal_adapter import build_modal_upload_plan

    project_dir = tmp_path / "p1"
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "sanitized.jsonl").write_text(
        '{"prompt":"x","response":"y"}\n', encoding="utf-8"
    )
    (datasets_dir / "sanitized.meta.json").write_text(
        '{"content_hash": "abc", "normalized": false}', encoding="utf-8"
    )

    configs_dir = project_dir / "configs"
    configs_dir.mkdir(parents=True)
    config_path = configs_dir / "run.yaml"
    config_path.write_text(
        _yaml.safe_dump(
            {
                "dataset": {
                    "source": "huggingface",
                    "dataset_id": "HuggingFaceH4/ultrachat_200k",
                    "format": "sharegpt",
                    "train_split": "train",
                    "eval_split": "validation",
                    "train_ratio": 0.8,
                    "val_ratio": 0.1,
                    "test_ratio": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )

    plan = build_modal_upload_plan(project_dir=project_dir, config_path=config_path)
    dataset = _read_rewritten_dataset(plan_files=plan.files)
    assert dataset["train_split"] == "train"
    assert dataset["eval_split"] == "validation"
    assert dataset["train_ratio"] == 0.8
    assert dataset["val_ratio"] == 0.1
    assert dataset["test_ratio"] == 0.1
    assert dataset["source"] == "local_jsonl"
    assert dataset["dataset_id"] == "/workspace/datasets/sanitized.jsonl"


def test_validate_execution_rejects_modal_without_credentials() -> None:
    cfg = ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "data_policy": "sanitized_cloud",
            "max_estimated_cost_usd": 2.0,
        }
    )
    with pytest.raises(UnsupportedEnvironmentError, match="modal_token"):
        orchestrator._validate_execution_for_run(execution=cfg)


def test_validate_execution_allows_modal_with_credentials() -> None:
    settings_service._overrides["modal_token_id"] = "ak-test"
    settings_service._overrides["modal_token_secret"] = "as-test"
    cfg = ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "data_policy": "sanitized_cloud",
            "max_estimated_cost_usd": 2.0,
        }
    )
    orchestrator._validate_execution_for_run(execution=cfg)


def test_validate_execution_allows_local_unconditionally() -> None:
    cfg = ExecutionConfig.model_validate({"environment": "local"})
    orchestrator._validate_execution_for_run(execution=cfg)


def test_execution_summary_round_trip() -> None:
    cfg = ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "modal_gpu_type": "l40s",
            "data_policy": "sanitized_cloud",
            "max_run_minutes": 45,
            "max_estimated_cost_usd": 1.5,
        }
    )
    summary = orchestrator._execution_summary(execution=cfg)
    assert summary == {
        "environment": "modal",
        "modalGpuType": "l40s",
        "maxRunMinutes": 45,
        "maxEstimatedCostUsd": 1.5,
        "dataPolicy": "sanitized_cloud",
    }


async def test_dispatch_training_modal_without_credentials_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "execution": {
                    "environment": "modal",
                    "data_policy": "sanitized_cloud",
                    "modal_gpu_type": "a10",
                }
            }
        )
    )
    with pytest.raises(ModalCredentialsMissingError):
        await dispatch_training(
            run_id="r1",
            config_path=cfg_path,
            project_dir=tmp_path,
            resume_from_checkpoint=None,
        )


async def test_create_run_rejects_modal_with_local_raw(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak-test"
    settings_service._overrides["modal_token_secret"] = "as-test"

    project_resp = await client.post("/api/v1/projects", json={"name": "modal-rejects-raw"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]
    active_id = project_resp.json()["active_config_version_id"]

    yaml_resp = await client.get(f"/api/v1/projects/{project_id}/configs/{active_id}/yaml")
    assert yaml_resp.status_code == 200
    parsed = yaml.safe_load(yaml_resp.text)
    parsed["execution"]["environment"] = "modal"
    # data_policy defaults to local_raw — explicit for clarity in this assertion.
    parsed["execution"]["data_policy"] = "local_raw"
    updated_yaml = yaml.safe_dump(parsed)

    new_cfg = await client.put(
        f"/api/v1/projects/{project_id}/configs",
        json={"yaml_content": updated_yaml, "source_tag": "user"},
    )
    assert new_cfg.status_code == 201
    new_version_id = new_cfg.json()["id"]

    run_resp = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"config_version_id": new_version_id},
    )
    body = run_resp.json()
    assert run_resp.status_code == 422, body
    error = body["error"]
    assert error["code"] == "UNSUPPORTED_ENVIRONMENT", body
    assert "data_policy" in error["message"]


async def test_create_run_rejects_modal_when_cost_over_cap(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak-test"
    settings_service._overrides["modal_token_secret"] = "as-test"

    project_resp = await client.post("/api/v1/projects", json={"name": "modal-rejects-cost"})
    project_id = project_resp.json()["id"]
    active_id = project_resp.json()["active_config_version_id"]

    yaml_resp = await client.get(f"/api/v1/projects/{project_id}/configs/{active_id}/yaml")
    parsed = yaml.safe_load(yaml_resp.text)
    parsed["execution"]["environment"] = "modal"
    parsed["execution"]["data_policy"] = "sanitized_cloud"
    parsed["execution"]["max_estimated_cost_usd"] = 99.0
    updated_yaml = yaml.safe_dump(parsed)

    new_cfg = await client.put(
        f"/api/v1/projects/{project_id}/configs",
        json={"yaml_content": updated_yaml, "source_tag": "user"},
    )
    assert new_cfg.status_code == 201
    new_version_id = new_cfg.json()["id"]

    run_resp = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"config_version_id": new_version_id},
    )
    body = run_resp.json()
    assert run_resp.status_code == 422, body
    assert "hard cap" in body["error"]["message"]


def test_training_dispatcher_does_not_import_modal_eagerly() -> None:
    """`modal` is an optional cloud extra — base/local installs must still import the dispatcher.

    The TYPE_CHECKING block keeps the symbols available for static analysis without
    executing the import at runtime; the real import happens inside `_spawn_modal_process`.
    """
    import app.services.training_dispatcher as td

    assert "ModalTrainingAdapter" not in td.__dict__
    assert "ModalAdapterConfig" not in td.__dict__


def test_modal_adapter_config_accepts_sandbox_timeout() -> None:
    from app.services.cloud.modal_adapter import ModalAdapterConfig

    cfg = ModalAdapterConfig(
        run_id="r1",
        config_path=Path("/tmp/c.yaml"),
        project_dir=Path("/tmp"),
        gpu_type="a10",
        modal_token_id="ak",
        modal_token_secret="as",
        heartbeat_path=Path("/tmp/.heartbeat"),
        sandbox_timeout_seconds=2700,
    )
    assert cfg.sandbox_timeout_seconds == 2700


def test_modal_adapter_config_default_sandbox_timeout_is_six_hours() -> None:
    from app.services.cloud.modal_adapter import ModalAdapterConfig

    cfg = ModalAdapterConfig(
        run_id="r1",
        config_path=Path("/tmp/c.yaml"),
        project_dir=Path("/tmp"),
        gpu_type="a10",
        modal_token_id="ak",
        modal_token_secret="as",
        heartbeat_path=Path("/tmp/.heartbeat"),
    )
    assert cfg.sandbox_timeout_seconds == 6 * 3600


def test_modal_training_image_includes_quantization_dependencies() -> None:
    """QLoRA configs require bitsandbytes; the trainer's launch wrapper requires accelerate."""
    from app.services.cloud.modal_adapter import _TRAINING_IMAGE_PACKAGES

    package_names = {pkg.split(">=")[0].split("==")[0] for pkg in _TRAINING_IMAGE_PACKAGES}
    assert "bitsandbytes" in package_names
    assert "accelerate" in package_names


async def test_spawn_modal_process_converts_max_run_minutes_to_seconds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`execution.max_run_minutes` must flow into the Modal sandbox timeout."""
    from app.services.cloud import modal_adapter as modal_adapter_module

    captured: dict[str, object] = {}

    class _CapturingAdapter:
        def __init__(self, *, config: object) -> None:
            captured["config"] = config

        async def start(self) -> None:
            return None

        async def read_event(self) -> dict[str, object] | None:
            return None

        async def cancel(self) -> None:
            return None

        async def wait(self) -> int:
            return 0

    monkeypatch.setattr(modal_adapter_module, "ModalTrainingAdapter", _CapturingAdapter)
    settings_service._overrides["modal_token_id"] = "ak"
    settings_service._overrides["modal_token_secret"] = "as"

    execution = ExecutionConfig.model_validate(
        {
            "environment": "modal",
            "modal_gpu_type": "a10",
            "data_policy": "sanitized_cloud",
            "max_run_minutes": 45,
        }
    )

    from app.services.training_dispatcher import _spawn_modal_process

    process = await _spawn_modal_process(
        run_id="r1",
        config_path=tmp_path / "cfg.yaml",
        project_dir=tmp_path,
        resume_from_checkpoint=None,
        execution=execution,
    )
    # Drain the pump task so the test doesn't leak a background coroutine.
    process.cleanup()

    config_passed = captured["config"]
    assert config_passed.sandbox_timeout_seconds == 45 * 60  # type: ignore[attr-defined]


async def test_modal_pump_emits_cancelled_event_when_terminated() -> None:
    """A cancelled Modal run must not be overwritten as `failed` by the orchestrator."""
    import asyncio
    import json as _json

    from app.services.training_dispatcher import ModalTrainingProcess, _pump_modal_events

    class _FakeAdapter:
        def __init__(self) -> None:
            self._events: list[dict[str, object]] = [{"type": "log", "message": "hi"}]
            self.cancel_called = False

        async def read_event(self) -> dict[str, object] | None:
            if self._events:
                return self._events.pop(0)
            return None

        async def cancel(self) -> None:
            self.cancel_called = True

        async def wait(self) -> int:
            return 130

    adapter = _FakeAdapter()
    reader = asyncio.StreamReader()
    process = ModalTrainingProcess(adapter=adapter, stdout_reader=reader)  # type: ignore[arg-type]

    process.terminate()
    # Yield once so the cancel task scheduled by terminate() actually runs.
    await asyncio.sleep(0)
    await _pump_modal_events(process=process, reader=reader)

    collected: list[dict[str, object]] = []
    async for raw_line in reader:
        text = raw_line.decode("utf-8").strip()
        if text:
            collected.append(_json.loads(text))

    terminals = [event for event in collected if event.get("type") == "complete"]
    assert len(terminals) == 1
    assert terminals[0]["status"] == "cancelled"
    assert adapter.cancel_called is True


async def test_modal_pump_does_not_emit_cancelled_when_not_terminated() -> None:
    """Natural EOF (no terminate call) must not synthesize a cancelled event."""
    import asyncio
    import json as _json

    from app.services.training_dispatcher import ModalTrainingProcess, _pump_modal_events

    class _FakeAdapter:
        def __init__(self) -> None:
            self._events: list[dict[str, object]] = [
                {"type": "log", "message": "ok"},
                {"type": "complete", "status": "completed"},
            ]

        async def read_event(self) -> dict[str, object] | None:
            if self._events:
                return self._events.pop(0)
            return None

        async def cancel(self) -> None:
            return None

        async def wait(self) -> int:
            return 0

    adapter = _FakeAdapter()
    reader = asyncio.StreamReader()
    process = ModalTrainingProcess(adapter=adapter, stdout_reader=reader)  # type: ignore[arg-type]

    await _pump_modal_events(process=process, reader=reader)

    collected: list[dict[str, object]] = []
    async for raw_line in reader:
        text = raw_line.decode("utf-8").strip()
        if text:
            collected.append(_json.loads(text))

    terminals = [event for event in collected if event.get("type") == "complete"]
    assert len(terminals) == 1
    assert terminals[0]["status"] == "completed"


@pytest.fixture
async def patched_session_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
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


async def test_process_trainer_event_stage_enter_populates_started_at(
    patched_session_factory,
) -> None:
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="pending",
                created_at="2026-05-19T11:30:00+00:00",
                updated_at="2026-05-19T11:30:00+00:00",
            )
        )
        await session.commit()

    stage_start_times: dict[str, str] = {}
    final_metrics: dict[str, float] = {}
    await orchestrator._process_trainer_event(
        event={
            "type": "stage_enter",
            "stage_name": "load_model",
            "stage_order": 1,
            "timestamp": "2026-05-19T12:00:00+00:00",
        },
        run_id="r1",
        project_id="p1",
        stage_start_times=stage_start_times,
        final_metrics=final_metrics,
    )

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.started_at == "2026-05-19T12:00:00+00:00"


async def test_create_run_persists_modal_execution_metadata_to_run_row(
    patched_session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg_module
    from app.models.config_version import ConfigVersion
    from app.models.project import Project
    from app.schemas.run import RunCreate, RunResponse

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)
    settings_service._overrides["modal_token_id"] = "ak-test"
    settings_service._overrides["modal_token_secret"] = "as-test"

    project_dir = tmp_path / "modal-meta-project"
    project_dir.mkdir()
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir()
    (datasets_dir / "sanitized.jsonl").write_text('{"prompt":"x","response":"y"}\n')

    yaml_blob = yaml.safe_dump(
        {
            "execution": {
                "environment": "modal",
                "modal_gpu_type": "l40s",
                "device": "cuda",
                "data_policy": "sanitized_cloud",
                "max_estimated_cost_usd": 2.0,
            }
        }
    )

    async with patched_session_factory() as session:
        session.add(
            Project(
                id="p1",
                name="modal-meta-project",
                directory_path=str(project_dir),
                created_at="2026-05-19T11:00:00+00:00",
                updated_at="2026-05-19T11:00:00+00:00",
            )
        )
        session.add(
            ConfigVersion(
                id="cv1",
                project_id="p1",
                version_number=1,
                yaml_blob=yaml_blob,
                yaml_hash="hash",
                source_tag="user",
                created_at="2026-05-19T11:00:00+00:00",
            )
        )
        await session.commit()

        created = await orchestrator.create_run(
            session=session,
            project_id="p1",
            payload=RunCreate(config_version_id="cv1"),
        )
        run_id = created.id

    async with patched_session_factory() as session:
        persisted = await session.get(Run, run_id)
        assert persisted is not None
        assert persisted.environment == "modal"
        assert persisted.modal_gpu_type == "l40s"
        assert persisted.device == "cuda"

        response = RunResponse.model_validate(persisted)
        assert response.environment == "modal"
        assert response.modal_gpu_type == "l40s"
        assert response.device == "cuda"


async def test_create_run_local_environment_leaves_modal_gpu_type_null(
    patched_session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg_module
    from app.models.config_version import ConfigVersion
    from app.models.project import Project
    from app.schemas.run import RunCreate

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    project_dir = tmp_path / "local-meta-project"
    project_dir.mkdir()

    yaml_blob = yaml.safe_dump(
        {
            "execution": {
                "environment": "local",
                "device": "mps",
            }
        }
    )

    async with patched_session_factory() as session:
        session.add(
            Project(
                id="p2",
                name="local-meta-project",
                directory_path=str(project_dir),
                created_at="2026-05-19T11:00:00+00:00",
                updated_at="2026-05-19T11:00:00+00:00",
            )
        )
        session.add(
            ConfigVersion(
                id="cv2",
                project_id="p2",
                version_number=1,
                yaml_blob=yaml_blob,
                yaml_hash="hash",
                source_tag="user",
                created_at="2026-05-19T11:00:00+00:00",
            )
        )
        await session.commit()

        created = await orchestrator.create_run(
            session=session,
            project_id="p2",
            payload=RunCreate(config_version_id="cv2"),
        )
        run_id = created.id

    async with patched_session_factory() as session:
        persisted = await session.get(Run, run_id)
        assert persisted is not None
        assert persisted.environment == "local"
        assert persisted.modal_gpu_type is None
        assert persisted.device == "mps"


async def test_process_trainer_event_stage_enter_does_not_overwrite_started_at(
    patched_session_factory,
) -> None:
    async with patched_session_factory() as session:
        session.add(
            Run(
                id="r1",
                project_id="p1",
                config_version_id="cv1",
                status="running",
                started_at="2026-05-19T12:00:00+00:00",
                created_at="2026-05-19T11:30:00+00:00",
                updated_at="2026-05-19T12:00:00+00:00",
            )
        )
        await session.commit()

    await orchestrator._process_trainer_event(
        event={
            "type": "stage_enter",
            "stage_name": "tokenize",
            "stage_order": 2,
            "timestamp": "2026-05-19T12:05:00+00:00",
        },
        run_id="r1",
        project_id="p1",
        stage_start_times={},
        final_metrics={},
    )

    async with patched_session_factory() as session:
        run = await session.get(Run, "r1")
        assert run is not None
        assert run.started_at == "2026-05-19T12:00:00+00:00"
