from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app

_MINIMAL_YAML = """\
project:
  name: test-project
  description: ""
  mode: single_user_local
model:
  source: huggingface
  model_id: ""
  family: causal_lm
  revision: main
  trust_remote_code: false
  torch_dtype: auto
dataset:
  source: huggingface
  dataset_id: ""
  train_split: train
  eval_split: validation
  input_field: prompt
  target_field: response
  format: default
preprocessing:
  max_seq_length: 512
  truncation: true
  packing: false
  padding: longest
training:
  task_type: sft
  epochs: 2
  batch_size: 4
  gradient_accumulation_steps: 4
  learning_rate: 0.0002
  weight_decay: 0.01
  max_grad_norm: 1.0
  eval_steps: 50
  save_steps: 100
  logging_steps: 10
  seed: 42
optimization:
  optimizer: adamw
  scheduler: cosine
  warmup_ratio: 0.03
  warmup_steps: 0
  gradient_checkpointing: true
  mixed_precision: bf16
adapters:
  enabled: true
  type: lora
  rank: 8
  alpha: 16
  dropout: 0.05
  target_modules:
    - q_proj
    - v_proj
  bias: none
  task_type: CAUSAL_LM
quantization:
  enabled: false
  mode: 4bit
  compute_dtype: bfloat16
  quant_type: nf4
  double_quant: true
observability:
  log_every_steps: 10
  capture_grad_norm: true
  capture_memory: true
  capture_activation_samples: true
  capture_weight_deltas: true
  observability_level: standard
ai_assistant:
  enabled: true
  provider: anthropic
  mode: suggest_only
  allow_config_diffs: true
  auto_analyze_on_completion: true
execution:
  device: auto
  num_workers: 2
checkpoint_retention:
  keep_last_n: 3
  always_keep_best_eval: true
  always_keep_final: true
  delete_intermediates_after_completion: true
introspection:
  architecture_view: true
  editable_weight_scope: bounded_expert_mode
  activation_probe_samples: 3
  activation_storage: summary_only
"""


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


@pytest.fixture
async def project_id(client: AsyncClient, tmp_path, monkeypatch) -> str:
    from app.core import config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    resp = await client.post(
        "/api/v1/projects", json={"name": "config-test-project"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_list_config_versions(client: AsyncClient, project_id: str) -> None:
    response = await client.get(f"/api/v1/projects/{project_id}/configs")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["total"] >= 1  # initial config created on project creation


async def test_get_active_config(client: AsyncClient, project_id: str) -> None:
    response = await client.get(f"/api/v1/projects/{project_id}/configs/active")
    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert "version_number" in body
    assert body["version_number"] == 1


async def test_create_config_version(client: AsyncClient, project_id: str) -> None:
    modified_yaml = _MINIMAL_YAML.replace("learning_rate: 0.0002", "learning_rate: 0.0001")
    response = await client.put(
        f"/api/v1/projects/{project_id}/configs",
        json={
            "yaml_content": modified_yaml,
            "source_tag": "user",
            "source_detail": None,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["version_number"] == 2
    assert body["source_tag"] == "user"


async def test_create_config_version_diff_computed(
    client: AsyncClient, project_id: str
) -> None:
    modified_yaml = _MINIMAL_YAML.replace("learning_rate: 0.0002", "learning_rate: 0.0001")
    response = await client.put(
        f"/api/v1/projects/{project_id}/configs",
        json={"yaml_content": modified_yaml, "source_tag": "user"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["diff_from_prev"] is not None
    diff = body["diff_from_prev"]
    assert "changed" in diff
    assert "training.learning_rate" in diff["changed"]


async def test_get_config_version_by_id(client: AsyncClient, project_id: str) -> None:
    active_resp = await client.get(f"/api/v1/projects/{project_id}/configs/active")
    version_id = active_resp.json()["id"]

    response = await client.get(f"/api/v1/projects/{project_id}/configs/{version_id}")
    assert response.status_code == 200
    assert response.json()["id"] == version_id


async def test_get_config_version_not_found(client: AsyncClient, project_id: str) -> None:
    response = await client.get(f"/api/v1/projects/{project_id}/configs/nonexistent-id")
    assert response.status_code == 404


async def test_diff_config_versions(client: AsyncClient, project_id: str) -> None:
    active_resp = await client.get(f"/api/v1/projects/{project_id}/configs/active")
    version_a_id = active_resp.json()["id"]

    modified_yaml = _MINIMAL_YAML.replace("rank: 8", "rank: 16")
    put_resp = await client.put(
        f"/api/v1/projects/{project_id}/configs",
        json={"yaml_content": modified_yaml, "source_tag": "user"},
    )
    version_b_id = put_resp.json()["id"]

    response = await client.get(
        f"/api/v1/projects/{project_id}/configs/{version_a_id}/diff/{version_b_id}"
    )
    assert response.status_code == 200
    body = response.json()
    assert "diff" in body
    assert "changed" in body["diff"]


async def test_validate_config_version_valid(client: AsyncClient, project_id: str) -> None:
    active_resp = await client.get(f"/api/v1/projects/{project_id}/configs/active")
    version_id = active_resp.json()["id"]

    response = await client.post(
        f"/api/v1/projects/{project_id}/configs/{version_id}/validate"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is True
    assert body["errors"] == []


async def test_get_config_yaml(client: AsyncClient, project_id: str) -> None:
    active_resp = await client.get(f"/api/v1/projects/{project_id}/configs/active")
    version_id = active_resp.json()["id"]

    response = await client.get(
        f"/api/v1/projects/{project_id}/configs/{version_id}/yaml"
    )
    assert response.status_code == 200
    assert "project:" in response.text


async def test_create_invalid_yaml_rejected(client: AsyncClient, project_id: str) -> None:
    response = await client.put(
        f"/api/v1/projects/{project_id}/configs",
        json={"yaml_content": "this: is: not: valid: yaml:", "source_tag": "user"},
    )
    assert response.status_code in (422, 500)
