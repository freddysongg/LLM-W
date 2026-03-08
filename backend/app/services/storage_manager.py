from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ArtifactFileNotFoundError, ArtifactNotFoundError
from app.models.artifact import Artifact
from app.models.config_version import ConfigVersion
from app.models.project import Project
from app.models.run import Run
from app.models.storage_record import StorageRecord
from app.schemas.artifact import ArtifactCleanupResponse, ArtifactListResponse, ArtifactResponse
from app.schemas.storage import (
    ProjectStorageResponse,
    RetentionPolicySummary,
    RunStorageSummary,
    StorageCategoryDetail,
    StorageTotalResponse,
)


async def get_project_storage(*, session: AsyncSession, project_id: str) -> ProjectStorageResponse:
    sr_result = await session.execute(
        select(StorageRecord).where(StorageRecord.project_id == project_id)
    )
    storage_records = list(sr_result.scalars().all())

    breakdown: dict[str, StorageCategoryDetail] = {}
    total_bytes = 0
    for record in storage_records:
        breakdown[record.category] = StorageCategoryDetail(
            bytes=record.total_bytes,
            file_count=record.file_count,
        )
        total_bytes += record.total_bytes

    if not breakdown:
        breakdown, total_bytes = await _compute_storage_breakdown(
            session=session, project_id=project_id
        )
        await _upsert_storage_records(session=session, project_id=project_id, breakdown=breakdown)

    runs_result = await session.execute(select(Run).where(Run.project_id == project_id))
    runs = list(runs_result.scalars().all())

    per_run: list[RunStorageSummary] = []
    for run in runs:
        artifacts_result = await session.execute(select(Artifact).where(Artifact.run_id == run.id))
        artifacts = list(artifacts_result.scalars().all())
        run_bytes = sum(a.file_size_bytes for a in artifacts if a.file_size_bytes is not None)
        checkpoint_count = sum(1 for a in artifacts if a.artifact_type == "checkpoint")
        per_run.append(
            RunStorageSummary(
                run_id=run.id,
                total_bytes=run_bytes,
                checkpoint_count=checkpoint_count,
                status=run.status,
            )
        )

    retention = await _compute_retention_summary(session=session, project_id=project_id)

    return ProjectStorageResponse(
        project_id=project_id,
        total_bytes=total_bytes,
        breakdown=breakdown,
        per_run=per_run,
        retention_policy=retention,
    )


async def get_total_storage(*, session: AsyncSession) -> StorageTotalResponse:
    projects_result = await session.execute(select(Project))
    projects = list(projects_result.scalars().all())

    total_bytes = 0
    per_project: dict[str, int] = {}

    for project in projects:
        sr_result = await session.execute(
            select(StorageRecord).where(StorageRecord.project_id == project.id)
        )
        records = list(sr_result.scalars().all())
        project_bytes = sum(r.total_bytes for r in records)
        if not records:
            breakdown, project_bytes = await _compute_storage_breakdown(
                session=session, project_id=project.id
            )
            await _upsert_storage_records(
                session=session, project_id=project.id, breakdown=breakdown
            )
        per_project[project.id] = project_bytes
        total_bytes += project_bytes

    return StorageTotalResponse(
        total_bytes=total_bytes,
        per_project=per_project,
        project_count=len(projects),
    )


async def run_project_cleanup(*, session: AsyncSession, project_id: str) -> ArtifactCleanupResponse:
    project_result = await session.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    retention_cfg = await _load_retention_config(session=session, project_id=project_id)

    runs_result = await session.execute(
        select(Run).where(
            Run.project_id == project_id,
            Run.status == "completed",
        )
    )
    completed_runs = list(runs_result.scalars().all())

    deleted_count = 0
    freed_bytes = 0
    retained_count = 0

    for run in completed_runs:
        result = await _apply_retention_for_run(
            session=session,
            run=run,
            project_directory=project.directory_path if project else None,
            keep_last_n=retention_cfg["keep_last_n"],
            always_keep_best_eval=retention_cfg["always_keep_best_eval"],
            always_keep_final=retention_cfg["always_keep_final"],
            delete_intermediates=retention_cfg["delete_intermediates_after_completion"],
        )
        deleted_count += result["deleted"]
        freed_bytes += result["freed_bytes"]
        retained_count += result["retained"]

    breakdown, _ = await _compute_storage_breakdown(session=session, project_id=project_id)
    await _upsert_storage_records(session=session, project_id=project_id, breakdown=breakdown)

    return ArtifactCleanupResponse(
        deleted_count=deleted_count,
        freed_bytes=freed_bytes,
        retained_count=retained_count,
    )


