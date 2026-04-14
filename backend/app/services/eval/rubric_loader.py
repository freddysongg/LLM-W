from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from deepdiff import DeepDiff
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rubric import Rubric as RubricModel
from app.models.rubric_version import RubricVersion
from app.schemas.rubric import Rubric

_CALIBRATION_STATUS_UNCALIBRATED = "uncalibrated"


@dataclass(frozen=True)
class RubricVersionRecord:
    """Boundary-safe snapshot of a persisted rubric_versions row."""

    id: str
    rubric_id: str
    version_number: int
    content_hash: str
    judge_model_pin: str
    calibration_status: str
    diff_from_prev: str | None
    created_at: str
    is_new: bool


async def load_rubric_from_yaml(
    *,
    yaml_path: Path,
    session: AsyncSession,
) -> RubricVersionRecord:
    """Load, validate, content-hash, and persist a rubric YAML to rubric_versions.

    Idempotent: if the content_hash matches an existing rubric_versions row
    for the same rubric, returns that row without creating a duplicate.
    Otherwise writes a new row with version_number = max(existing) + 1 and
    computes diff_from_prev via deepdiff.
    """
    raw_yaml_text = yaml_path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(raw_yaml_text.encode("utf-8")).hexdigest()

    parsed_yaml = yaml.safe_load(raw_yaml_text)
    if not isinstance(parsed_yaml, dict):
        raise ValueError(
            f"rubric YAML at {yaml_path} must deserialize to a mapping, "
            f"got {type(parsed_yaml).__name__}"
        )

    rubric = Rubric.model_validate(parsed_yaml)

    now_iso = datetime.now(UTC).isoformat()

    rubric_row = await _get_or_create_rubric(
        session=session,
        rubric=rubric,
        created_at=now_iso,
    )

    existing = await _find_existing_version(
        session=session,
        rubric_id=rubric_row.id,
        content_hash=content_hash,
    )
    if existing is not None:
        return _snapshot(version=existing, is_new=False)

    prev_version = await _get_latest_version(session=session, rubric_id=rubric_row.id)
    next_version_number = (prev_version.version_number + 1) if prev_version else 1
    diff_from_prev = _compute_diff_from_prev(
        prev_yaml_blob=prev_version.yaml_blob if prev_version else None,
        new_yaml=parsed_yaml,
    )

    new_version = RubricVersion(
        id=str(uuid.uuid4()),
        rubric_id=rubric_row.id,
        version_number=next_version_number,
        yaml_blob=raw_yaml_text,
        content_hash=content_hash,
        diff_from_prev=diff_from_prev,
        calibration_metrics=None,
        calibration_status=_CALIBRATION_STATUS_UNCALIBRATED,
        judge_model_pin=rubric.judge_model_pin,
        created_at=now_iso,
    )
    session.add(new_version)
    await session.commit()
    await session.refresh(new_version)

    return _snapshot(version=new_version, is_new=True)


async def _get_or_create_rubric(
    *,
    session: AsyncSession,
    rubric: Rubric,
    created_at: str,
) -> RubricModel:
    result = await session.execute(select(RubricModel).where(RubricModel.name == rubric.id))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    new_row = RubricModel(
        id=str(uuid.uuid4()),
        name=rubric.id,
        description=rubric.description,
        research_basis=json.dumps(rubric.research_basis),
        created_at=created_at,
    )
    session.add(new_row)
    await session.flush()
    return new_row


async def _find_existing_version(
    *,
    session: AsyncSession,
    rubric_id: str,
    content_hash: str,
) -> RubricVersion | None:
    result = await session.execute(
        select(RubricVersion).where(
            RubricVersion.rubric_id == rubric_id,
            RubricVersion.content_hash == content_hash,
        )
    )
    return result.scalar_one_or_none()


async def _get_latest_version(*, session: AsyncSession, rubric_id: str) -> RubricVersion | None:
    max_result = await session.execute(
        select(func.max(RubricVersion.version_number)).where(RubricVersion.rubric_id == rubric_id)
    )
    max_version = max_result.scalar_one_or_none()
    if max_version is None:
        return None

    row_result = await session.execute(
        select(RubricVersion).where(
            RubricVersion.rubric_id == rubric_id,
            RubricVersion.version_number == max_version,
        )
    )
    return row_result.scalar_one_or_none()


def _compute_diff_from_prev(
    *,
    prev_yaml_blob: str | None,
    new_yaml: dict[str, Any],
) -> str | None:
    if prev_yaml_blob is None:
        return None

    prev_parsed = yaml.safe_load(prev_yaml_blob)
    if not isinstance(prev_parsed, dict):
        prev_parsed = {}

    diff = DeepDiff(prev_parsed, new_yaml, ignore_order=True)
    if not diff:
        return None

    return diff.to_json()


def _snapshot(*, version: RubricVersion, is_new: bool) -> RubricVersionRecord:
    return RubricVersionRecord(
        id=version.id,
        rubric_id=version.rubric_id,
        version_number=version.version_number,
        content_hash=version.content_hash,
        judge_model_pin=version.judge_model_pin,
        calibration_status=version.calibration_status,
        diff_from_prev=version.diff_from_prev,
        created_at=version.created_at,
        is_new=is_new,
    )
