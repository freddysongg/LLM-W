"""Merge a training run's peft adapter into its base model and persist the result.

The merge call is synchronous from the caller's point of view — the route
awaits :func:`merge_run_into_base` and the response is the persisted
:class:`MergedModelResponse`. The heavy ``peft.merge_and_unload`` step is run
inside a thread pool so the FastAPI event loop stays responsive while the
CPU-bound work executes (merges can take minutes on large bases).

Lazy-import contract: ``peft`` and ``transformers`` are training extras. Both
are imported only inside :func:`_perform_merge`, never at module level, so
base/local installs without the ``training`` extra can still import this
module.

Storage layout: merged checkpoints land under
``{project.directory_path}/merged/{merged_id}/``, mirroring the per-run
checkpoint layout.
"""

from __future__ import annotations

import asyncio
import functools
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConfigVersionNotFoundError,
    NoCheckpointError,
    ProjectNotFoundError,
    RunNotFoundError,
)
from app.models.config_version import ConfigVersion
from app.models.merged_model import MergedModel
from app.models.project import Project
from app.models.run import Run
from app.schemas.merged_model import MergedModelListResponse, MergedModelResponse


class MergedModelNotFoundError(Exception):
    def __init__(self, merged_id: str) -> None:
        super().__init__(f"Merged model not found: {merged_id}")
        self.merged_id = merged_id


class MissingBaseModelError(Exception):
    def __init__(self, project_id: str) -> None:
        super().__init__(
            f"Active config for project {project_id} has no model.model_id"
        )
        self.project_id = project_id


def _to_response(merged: MergedModel) -> MergedModelResponse:
    return MergedModelResponse.model_validate(merged)


async def _load_project(*, session: AsyncSession, project_id: str) -> Project:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(project_id)
    return project


async def _load_run(
    *, session: AsyncSession, project_id: str, run_id: str
) -> Run:
    result = await session.execute(
        select(Run).where(Run.id == run_id, Run.project_id == project_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise RunNotFoundError(run_id)
    return run


async def _load_merged(
    *, session: AsyncSession, project_id: str, merged_id: str
) -> MergedModel:
    result = await session.execute(
        select(MergedModel).where(
            MergedModel.id == merged_id,
            MergedModel.project_id == project_id,
        )
    )
    merged = result.scalar_one_or_none()
    if merged is None:
        raise MergedModelNotFoundError(merged_id)
    return merged


async def _get_run_base_model_id(
    *, session: AsyncSession, run: Run
) -> str:
    """Resolve the base model from the run's frozen config snapshot.

    peft adapters are tied to the specific base they were trained against. If
    the project's active config has moved on since the run completed, that
    later base may have a different architecture or weight shape and the
    merge would silently produce an invalid checkpoint. Reading the run's
    own `config_version_id` keeps the merge faithful to what was trained.
    """
    result = await session.execute(
        select(ConfigVersion).where(ConfigVersion.id == run.config_version_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise ConfigVersionNotFoundError(run.config_version_id)
    parsed: dict[str, Any] = yaml.safe_load(config.yaml_blob) or {}
    model_section = parsed.get("model", {}) if isinstance(parsed, dict) else {}
    base_model_id = (
        model_section.get("model_id") if isinstance(model_section, dict) else None
    )
    if not isinstance(base_model_id, str) or not base_model_id:
        raise MissingBaseModelError(run.project_id)
    return base_model_id


def _dir_size_bytes(path: Path) -> int:
    if not path.is_dir():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


async def list_merged_models(
    *,
    session: AsyncSession,
    project_id: str,
) -> MergedModelListResponse:
    await _load_project(session=session, project_id=project_id)
    total_q = select(func.count()).where(MergedModel.project_id == project_id)
    items_q = (
        select(MergedModel)
        .where(MergedModel.project_id == project_id)
        .order_by(MergedModel.created_at.desc())
    )
    total = (await session.execute(total_q)).scalar_one()
    rows = list((await session.execute(items_q)).scalars().all())
    return MergedModelListResponse(
        items=[_to_response(m) for m in rows],
        total=total,
    )


async def get_merged_model(
    *,
    session: AsyncSession,
    project_id: str,
    merged_id: str,
) -> MergedModelResponse:
    merged = await _load_merged(
        session=session, project_id=project_id, merged_id=merged_id
    )
    return _to_response(merged)


async def merge_run_into_base(
    *,
    session: AsyncSession,
    project_id: str,
    source_run_id: str,
) -> MergedModelResponse:
    project = await _load_project(session=session, project_id=project_id)
    run = await _load_run(
        session=session, project_id=project_id, run_id=source_run_id
    )
    if run.last_checkpoint_path is None:
        raise NoCheckpointError(source_run_id)
    adapter_path = Path(run.last_checkpoint_path)
    base_model_id = await _get_run_base_model_id(session=session, run=run)

    merged_id = str(uuid.uuid4())
    output_path = Path(project.directory_path) / "merged" / merged_id

    try:
        await asyncio.get_running_loop().run_in_executor(
            None,
            functools.partial(
                _perform_merge,
                base_model_id=base_model_id,
                adapter_path=adapter_path,
                output_path=output_path,
            ),
        )
    except BaseException:
        shutil.rmtree(output_path, ignore_errors=True)
        raise

    size_bytes = _dir_size_bytes(output_path)
    now = datetime.now(UTC).isoformat()
    merged = MergedModel(
        id=merged_id,
        project_id=project_id,
        base_model_id=base_model_id,
        source_run_id=source_run_id,
        adapter_step=run.current_step,
        file_path=str(output_path),
        file_size_bytes=size_bytes,
        created_at=now,
    )
    session.add(merged)
    await session.commit()
    return _to_response(merged)


async def delete_merged_model(
    *,
    session: AsyncSession,
    project_id: str,
    merged_id: str,
) -> None:
    merged = await _load_merged(
        session=session, project_id=project_id, merged_id=merged_id
    )
    target = Path(merged.file_path)
    await session.delete(merged)
    await session.commit()
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)


def _perform_merge(
    *,
    base_model_id: str,
    adapter_path: Path,
    output_path: Path,
) -> None:
    """Load base + adapter, run peft.merge_and_unload, write the merged dir.

    Runs on the calling thread (intended to be a thread-pool worker since the
    operations here are CPU- and IO-heavy and can take minutes).
    """
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    output_path.mkdir(parents=True, exist_ok=True)
    base_model = AutoModelForCausalLM.from_pretrained(base_model_id)
    peft_model = PeftModel.from_pretrained(base_model, str(adapter_path))
    merged_model = peft_model.merge_and_unload()
    merged_model.save_pretrained(str(output_path))
    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    tokenizer.save_pretrained(str(output_path))