async def run_artifact_cleanup(
    *, session: AsyncSession, project_id: str
) -> ArtifactCleanupResponse:
    return await run_project_cleanup(session=session, project_id=project_id)


async def _apply_retention_for_run(
    *,
    session: AsyncSession,
    run: Run,
    project_directory: str | None,
    keep_last_n: int,
    always_keep_best_eval: bool,
    always_keep_final: bool,
    delete_intermediates: bool,
) -> dict[str, int]:
    checkpoints_result = await session.execute(
        select(Artifact)
        .where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == "checkpoint",
        )
        .order_by(Artifact.created_at)
    )
    checkpoints = list(checkpoints_result.scalars().all())

    if not checkpoints:
        return {"deleted": 0, "freed_bytes": 0, "retained": 0}

    retained_ids: set[str] = set()

    if keep_last_n > 0:
        for ckpt in checkpoints[-keep_last_n:]:
            retained_ids.add(ckpt.id)

    if always_keep_final and checkpoints:
        retained_ids.add(checkpoints[-1].id)

    if always_keep_best_eval:
        best_eval_result = await session.execute(
            select(Artifact).where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == "checkpoint",
                Artifact.is_retained == 1,
            )
        )
        for ckpt in best_eval_result.scalars().all():
            retained_ids.add(ckpt.id)

    deleted = 0
    freed_bytes = 0
    retained = 0

    for ckpt in checkpoints:
        if ckpt.id in retained_ids:
            ckpt.is_retained = 1
            retained += 1
        else:
            ckpt.is_retained = 0
            if delete_intermediates:
                file_bytes = ckpt.file_size_bytes or 0
                if project_directory is not None:
                    ckpt_path = Path(ckpt.file_path)
                    if ckpt_path.exists():
                        try:
                            if ckpt_path.is_dir():
                                import shutil

                                shutil.rmtree(ckpt_path)
                            else:
                                ckpt_path.unlink()
                            freed_bytes += file_bytes
                            deleted += 1
                            await session.delete(ckpt)
                        except OSError:
                            pass

    return {"deleted": deleted, "freed_bytes": freed_bytes, "retained": retained}


async def _compute_storage_breakdown(
    *, session: AsyncSession, project_id: str
) -> tuple[dict[str, StorageCategoryDetail], int]:
    artifacts_result = await session.execute(
        select(Artifact).where(Artifact.project_id == project_id)
    )
    artifacts = list(artifacts_result.scalars().all())

    category_map: dict[str, tuple[int, int]] = {}
    for artifact in artifacts:
        category = _artifact_type_to_category(artifact.artifact_type)
        size = artifact.file_size_bytes or 0
        existing_bytes, existing_count = category_map.get(category, (0, 0))
        category_map[category] = (existing_bytes + size, existing_count + 1)

    breakdown: dict[str, StorageCategoryDetail] = {}
    total_bytes = 0
    for category, (cat_bytes, file_count) in category_map.items():
        breakdown[category] = StorageCategoryDetail(bytes=cat_bytes, file_count=file_count)
        total_bytes += cat_bytes

    return breakdown, total_bytes


async def _upsert_storage_records(
    *,
    session: AsyncSession,
    project_id: str,
    breakdown: dict[str, StorageCategoryDetail],
) -> None:
    now = datetime.now(UTC).isoformat()
    existing_result = await session.execute(
        select(StorageRecord).where(StorageRecord.project_id == project_id)
    )
    existing_by_category: dict[str, StorageRecord] = {
        r.category: r for r in existing_result.scalars().all()
    }

    for category, detail in breakdown.items():
        if category in existing_by_category:
            record = existing_by_category[category]
            record.total_bytes = detail.bytes
            record.file_count = detail.file_count
            record.last_computed_at = now
        else:
            record = StorageRecord(
                id=str(uuid.uuid4()),
                project_id=project_id,
                category=category,
                total_bytes=detail.bytes,
                file_count=detail.file_count,
                last_computed_at=now,
            )
            session.add(record)

    for category, record in existing_by_category.items():
        if category not in breakdown:
            record.total_bytes = 0
            record.file_count = 0
            record.last_computed_at = now


