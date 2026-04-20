# Config Snapshot and Final Evaluation Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every run (a) persists an immutable YAML snapshot of its effective hyperparameters as an `Artifact` of type `config_snapshot`, viewable via a new Config tab; and (b) runs a structured final evaluation stage after training completes, emitting `final_eval_*` metrics distinct from mid-training callback evals.

**Architecture:** Backend: `orchestrator.create_run` writes `projects/<pid>/runs/<rid>/config.yaml` and inserts an `Artifact` row before dispatching the trainer subprocess. A new `run_service.get_config_snapshot` reads the file, diffs it against the parent `ConfigVersion`, and returns `{yaml, parentVersionId, diff}` through a new REST route. Trainer: the existing no-op stage 11 emit at `trainer.py:1294-1314` is replaced with a real `Trainer.evaluate()` call that emits metrics under `final_eval_*` keys. Frontend: a new Config tab renders the YAML plus diff panel; existing tab pattern in `runs-page.tsx` is extended.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async, pytest + httpx.AsyncClient; React 19, TanStack Query v5, shadcn Tabs, TypeScript strict.

---

## File Structure

**Backend — create:**
- `backend/app/schemas/run_observability.py` — `ConfigSnapshotResponse`, `ConfigDiff` Pydantic models (new module for run-level observability schemas so they don't pollute `artifact.py`)
- `backend/tests/test_config_snapshot.py` — integration tests for the new endpoint + orchestrator emission
- `backend/tests/test_final_eval_stage.py` — trainer-side tests for the final eval emission

**Backend — modify:**
- `backend/app/services/config_service.py` — expose `compute_config_diff(old_yaml, new_yaml) -> dict` (wrapper over existing `_compute_diff` with flattening); add `serialize_effective_config_yaml(raw_yaml: str) -> str`
- `backend/app/services/orchestrator.py` — in `create_run`, after the run/stage commit, write the config snapshot file and insert an Artifact row
- `backend/app/services/run_service.py` — new `get_config_snapshot(*, session, project_id, run_id) -> ConfigSnapshotResponse`
- `backend/app/api/routes/runs.py` — new route `GET /api/v1/projects/{project_id}/runs/{run_id}/config-snapshot`
- `backend/app/services/trainer.py` — replace the no-op stage 11 emit at lines 1294-1314 with a real final eval block

**Frontend — create:**
- `frontend/src/types/config-snapshot.ts` — `ConfigSnapshot`, `ConfigDiff` types
- `frontend/src/api/config-snapshot.ts` — `fetchConfigSnapshot` client function
- `frontend/src/hooks/useConfigSnapshot.ts` — TanStack Query hook
- `frontend/src/components/runs/config-snapshot-tab.tsx` — Config tab content

**Frontend — modify:**
- `frontend/src/pages/runs-page.tsx` — add Config tab trigger and content, wire selected run id

---

## Conventions for this plan

- Every code step shows the actual code. No "implement similar to…" placeholders.
- Every test step shows the actual assertion.
- Every commit step shows the exact files to stage.
- Backend tests follow the pattern in `backend/tests/test_projects.py` (in-memory SQLite + `httpx.AsyncClient` + dependency overrides).
- Frontend has no test suite established. This plan does not introduce one; frontend verification is manual via the running dev server at the end. Per project CLAUDE.md, when the first frontend test lands, its location sets the project convention — not in scope for this plan.
- **All commits use lowercase imperative with comma-separated changes per project git rules. No AI attribution.**
- **Run type checks after every backend and frontend modification task** per user CLAUDE.md.

---

## Part A — Config snapshot per run

### Task 1: Public config diff + effective YAML serialization helpers

**Files:**
- Modify: `backend/app/services/config_service.py`
- Test: `backend/tests/test_config_snapshot.py`

- [ ] **Step 1.1: Read current `config_service.py` to confirm `_compute_diff` signature and flattening behavior**

Run: `sed -n '220,260p' backend/app/services/config_service.py`

You're looking for whether `_compute_diff` flattens internally or expects pre-flattened input. The prior recon says inputs are dot-path-flattened dicts — verify.

- [ ] **Step 1.2: Write the failing test**

Create `backend/tests/test_config_snapshot.py` with:

```python
from __future__ import annotations

import pytest

from app.services.config_service import (
    compute_config_diff,
    serialize_effective_config_yaml,
)

_BASE_YAML = """\
project:
  name: p
  mode: single_user_local
training:
  learning_rate: 0.0002
  batch_size: 4
"""

_CHANGED_YAML = """\
project:
  name: p
  mode: single_user_local
training:
  learning_rate: 0.0003
  batch_size: 4
  epochs: 3
"""


def test_compute_config_diff_reports_changed_and_added_keys() -> None:
    diff = compute_config_diff(old_yaml=_BASE_YAML, new_yaml=_CHANGED_YAML)
    assert "training.learning_rate" in diff["changed"]
    assert diff["changed"]["training.learning_rate"] == {"old": 0.0002, "new": 0.0003}
    assert "training.epochs" in diff["added"]
    assert diff["added"]["training.epochs"] == 3
    assert diff["removed"] == {}


def test_serialize_effective_config_yaml_round_trips() -> None:
    out = serialize_effective_config_yaml(raw_yaml=_BASE_YAML)
    assert "project:" in out
    assert "learning_rate: 0.0002" in out
```

- [ ] **Step 1.3: Run the failing test**

Run: `cd backend && pytest tests/test_config_snapshot.py::test_compute_config_diff_reports_changed_and_added_keys -v`
Expected: ImportError / AttributeError — `compute_config_diff` doesn't exist yet.

- [ ] **Step 1.4: Implement the two helpers**

Add to `backend/app/services/config_service.py` (append at the bottom):

```python
import yaml


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def compute_config_diff(*, old_yaml: str, new_yaml: str) -> dict[str, Any]:
    old = _flatten(yaml.safe_load(old_yaml) or {})
    new = _flatten(yaml.safe_load(new_yaml) or {})
    return _compute_diff(old, new)


def serialize_effective_config_yaml(*, raw_yaml: str) -> str:
    from app.schemas.workbench_config import WorkbenchConfig

    raw = yaml.safe_load(raw_yaml)
    validated = WorkbenchConfig.model_validate(raw)
    return yaml.safe_dump(validated.model_dump(mode="json"), sort_keys=False)
```

**Note:** If an existing `_flatten` helper is already present in `config_service.py`, delete this one and call the existing one. Check first with `grep -n "def _flatten\|def flatten" backend/app/services/config_service.py`. If `_compute_diff` itself already flattens internally, remove the flatten calls in `compute_config_diff` and pass the raw parsed dicts directly.

- [ ] **Step 1.5: Run tests to verify pass**

Run: `cd backend && pytest tests/test_config_snapshot.py -v`
Expected: both tests PASS.

- [ ] **Step 1.6: Type check**

Run: `cd backend && python -m mypy app/services/config_service.py` (or `ruff check app/services/config_service.py` if mypy isn't configured).
Expected: no new errors.

- [ ] **Step 1.7: Commit**

```bash
git add backend/app/services/config_service.py backend/tests/test_config_snapshot.py
git commit -m "add: compute_config_diff and serialize_effective_config_yaml helpers in config_service"
```

---

### Task 2: Orchestrator writes config snapshot artifact on run start

**Files:**
- Modify: `backend/app/services/orchestrator.py` (in `create_run`, lines ~200–230)
- Test: `backend/tests/test_config_snapshot.py` (extend)

- [ ] **Step 2.1: Read `create_run` to confirm insertion point**

Run: `sed -n '147,242p' backend/app/services/orchestrator.py`

You're confirming:
- `session.commit()` line where run + stages are persisted (around line 202)
- Where `asyncio.create_task(_run_trainer_subprocess(...))` or equivalent dispatch happens (around line 232)
- How to access the project's `projects_dir` root. Look at existing checkpoint artifact insertion (`_record_artifact`) for the disk-write pattern.

- [ ] **Step 2.2: Confirm config version YAML access**

Run: `grep -n "yaml_blob\|config_yaml\|yaml_content" backend/app/models/config_version.py`

The column name matters for the next step (expect `yaml_blob`, but verify).

- [ ] **Step 2.3: Write the failing integration test**

Append to `backend/tests/test_config_snapshot.py`:

```python
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app


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
async def client(db_session, tmp_path, monkeypatch):
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "projects_dir", tmp_path)

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_create_run_writes_config_snapshot_artifact(
    client: AsyncClient,
    db_session,
    tmp_path: Path,
) -> None:
    project_resp = await client.post(
        "/api/v1/projects",
        json={"name": "snap-test", "description": ""},
    )
    assert project_resp.status_code == 201
    project = project_resp.json()
    project_id = project["id"]
    config_version_id = project["active_config_version_id"]

    run_resp = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"config_version_id": config_version_id, "name": "test-run"},
    )
    assert run_resp.status_code in (200, 201)
    run = run_resp.json()
    run_id = run["id"]

    expected_path = tmp_path / project_id / "runs" / run_id / "config.yaml"
    assert expected_path.exists(), f"config snapshot file not written at {expected_path}"

    from sqlalchemy import select

    from app.models.artifact import Artifact

    rows = (
        await db_session.execute(
            select(Artifact).where(
                Artifact.run_id == run_id,
                Artifact.artifact_type == "config_snapshot",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].file_path == str(expected_path)
    assert rows[0].is_retained == 1
```

- [ ] **Step 2.4: Run test to verify it fails**

Run: `cd backend && pytest tests/test_config_snapshot.py::test_create_run_writes_config_snapshot_artifact -v`
Expected: FAIL on `expected_path.exists()` — snapshot not yet written.

- [ ] **Step 2.5: Add config snapshot helper to orchestrator**

Open `backend/app/services/orchestrator.py`. Near the existing `_record_artifact` helper, add:

```python
from pathlib import Path

from app.core.config import settings
from app.services.config_service import serialize_effective_config_yaml


async def _write_config_snapshot(
    *,
    session: AsyncSession,
    run_id: str,
    project_id: str,
    config_yaml: str,
) -> None:
    run_dir = Path(settings.projects_dir) / project_id / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = run_dir / "config.yaml"
    effective_yaml = serialize_effective_config_yaml(raw_yaml=config_yaml)
    snapshot_path.write_text(effective_yaml, encoding="utf-8")

    artifact = Artifact(
        id=str(uuid.uuid4()),
        run_id=run_id,
        project_id=project_id,
        artifact_type="config_snapshot",
        file_path=str(snapshot_path),
        file_size_bytes=snapshot_path.stat().st_size,
        is_retained=1,
        created_at=datetime.now(UTC).isoformat(),
    )
    session.add(artifact)
    await session.commit()
```

Import `Artifact` and `uuid`, `datetime`, `UTC`, `AsyncSession` if not already.

- [ ] **Step 2.6: Call the helper from `create_run`**

In `create_run`, after the existing `session.commit()` that persists the run and before the trainer subprocess dispatch, add:

```python
await _write_config_snapshot(
    session=session,
    run_id=run.id,
    project_id=project_id,
    config_yaml=config_version.yaml_blob,
)
```

(Use the exact column name confirmed in step 2.2 — `yaml_blob` or whatever the recon showed.)

- [ ] **Step 2.7: Run test to verify pass**

Run: `cd backend && pytest tests/test_config_snapshot.py::test_create_run_writes_config_snapshot_artifact -v`
Expected: PASS.

- [ ] **Step 2.8: Run full test_config_snapshot suite and adjacent suites**

Run: `cd backend && pytest tests/test_config_snapshot.py tests/test_projects.py -v`
Expected: all PASS. (Snapshot addition must not break project/run creation.)

- [ ] **Step 2.9: Type check**

Run: `cd backend && python -m mypy app/services/orchestrator.py` (or `ruff check`).

- [ ] **Step 2.10: Commit**

```bash
git add backend/app/services/orchestrator.py backend/tests/test_config_snapshot.py
git commit -m "add: config snapshot artifact written on run start in orchestrator.create_run"
```

---

### Task 3: Response schema for config snapshot endpoint

**Files:**
- Create: `backend/app/schemas/run_observability.py`

- [ ] **Step 3.1: Write the schema**

Create `backend/app/schemas/run_observability.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigDiff(BaseModel):
    changed: dict[str, dict[str, Any]]
    added: dict[str, Any]
    removed: dict[str, Any]


class ConfigSnapshotResponse(BaseModel):
    run_id: str
    parent_config_version_id: str
    yaml: str
    diff: ConfigDiff
```

- [ ] **Step 3.2: Type check**

Run: `cd backend && python -m mypy app/schemas/run_observability.py`

- [ ] **Step 3.3: Commit**

```bash
git add backend/app/schemas/run_observability.py
git commit -m "add: ConfigSnapshotResponse and ConfigDiff pydantic schemas"
```

---

### Task 4: `run_service.get_config_snapshot` + REST endpoint

**Files:**
- Modify: `backend/app/services/run_service.py`
- Modify: `backend/app/api/routes/runs.py`
- Test: `backend/tests/test_config_snapshot.py` (extend)

- [ ] **Step 4.1: Read existing service function for patterns**

Run: `grep -n "def list_checkpoints\|def get_run" backend/app/services/run_service.py | head -20`
Run: `sed -n '/def list_checkpoints/,/^async def\|^def /p' backend/app/services/run_service.py | head -40`

You want the signature pattern and error-raising convention (`RunNotFoundError`).

- [ ] **Step 4.2: Write the failing endpoint test**

Append to `backend/tests/test_config_snapshot.py`:

```python
async def test_get_config_snapshot_returns_yaml_and_diff(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    project_resp = await client.post(
        "/api/v1/projects",
        json={"name": "diff-test", "description": ""},
    )
    project = project_resp.json()
    project_id = project["id"]
    cv_id = project["active_config_version_id"]
    run_resp = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"config_version_id": cv_id, "name": "r"},
    )
    run_id = run_resp.json()["id"]

    snap_resp = await client.get(
        f"/api/v1/projects/{project_id}/runs/{run_id}/config-snapshot"
    )
    assert snap_resp.status_code == 200
    body = snap_resp.json()
    assert body["run_id"] == run_id
    assert body["parent_config_version_id"] == cv_id
    assert "project:" in body["yaml"]
    assert "changed" in body["diff"]
    assert "added" in body["diff"]
    assert "removed" in body["diff"]


async def test_get_config_snapshot_returns_404_for_missing_run(
    client: AsyncClient,
) -> None:
    project_resp = await client.post(
        "/api/v1/projects",
        json={"name": "nope", "description": ""},
    )
    project_id = project_resp.json()["id"]
    resp = await client.get(
        f"/api/v1/projects/{project_id}/runs/does-not-exist/config-snapshot"
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "RUN_NOT_FOUND"
```

- [ ] **Step 4.3: Run failing test**

Run: `cd backend && pytest tests/test_config_snapshot.py::test_get_config_snapshot_returns_yaml_and_diff -v`
Expected: 404 (route doesn't exist yet).

- [ ] **Step 4.4: Implement the service function**

Append to `backend/app/services/run_service.py`:

```python
from pathlib import Path

from sqlalchemy import select

from app.models.artifact import Artifact
from app.models.config_version import ConfigVersion
from app.models.run import Run
from app.schemas.run_observability import ConfigDiff, ConfigSnapshotResponse
from app.services.config_service import compute_config_diff
from app.services.run_service_exceptions import RunNotFoundError


async def get_config_snapshot(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
) -> ConfigSnapshotResponse:
    run = (
        await session.execute(
            select(Run).where(Run.id == run_id, Run.project_id == project_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise RunNotFoundError(run_id)

    artifact = (
        await session.execute(
            select(Artifact).where(
                Artifact.run_id == run_id,
                Artifact.artifact_type == "config_snapshot",
            )
        )
    ).scalar_one_or_none()
    if artifact is None:
        raise RunNotFoundError(f"no config snapshot for run {run_id}")

    snapshot_yaml = Path(artifact.file_path).read_text(encoding="utf-8")

    parent = await session.get(ConfigVersion, run.config_version_id)
    parent_yaml = parent.yaml_blob if parent is not None else ""
    diff_dict = compute_config_diff(old_yaml=parent_yaml, new_yaml=snapshot_yaml)

    return ConfigSnapshotResponse(
        run_id=run_id,
        parent_config_version_id=run.config_version_id,
        yaml=snapshot_yaml,
        diff=ConfigDiff(**diff_dict),
    )
```

**Note:** If `RunNotFoundError` actually lives at a different import path (e.g. `app.services.run_service` itself), adjust the import. Run `grep -n "class RunNotFoundError" backend/app/services/` to find the truth.

- [ ] **Step 4.5: Implement the route**

Open `backend/app/api/routes/runs.py`. Add this handler next to `list_checkpoints`:

```python
from app.schemas.run_observability import ConfigSnapshotResponse


@router.get(
    "/{project_id}/runs/{run_id}/config-snapshot",
    response_model=ConfigSnapshotResponse,
)
async def get_run_config_snapshot(
    project_id: str,
    run_id: str,
    session: DbSession,
) -> ConfigSnapshotResponse:
    try:
        return await run_service.get_config_snapshot(
            session=session,
            project_id=project_id,
            run_id=run_id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
```

Add imports if needed: `ConfigSnapshotResponse`, confirm `RunNotFoundError` is already imported in this file (it is — used by `list_checkpoints`).

- [ ] **Step 4.6: Run the tests**

Run: `cd backend && pytest tests/test_config_snapshot.py -v`
Expected: all four tests PASS.

- [ ] **Step 4.7: Type check**

Run: `cd backend && python -m mypy app/services/run_service.py app/api/routes/runs.py`

- [ ] **Step 4.8: Commit**

```bash
git add backend/app/services/run_service.py backend/app/api/routes/runs.py backend/tests/test_config_snapshot.py
git commit -m "add: GET run config-snapshot endpoint with effective yaml and diff against parent config version"
```

---

### Task 5: Frontend types, API client, hook

**Files:**
- Create: `frontend/src/types/config-snapshot.ts`
- Create: `frontend/src/api/config-snapshot.ts`
- Create: `frontend/src/hooks/useConfigSnapshot.ts`

- [ ] **Step 5.1: Write the types**

Create `frontend/src/types/config-snapshot.ts`:

```typescript
export interface ConfigDiffEntry {
  readonly old: unknown;
  readonly new: unknown;
}

export interface ConfigDiff {
  readonly changed: Readonly<Record<string, ConfigDiffEntry>>;
  readonly added: Readonly<Record<string, unknown>>;
  readonly removed: Readonly<Record<string, unknown>>;
}

export interface ConfigSnapshot {
  readonly runId: string;
  readonly parentConfigVersionId: string;
  readonly yaml: string;
  readonly diff: ConfigDiff;
}
```

- [ ] **Step 5.2: Read the existing API client pattern**

Run: `sed -n '1,40p' frontend/src/api/artifacts.ts` (match the `fetchApi` usage and response mapping pattern).

- [ ] **Step 5.3: Write the API client**

Create `frontend/src/api/config-snapshot.ts`:

```typescript
import type { ConfigDiff, ConfigSnapshot } from "@/types/config-snapshot";
import { fetchApi } from "./client";

interface RawConfigSnapshot {
  readonly run_id: string;
  readonly parent_config_version_id: string;
  readonly yaml: string;
  readonly diff: ConfigDiff;
}

export async function fetchConfigSnapshot({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<ConfigSnapshot> {
  const raw = await fetchApi<RawConfigSnapshot>({
    path: `/projects/${projectId}/runs/${runId}/config-snapshot`,
  });
  return {
    runId: raw.run_id,
    parentConfigVersionId: raw.parent_config_version_id,
    yaml: raw.yaml,
    diff: raw.diff,
  };
}
```

- [ ] **Step 5.4: Write the hook**

Create `frontend/src/hooks/useConfigSnapshot.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import { fetchConfigSnapshot } from "@/api/config-snapshot";
import type { ConfigSnapshot } from "@/types/config-snapshot";

const CONFIG_SNAPSHOT_KEY = (projectId: string, runId: string) =>
  ["projects", projectId, "runs", runId, "config-snapshot"] as const;

export function useConfigSnapshot({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}) {
  return useQuery<ConfigSnapshot>({
    queryKey: CONFIG_SNAPSHOT_KEY(projectId, runId),
    queryFn: () => fetchConfigSnapshot({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}
```

- [ ] **Step 5.5: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 5.6: Commit**

```bash
git add frontend/src/types/config-snapshot.ts frontend/src/api/config-snapshot.ts frontend/src/hooks/useConfigSnapshot.ts
git commit -m "add: config snapshot types, api client, and tanstack query hook"
```

---

### Task 6: Config tab component + runs page integration

**Files:**
- Create: `frontend/src/components/runs/config-snapshot-tab.tsx`
- Modify: `frontend/src/pages/runs-page.tsx`

- [ ] **Step 6.1: Build the Config tab component**

Create `frontend/src/components/runs/config-snapshot-tab.tsx`:

```typescript
import { useConfigSnapshot } from "@/hooks/useConfigSnapshot";
import type { ConfigDiff } from "@/types/config-snapshot";

interface ConfigSnapshotTabProps {
  readonly projectId: string;
  readonly runId: string;
}

export function ConfigSnapshotTab({ projectId, runId }: ConfigSnapshotTabProps) {
  const { data, isLoading, error } = useConfigSnapshot({ projectId, runId });

  if (isLoading) {
    return <div className="text-xs text-muted-foreground">Loading config…</div>;
  }
  if (error !== null) {
    return (
      <div className="text-xs text-destructive">
        Failed to load config snapshot: {error instanceof Error ? error.message : "unknown"}
      </div>
    );
  }
  if (data === undefined) {
    return <div className="text-xs text-muted-foreground">No snapshot.</div>;
  }

  return (
    <div className="grid grid-cols-[1fr_1fr] gap-3">
      <ConfigYamlPane yaml={data.yaml} />
      <ConfigDiffPane diff={data.diff} />
    </div>
  );
}

function ConfigYamlPane({ yaml }: { readonly yaml: string }) {
  return (
    <pre className="overflow-auto rounded-md border border-border bg-muted/30 p-3 text-[11px] leading-relaxed font-mono">
      {yaml}
    </pre>
  );
}

function ConfigDiffPane({ diff }: { readonly diff: ConfigDiff }) {
  const hasChanges =
    Object.keys(diff.changed).length > 0 ||
    Object.keys(diff.added).length > 0 ||
    Object.keys(diff.removed).length > 0;

  if (!hasChanges) {
    return (
      <div className="rounded-md border border-border bg-muted/20 p-3 text-xs text-muted-foreground">
        No differences from parent config version.
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-md border border-border bg-muted/20 p-3 text-[11px] font-mono">
      {Object.entries(diff.changed).map(([key, entry]) => (
        <div key={`c-${key}`} className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">{key}</span>
          <span className="text-destructive">- {String(entry.old)}</span>
          <span className="text-emerald-600">+ {String(entry.new)}</span>
        </div>
      ))}
      {Object.entries(diff.added).map(([key, value]) => (
        <div key={`a-${key}`} className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">{key}</span>
          <span className="text-emerald-600">+ {String(value)}</span>
        </div>
      ))}
      {Object.entries(diff.removed).map(([key, value]) => (
        <div key={`r-${key}`} className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">{key}</span>
          <span className="text-destructive">- {String(value)}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 6.2: Read runs-page tabs block for splice point**

Run: `grep -n "TabsList\|TabsTrigger\|TabsContent" frontend/src/pages/runs-page.tsx | head -30`

Confirm the current tab ordering and find the line ranges for each `TabsTrigger` and `TabsContent`.

- [ ] **Step 6.3: Add the Config tab to runs-page.tsx**

In `frontend/src/pages/runs-page.tsx`:

1. Add import near other `@/components/runs/...` imports:

```typescript
import { ConfigSnapshotTab } from "@/components/runs/config-snapshot-tab";
```

2. Inside the `<TabsList>`, add a new trigger **before** the existing triggers (or after Timeline — pick whichever ordering feels right to the user; the plan defaults to inserting right before Checkpoints):

```tsx
<TabsTrigger value="config">Config</TabsTrigger>
```

3. Inside the tabs container, add the content:

```tsx
<TabsContent value="config" className="space-y-3">
  {activeProjectId && selectedRunId ? (
    <ConfigSnapshotTab projectId={activeProjectId} runId={selectedRunId} />
  ) : (
    <div className="text-xs text-muted-foreground">Select a run to view its config.</div>
  )}
</TabsContent>
```

Use the exact variable names already in scope in `runs-page.tsx` (confirmed via the earlier recon as `activeProjectId` and `selectedRunId`).

- [ ] **Step 6.4: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6.5: Lint**

Run: `cd frontend && npx eslint src/components/runs/config-snapshot-tab.tsx src/pages/runs-page.tsx`

Fix any violations surfaced. Do not add `eslint-disable` per project rules.

- [ ] **Step 6.6: Manual verification**

Ask the user to start the frontend dev server (per user CLAUDE.md, Claude doesn't start dev servers). User verifies:
1. Navigate to Runs page
2. Select an existing run (or create a new one)
3. Click Config tab
4. YAML pane shows resolved config; diff pane shows "No differences from parent config version" for a fresh run

- [ ] **Step 6.7: Commit**

```bash
git add frontend/src/components/runs/config-snapshot-tab.tsx frontend/src/pages/runs-page.tsx
git commit -m "add: config tab on runs page showing effective yaml and diff against parent version"
```

---

## Part B — Final evaluation stage

### Task 7: Trainer runs real final eval instead of no-op stage 11

**Files:**
- Modify: `backend/app/services/trainer.py` (lines ~1294–1314)
- Test: `backend/tests/test_final_eval_stage.py` (new)

- [ ] **Step 7.1: Read the current no-op block and surrounding context**

Run: `sed -n '1280,1340p' backend/app/services/trainer.py`

Confirm:
- `trainer.train(...)` return point
- How `final_metrics` is populated
- Whether `trainer.evaluate()` is even available (HF Trainer standard API)
- How the eval dataset is attached. Look for `eval_dataset=` in the file.

- [ ] **Step 7.2: Confirm the eval dataset attachment**

Run: `grep -n "eval_dataset" backend/app/services/trainer.py | head -10`

You want to see where `eval_dataset` is passed into the `Trainer(...)` constructor and whether it's conditionally set to `None` when no eval split is available.

- [ ] **Step 7.3: Write the failing test**

Create `backend/tests/test_final_eval_stage.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def test_final_eval_emits_stage_and_final_prefixed_metrics(capsys) -> None:
    """When a run completes successfully with an eval dataset, trainer emits
    stage_enter/stage_complete for 'evaluation' and final_eval_* metrics."""
    from app.services import trainer

    fake_trainer = MagicMock()
    fake_trainer.state.log_history = [{"loss": 0.5, "epoch": 1.0}]
    fake_trainer.state.global_step = 100
    fake_trainer.state.epoch = 1.0
    fake_trainer.evaluate.return_value = {"eval_loss": 0.42, "eval_runtime": 0.1}

    with patch.object(trainer, "_CANCEL_REQUESTED") as cancel_flag, \
         patch.object(trainer, "_is_main_process", return_value=True):
        cancel_flag.is_set.return_value = False

        trainer._emit_final_evaluation(hf_trainer=fake_trainer, has_eval_dataset=True)

    captured = capsys.readouterr().out.splitlines()
    events = [json.loads(line) for line in captured if line.strip()]
    types_in_order = [e["type"] for e in events]

    assert types_in_order.index("stage_enter") < types_in_order.index("metric")
    assert types_in_order.index("metric") < types_in_order.index("stage_complete")

    enter = next(e for e in events if e["type"] == "stage_enter")
    assert enter["stage_name"] == "evaluation"
    assert enter["stage_order"] == 11

    metric_event = next(e for e in events if e["type"] == "metric")
    assert "final_eval_loss" in metric_event["metrics"]
    assert metric_event["metrics"]["final_eval_loss"] == 0.42

    complete = next(e for e in events if e["type"] == "stage_complete")
    assert complete["stage_name"] == "evaluation"
    assert "skipped" not in complete["output_summary"].lower()


def test_final_eval_marks_stage_skipped_when_no_eval_dataset(capsys) -> None:
    from app.services import trainer

    fake_trainer = MagicMock()
    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_final_evaluation(hf_trainer=fake_trainer, has_eval_dataset=False)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    complete = next(e for e in events if e["type"] == "stage_complete")
    assert "skipped" in complete["output_summary"].lower()
    fake_trainer.evaluate.assert_not_called()
```

- [ ] **Step 7.4: Run failing test**

Run: `cd backend && pytest tests/test_final_eval_stage.py -v`
Expected: FAIL — `trainer._emit_final_evaluation` doesn't exist.

- [ ] **Step 7.5: Replace the no-op stage 11 block with real eval**

In `backend/app/services/trainer.py`, **replace** the existing no-op block (lines ~1300–1314, the one with comment `# Stage 11 is a reserved no-op placeholder in v4...`) with a call to a new helper.

First, **add the helper** above `def main(...)` (or wherever top-level functions live):

```python
def _emit_final_evaluation(
    *,
    hf_trainer: Any,
    has_eval_dataset: bool,
) -> None:
    if not _is_main_process():
        return
    import time

    start = time.perf_counter()
    _emit_stage_enter(stage_name="evaluation", stage_order=11)

    if not has_eval_dataset:
        duration_ms = int((time.perf_counter() - start) * 1000)
        _emit_stage_complete(
            stage_name="evaluation",
            duration_ms=duration_ms,
            output_summary="skipped; no eval dataset configured",
        )
        return

    eval_metrics = hf_trainer.evaluate()
    step = hf_trainer.state.global_step
    epoch = float(hf_trainer.state.epoch or 0.0)
    final_metrics: dict[str, float] = {}
    for key, value in eval_metrics.items():
        if not isinstance(value, (int, float)):
            continue
        final_key = f"final_{key}" if not key.startswith("final_") else key
        final_metrics[final_key] = float(value)

    if final_metrics:
        _emit_metric(step=step, epoch=epoch, metrics=final_metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    _emit_stage_complete(
        stage_name="evaluation",
        duration_ms=duration_ms,
        output_summary=(
            f"final eval at step {step}; "
            f"{len(final_metrics)} metrics emitted"
        ),
    )
```

Second, **replace the no-op block**. Today it looks like:

```python
# Stage 11 is a reserved no-op placeholder in v4...
_emit_stage_enter(stage_name="evaluation", stage_order=11)
_emit_stage_complete(
    stage_name="evaluation",
    duration_ms=0,
    output_summary="reserved no-op; v4 eval runs manually via UI or CLI",
)
```

Replace with:

```python
_emit_final_evaluation(
    hf_trainer=trainer,
    has_eval_dataset=eval_dataset is not None,
)
```

Use the actual variable name for the HF Trainer instance (likely `trainer`) and the actual variable holding the eval dataset (likely `eval_dataset` — confirm via step 7.2's grep).

- [ ] **Step 7.6: Run the tests**

Run: `cd backend && pytest tests/test_final_eval_stage.py -v`
Expected: both tests PASS.

- [ ] **Step 7.7: Run adjacent trainer tests**

Run: `cd backend && pytest tests/test_trainer_accelerate.py tests/test_trainer_rank_aware.py -v`
Expected: all PASS. Regression check for the callback-eval machinery.

- [ ] **Step 7.8: Type check**

Run: `cd backend && python -m mypy app/services/trainer.py`

- [ ] **Step 7.9: Commit**

```bash
git add backend/app/services/trainer.py backend/tests/test_final_eval_stage.py
git commit -m "update: trainer runs real final evaluation stage emitting final_ prefixed metrics, replaces no-op stage 11 placeholder"
```

---

### Task 8: Confirm callback_evaluation stage is untouched

**Files:**
- Test: `backend/tests/test_final_eval_stage.py` (extend)

- [ ] **Step 8.1: Add regression test**

Append to `backend/tests/test_final_eval_stage.py`:

```python
def test_callback_evaluation_stage_name_still_used_for_midtraining_evals(capsys) -> None:
    """Mid-training eval callback must still emit stage name 'callback_evaluation',
    not 'evaluation'. Final eval stage emission must never collide with it."""
    from app.services import trainer

    callback = trainer.WorkbenchCallback()
    fake_state = MagicMock()
    fake_state.global_step = 50
    fake_state.epoch = 0.5
    with patch.object(trainer, "_is_main_process", return_value=True):
        callback.on_evaluate(
            args=MagicMock(),
            state=fake_state,
            control=MagicMock(),
            metrics={"eval_loss": 0.7},
        )

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    stage_names = {e.get("stage_name") for e in events if "stage_name" in e}
    assert trainer._CALLBACK_EVAL_STAGE_NAME in stage_names
    assert "evaluation" not in stage_names, \
        "callback eval must NOT use reserved 'evaluation' stage name"
```

If `WorkbenchCallback` is not the exact class name or the signature differs, inspect with `grep -n "class.*Callback\|on_evaluate" backend/app/services/trainer.py` and adjust.

- [ ] **Step 8.2: Run the regression test**

Run: `cd backend && pytest tests/test_final_eval_stage.py::test_callback_evaluation_stage_name_still_used_for_midtraining_evals -v`
Expected: PASS.

- [ ] **Step 8.3: Commit**

```bash
git add backend/tests/test_final_eval_stage.py
git commit -m "add: regression test guarding callback_evaluation stage name against reserved evaluation name"
```

---

## Final sweep

### Task 9: Full-suite verification

- [ ] **Step 9.1: Run full backend test suite**

Run: `cd backend && pytest -v`
Expected: all tests PASS (existing + 7 new tests from this plan).

- [ ] **Step 9.2: Run full backend lint**

Run: `cd backend && ruff check app/ tests/`
Expected: no errors. Fix in place if any.

- [ ] **Step 9.3: Run frontend type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 9.4: Run frontend lint**

Run: `cd frontend && npx eslint src/`
Expected: no errors. Fix in place if any.

- [ ] **Step 9.5: Ask user for manual verification**

Request the user start the dev servers and confirm:
1. Create a new run on an existing project
2. Observe run completes with stage 11 "evaluation" marked completed
3. Observe `final_eval_loss` in the Metrics tab's "Other metrics" section (or in the run detail — will be auto-surfaced once Plan 3 lands; in this plan's scope, at minimum the DB should contain the `final_eval_*` metric points)
4. Click Config tab, see YAML and "No differences" on a fresh run
5. Edit the active config version, create a second run, confirm the Config tab shows the diff for the second run

If any check fails, open a new task capturing the regression; do not mark this plan complete.

- [ ] **Step 9.6: Final commit if any lint/type fixes were needed**

```bash
git add <files touched by step 9.2 or 9.4>
git commit -m "fix: address lint and type findings from final sweep"
```

---

## Acceptance criteria

- Creating a run produces `projects/<pid>/runs/<rid>/config.yaml` on disk and an `Artifact` row of type `config_snapshot`.
- `GET /api/v1/projects/{id}/runs/{run_id}/config-snapshot` returns `{run_id, parent_config_version_id, yaml, diff}` with valid diff against the parent `ConfigVersion.yaml_blob`.
- Runs page has a **Config** tab that renders the YAML and diff.
- After a training run completes, `stage_enter("evaluation", stage_order=11)` and `stage_complete("evaluation", ...)` are emitted with non-placeholder content.
- Emitted `final_eval_*` metric points are persisted to the `metric_points` table.
- The `callback_evaluation` stage name is unchanged and still emitted for mid-training evals.
- All backend tests pass (`pytest` green). Frontend `tsc` and `eslint` clean.

## Out of scope (covered by future plans)

- Dynamic metric UI surface ("Other metrics" section) — Plan 3.
- Frontend rendering of `final_eval_*` metrics is not required here; the data must be in the DB and the Config tab must work. Visual surfacing comes in Plan 3.
- Syntax highlighting for the YAML pane. `<pre>` + monospace is sufficient for v1.
- Downloading the snapshot as a file from the UI.
