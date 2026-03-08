from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ProjectNameConflictError, ProjectNotFoundError
from app.models.project import Project
from app.models.run import Run
from app.schemas.config_version import ConfigVersionCreate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.storage import (
    ProjectStorageResponse,
    RetentionPolicySummary,
    RunStorageSummary,
    StorageCategoryDetail,
)
from app.services.config_service import create_config_version


async def list_projects(*, session: AsyncSession) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


async def get_project(*, session: AsyncSession, project_id: str) -> Project:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(project_id)
    return project


async def create_project(*, session: AsyncSession, payload: ProjectCreate) -> Project:
    existing_result = await session.execute(
        select(Project).where(Project.name == payload.name)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise ProjectNameConflictError(payload.name)

    project_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    project_dir = settings.projects_dir / payload.name
    project_dir.mkdir(parents=True, exist_ok=True)

    project = Project(
        id=project_id,
        name=payload.name,
        description=payload.description,
        directory_path=str(project_dir),
        active_config_version_id=None,
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    await session.flush()

    initial_yaml = _build_initial_config_yaml(payload.name)
    config_version = await create_config_version(
        session=session,
        project_id=project_id,
        payload=ConfigVersionCreate(
            yaml_content=initial_yaml,
            source_tag="system",
            source_detail="initial scaffold config",
        ),
    )

    project.active_config_version_id = config_version.id
    await session.commit()
    await session.refresh(project)

    return project


async def update_project(
    *, session: AsyncSession, project_id: str, payload: ProjectUpdate
) -> Project:
    project = await get_project(session=session, project_id=project_id)

    if payload.name is not None and payload.name != project.name:
        conflict_result = await session.execute(
            select(Project).where(Project.name == payload.name)
        )
        if conflict_result.scalar_one_or_none() is not None:
            raise ProjectNameConflictError(payload.name)
        project.name = payload.name

    if payload.description is not None:
        project.description = payload.description

    project.updated_at = datetime.now(UTC).isoformat()
    await session.commit()
    await session.refresh(project)

    return project


async def delete_project(*, session: AsyncSession, project_id: str) -> None:
    project = await get_project(session=session, project_id=project_id)

    project_dir = Path(project.directory_path)
    if project_dir.exists():
        shutil.rmtree(project_dir)

    await session.delete(project)
    await session.commit()


async def set_active_config_version(
    *, session: AsyncSession, project_id: str, config_version_id: str
) -> None:
    project = await get_project(session=session, project_id=project_id)
    project.active_config_version_id = config_version_id
    project.updated_at = datetime.now(UTC).isoformat()
    await session.commit()


async def get_project_storage(
    *, session: AsyncSession, project_id: str
) -> ProjectStorageResponse:
    project = await get_project(session=session, project_id=project_id)
    project_dir = Path(project.directory_path)

    categories = ["checkpoints", "logs", "activations", "exports", "configs"]
    breakdown: dict[str, StorageCategoryDetail] = {}

    for category in categories:
        category_dir = project_dir / category
        if category_dir.exists():
            total_bytes = sum(
                f.stat().st_size for f in category_dir.rglob("*") if f.is_file()
            )
            file_count = sum(1 for f in category_dir.rglob("*") if f.is_file())
        else:
            total_bytes = 0
            file_count = 0
        breakdown[category] = StorageCategoryDetail(bytes=total_bytes, file_count=file_count)

    total_bytes = sum(detail.bytes for detail in breakdown.values())

    runs_result = await session.execute(
        select(Run).where(Run.project_id == project_id)
    )
    runs = list(runs_result.scalars().all())
    per_run = [
        RunStorageSummary(
            run_id=run.id,
            total_bytes=0,
            checkpoint_count=0,
            status=run.status,
        )
        for run in runs
    ]

    checkpoints_dir = project_dir / "checkpoints"
    reclaimable_bytes = 0
    reclaimable_checkpoints = 0
    if checkpoints_dir.exists():
        checkpoint_dirs = sorted(
            [d for d in checkpoints_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
        )
        keep_last_n = settings.watchdog_stale_timeout_seconds  # using config default
        keep_last_n = 3  # default retention
        if len(checkpoint_dirs) > keep_last_n:
            excess = checkpoint_dirs[: len(checkpoint_dirs) - keep_last_n]
            reclaimable_checkpoints = len(excess)
            reclaimable_bytes = sum(
                f.stat().st_size
                for d in excess
                for f in d.rglob("*")
                if f.is_file()
            )

    return ProjectStorageResponse(
        project_id=project_id,
        total_bytes=total_bytes,
        breakdown=breakdown,
        per_run=per_run,
        retention_policy=RetentionPolicySummary(
            keep_last_n=3,
            reclaimable_bytes=reclaimable_bytes,
            reclaimable_checkpoints=reclaimable_checkpoints,
        ),
    )


def _build_initial_config_yaml(project_name: str) -> str:
    import yaml as pyyaml

    config: dict[str, object] = {
        "project": {
            "name": project_name,
            "description": "",
            "mode": "single_user_local",
        },
        "model": {
            "source": "huggingface",
            "model_id": "",
            "family": "causal_lm",
            "revision": "main",
            "trust_remote_code": False,
            "torch_dtype": "auto",
        },
        "dataset": {
            "source": "huggingface",
            "dataset_id": "",
            "train_split": "train",
            "eval_split": "validation",
            "input_field": "prompt",
            "target_field": "response",
            "format": "default",
        },
        "preprocessing": {
            "max_seq_length": 512,
            "truncation": True,
            "packing": False,
            "padding": "longest",
        },
        "training": {
            "task_type": "sft",
            "epochs": 2,
            "batch_size": 4,
            "gradient_accumulation_steps": 4,
            "learning_rate": 0.0002,
            "weight_decay": 0.01,
            "max_grad_norm": 1.0,
            "eval_steps": 50,
            "save_steps": 100,
            "logging_steps": 10,
            "seed": 42,
        },
        "optimization": {
            "optimizer": "adamw",
            "scheduler": "cosine",
            "warmup_ratio": 0.03,
            "warmup_steps": 0,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
        },
        "adapters": {
            "enabled": True,
            "type": "lora",
            "rank": 8,
            "alpha": 16,
            "dropout": 0.05,
            "target_modules": ["q_proj", "v_proj"],
            "bias": "none",
            "task_type": "CAUSAL_LM",
        },
        "quantization": {
            "enabled": False,
            "mode": "4bit",
            "compute_dtype": "bfloat16",
            "quant_type": "nf4",
            "double_quant": True,
        },
        "observability": {
            "log_every_steps": 10,
            "capture_grad_norm": True,
            "capture_memory": True,
            "capture_activation_samples": True,
            "capture_weight_deltas": True,
            "observability_level": "standard",
        },
        "ai_assistant": {
            "enabled": True,
            "provider": "anthropic",
            "mode": "suggest_only",
            "allow_config_diffs": True,
            "auto_analyze_on_completion": True,
        },
        "execution": {
            "device": "auto",
            "num_workers": 2,
        },
        "checkpoint_retention": {
            "keep_last_n": 3,
            "always_keep_best_eval": True,
            "always_keep_final": True,
            "delete_intermediates_after_completion": True,
        },
        "introspection": {
            "architecture_view": True,
            "editable_weight_scope": "bounded_expert_mode",
            "activation_probe_samples": 3,
            "activation_storage": "summary_only",
        },
    }

    return pyyaml.dump(config, default_flow_style=False, allow_unicode=True)