async def _compute_retention_summary(
    *, session: AsyncSession, project_id: str
) -> RetentionPolicySummary:
    retention_cfg = await _load_retention_config(session=session, project_id=project_id)
    keep_last_n = retention_cfg["keep_last_n"]

    runs_result = await session.execute(
        select(Run).where(
            Run.project_id == project_id,
            Run.status == "completed",
        )
    )
    runs = list(runs_result.scalars().all())

    reclaimable_bytes = 0
    reclaimable_checkpoints = 0

    for run in runs:
        checkpoints_result = await session.execute(
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == "checkpoint",
            )
            .order_by(Artifact.created_at)
        )
        checkpoints = list(checkpoints_result.scalars().all())
        if len(checkpoints) > keep_last_n:
            non_retained = checkpoints[:-keep_last_n]
            for ckpt in non_retained:
                if ckpt.is_retained == 0:
                    reclaimable_checkpoints += 1
                    reclaimable_bytes += ckpt.file_size_bytes or 0

    return RetentionPolicySummary(
        keep_last_n=keep_last_n,
        reclaimable_bytes=reclaimable_bytes,
        reclaimable_checkpoints=reclaimable_checkpoints,
    )


async def _load_retention_config(*, session: AsyncSession, project_id: str) -> dict[str, object]:
    defaults = {
        "keep_last_n": 3,
        "always_keep_best_eval": True,
        "always_keep_final": True,
        "delete_intermediates_after_completion": True,
    }

    project_result = await session.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if project is None or project.active_config_version_id is None:
        return defaults

    cv_result = await session.execute(
        select(ConfigVersion.yaml_blob).where(ConfigVersion.id == project.active_config_version_id)
    )
    yaml_blob = cv_result.scalar_one_or_none()
    if yaml_blob is None:
        return defaults

    parsed = yaml.safe_load(yaml_blob)
    if not isinstance(parsed, dict):
        return defaults

    retention = parsed.get("checkpoint_retention", {})
    if not isinstance(retention, dict):
        return defaults

    return {
        "keep_last_n": int(retention.get("keep_last_n", defaults["keep_last_n"])),
        "always_keep_best_eval": bool(
            retention.get("always_keep_best_eval", defaults["always_keep_best_eval"])
        ),
        "always_keep_final": bool(
            retention.get("always_keep_final", defaults["always_keep_final"])
        ),
        "delete_intermediates_after_completion": bool(
            retention.get(
                "delete_intermediates_after_completion",
                defaults["delete_intermediates_after_completion"],
            )
        ),
    }


def _artifact_type_to_category(artifact_type: str) -> str:
    mapping = {
        "checkpoint": "checkpoints",
        "log_file": "logs",
        "activation_summary": "activations",
        "metric_export": "exports",
        "config_snapshot": "configs",
        "eval_output": "exports",
        "comparison_summary": "exports",
        "weight_delta": "exports",
        "ai_recommendation": "exports",
    }
    return mapping.get(artifact_type, "other")


# ---------------------------------------------------------------------------
# Artifact CRUD (service functions used by the artifacts router)
# ---------------------------------------------------------------------------


async def list_artifacts(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str | None = None,
    artifact_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ArtifactListResponse:
    from sqlalchemy import func

    filters = [Artifact.project_id == project_id]
    if run_id is not None:
        filters.append(Artifact.run_id == run_id)
    if artifact_type is not None:
        filters.append(Artifact.artifact_type == artifact_type)

    count_result = await session.execute(select(func.count(Artifact.id)).where(*filters))
    total = count_result.scalar_one()

    artifacts_result = await session.execute(
        select(Artifact)
        .where(*filters)
        .order_by(Artifact.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    artifacts = list(artifacts_result.scalars().all())

    return ArtifactListResponse(
        items=[ArtifactResponse.model_validate(a) for a in artifacts],
        total=total,
    )


async def get_artifact(
    *, session: AsyncSession, project_id: str, artifact_id: str
) -> ArtifactResponse:
    result = await session.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.project_id == project_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise ArtifactNotFoundError(artifact_id)
    return ArtifactResponse.model_validate(artifact)


async def get_artifact_download(
    *, session: AsyncSession, project_id: str, artifact_id: str
) -> FileResponse:
    result = await session.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.project_id == project_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise ArtifactNotFoundError(artifact_id)

    file_path = Path(artifact.file_path)
    if not file_path.exists() or not file_path.is_file():
        raise ArtifactFileNotFoundError(artifact_id)

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


async def delete_artifact(*, session: AsyncSession, project_id: str, artifact_id: str) -> None:
    result = await session.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.project_id == project_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise ArtifactNotFoundError(artifact_id)

    file_path = Path(artifact.file_path)
    if file_path.exists():
        try:
            if file_path.is_dir():
                import shutil

                shutil.rmtree(file_path)
            else:
                file_path.unlink()
        except OSError:
            pass

    await session.delete(artifact)
