from __future__ import annotations

import os
from pathlib import Path

import yaml

from app.core.config import settings
from app.core.model_registry import MODEL_REGISTRY
from app.schemas.model_registry import (
    ModelRegistryEntryResponse,
    RegisterModelEntryRequest,
)

_MANIFEST_FILENAME = "model_registry.yaml"


def _manifest_path() -> Path:
    return settings.data_dir / _MANIFEST_FILENAME


def _seed_entries() -> list[ModelRegistryEntryResponse]:
    return [
        ModelRegistryEntryResponse(
            name=entry.name,
            source=entry.source,
            is_pinned=entry.is_pinned,
            params=entry.params,
            context=entry.context,
            license=entry.license,
        )
        for entry in MODEL_REGISTRY
    ]


def _load_manifest_entries() -> list[ModelRegistryEntryResponse] | None:
    path = _manifest_path()
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return None
    entries_raw = raw.get("entries")
    if not isinstance(entries_raw, list):
        return None
    return [ModelRegistryEntryResponse.model_validate(item) for item in entries_raw]


def _save_manifest_entries(entries: list[ModelRegistryEntryResponse]) -> None:
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": [entry.model_dump() for entry in entries]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    os.replace(tmp, path)


def list_entries() -> list[ModelRegistryEntryResponse]:
    """Return the merged registry list.

    The on-disk manifest is the source of truth once it exists. Until then the
    seed catalog in ``app.core.model_registry`` is returned so first-boot users
    see a populated registry without any setup step.
    """
    persisted = _load_manifest_entries()
    if persisted is None:
        return _seed_entries()
    return persisted


def register_entry(*, request: RegisterModelEntryRequest) -> ModelRegistryEntryResponse:
    """Append the entry to the manifest and persist atomically.

    First-time registration seeds the manifest from the in-memory defaults so
    the operator's seed catalog is preserved. If an entry with the same name
    already exists the new payload replaces it, so re-registering corrects a
    typo without orphaning the previous row.
    """
    entry = ModelRegistryEntryResponse(
        name=request.name,
        source=request.source,
        is_pinned=request.is_pinned,
        path=request.path,
        dtype=request.dtype,
    )
    current = list_entries()
    next_entries = [existing for existing in current if existing.name != entry.name]
    next_entries.append(entry)
    _save_manifest_entries(next_entries)
    return entry
