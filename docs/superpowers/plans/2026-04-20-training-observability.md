# Training Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each **Task** is a self-contained unit a subagent can own end-to-end.

**Goal:** Make the full training pipeline transparent — run-level hyperparameter snapshots, a real final-evaluation stage, dynamic metric discovery, run-history summaries, real resource capacity detection, per-checkpoint weight statistics, and enforced checkpoint retention.

**Architecture:** Five independent but sequenced parts. Part A persists per-run YAML and replaces the no-op final eval. Part B corrects resource capacity reporting. Part C surfaces custom metrics and per-run history. Part D wires existing retention logic into lifecycle hooks. Part E populates the Weights page with real architecture and per-checkpoint statistics.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async, Alembic, PyTorch + HuggingFace Trainer; React 19, TanStack Query v5, shadcn Tabs / Collapsible, TypeScript strict.

**Spec:** `docs/superpowers/specs/2026-04-20-training-observability-design.md` — read it before starting.

---

## File structure

### Backend — create
- `backend/app/schemas/run_observability.py` — `ConfigSnapshotResponse`, `ConfigDiff`, `RunSummaryResponse`, `MetricNamesResponse`
- `backend/app/schemas/weights.py` — `ModelProfileResponse`, `LayerProfile`, `WeightSnapshotResponse`, `LayerWeightStats`
- `backend/app/models/weight_snapshot.py` — `WeightSnapshot` SQLAlchemy model
- `backend/app/services/metrics_service.py` — `downsample_to_n(points, n)` utility + helpers
- `backend/alembic/versions/0004_is_best_and_weight_observability.py` — migration
- `backend/tests/test_config_snapshot.py`
- `backend/tests/test_final_eval_stage.py`
- `backend/tests/test_resource_capacity.py`
- `backend/tests/test_metric_names_endpoint.py`
- `backend/tests/test_run_summary_endpoint.py`
- `backend/tests/test_retention_hooks.py`
- `backend/tests/test_model_profile.py`
- `backend/tests/test_weight_snapshots.py`

### Backend — modify
- `backend/app/services/config_service.py` — public `compute_config_diff`, `serialize_config_yaml_snapshot`
- `backend/app/services/orchestrator.py` — `_write_config_snapshot`, retention lifecycle hooks, new event handlers (`model_profile`, `weight_stats`), metric-names service
- `backend/app/services/run_service.py` — `get_config_snapshot`, `list_metric_names`, `get_run_summary`, `get_model_profile`, `list_weight_snapshots`
- `backend/app/services/storage_manager.py` — rename `_apply_retention_for_run` → `apply_retention_for_run` (remove underscore); add `apply_retention_after_checkpoint(*, session, run_id)` convenience wrapper
- `backend/app/services/trainer.py` — `_emit_final_evaluation`, `_emit_model_profile`, `_emit_weight_stats`, best-eval tracking, `is_best_eval` in checkpoint events
- `backend/app/api/routes/runs.py` — five new endpoints (see Cross-Cutting)
- `backend/app/api/websocket/stream.py` — extend `_collect_system_resources` with totals; drop `gpu_utilization_pct`
- `backend/app/schemas/websocket.py` (or wherever `ResourceUpdatePayload` lives — if it doesn't exist, create it) — add `ram_total_mb`, `vram_total_mb`; remove `gpu_utilization_pct`
- `backend/app/schemas/workbench_config.py` — flip `delete_intermediates_after_completion` default to `False`
- `backend/app/models/model_profile.py` — add `layers_json` column
- `backend/app/models/artifact.py` — add `is_best` column
- `backend/app/models/__init__.py` (if re-exports exist) — add `WeightSnapshot`

### Frontend — create
- `frontend/src/types/config-snapshot.ts`
- `frontend/src/types/model-profile.ts`
- `frontend/src/types/weight-snapshot.ts`
- `frontend/src/types/run-summary.ts`
- `frontend/src/api/config-snapshot.ts`
- `frontend/src/api/metric-names.ts`
- `frontend/src/api/run-summary.ts`
- `frontend/src/api/model-profile.ts`
- `frontend/src/api/weight-snapshots.ts`
- `frontend/src/hooks/useConfigSnapshot.ts`
- `frontend/src/hooks/useMetricNames.ts`
- `frontend/src/hooks/useRunSummaries.ts`
- `frontend/src/hooks/useModelProfile.ts`
- `frontend/src/hooks/useWeightSnapshots.ts`
- `frontend/src/components/runs/config-snapshot-tab.tsx`
- `frontend/src/components/runs/other-metrics-section.tsx`
- `frontend/src/components/runs/run-history-sparkline.tsx`
- `frontend/src/components/weights/layer-tree.tsx`
- `frontend/src/components/weights/layer-weight-history.tsx`

### Frontend — modify
- `frontend/src/pages/runs-page.tsx` — add Config tab
- `frontend/src/pages/training-page.tsx` — populate `metricsByRun` via summary endpoint; render sparklines
- `frontend/src/pages/weights-page.tsx` — wire real model profile + weight snapshot data
- `frontend/src/components/runs/live-metrics-charts.tsx` — integrate `<OtherMetricsSection>` below canonical charts
- `frontend/src/components/runs/system-resource-monitor.tsx` — read totals from payload; remove GPU util panel
- `frontend/src/components/runs/checkpoint-list.tsx` — "BEST EVAL" and "Pruned" badges
- `frontend/src/types/websocket.ts` — `ResourceUpdatePayload` totals fields; new event types
- `frontend/src/types/artifact.ts` — add `is_best` to Checkpoint/Artifact if not there
- `frontend/src/hooks/useRunStream.ts` — handle `model_profile_ready`, `weight_stats_recorded`, `retention_applied`
- `frontend/src/stores/run-stream-store.ts` — accept extended resource payload shape

---

## Conventions

- **TDD:** tests first. Every task with backend code writes a failing test before implementation.
- **Bite-sized steps:** one action per step (2–5 minutes of work).
- **Commit cadence:** one commit per Task (occasionally split if a Task produces two clearly separable artifacts). Commit messages follow the project's `git-commit` skill rules (lowercase, imperative, commas between changes, no AI attribution).
- **Type checks after every backend modification Task:** `cd backend && python -m mypy <file>` or fallback `ruff check <file>`. Frontend: `cd frontend && npx tsc --noEmit` after any TS change.
- **Frontend testing:** no test suite established in the repo. All frontend verification is manual (via the dev server run by the user, since Claude does not start dev servers per user CLAUDE.md). When a frontend test is eventually added, its location sets the convention — not in scope here.
- **No placeholders:** every code step shows real code. No "similar to above".
- **Verify-then-adjust gates:** when a signature / import path might differ from recon, the step explicitly instructs a single `grep` or `sed` check first, with a fallback note. Not a placeholder.

### Cross-cutting schema additions (referenced from multiple tasks)

**New REST endpoints (all prefixed `/api/v1/projects/{project_id}/runs/`):**
| Method | Path | Task |
|---|---|---|
| GET | `.../{run_id}/config-snapshot` | 4 |
| GET | `.../{run_id}/metrics/names` | 11 |
| GET | `.../summary?ids=<csv>` (plural, on the project) | 13 |
| GET | `.../{run_id}/model-profile` | 25 |
| GET | `.../{run_id}/weight-snapshots?layer=<name>` | 26 |

**New WS message types** (published via `event_bus.publish` in orchestrator, consumed in `useRunStream.ts`):
| Event | Payload | Task |
|---|---|---|
| `model_profile_ready` | `{runId, modelProfileId, layerCount, totalParams, trainableParams}` | 24 |
| `weight_stats_recorded` | `{runId, step, layerCount}` | 24 |
| `retention_applied` | `{runId, kept: int[], pruned: int[]}` | 20 |

---

# Part A — Config snapshot and final evaluation stage

---

## Task 1 — Public config diff + effective YAML serialization helpers

**Files:**
- Modify: `backend/app/services/config_service.py`
- Test: `backend/tests/test_config_snapshot.py`

- [ ] **1.1 Read existing diff helper**

Run: `sed -n '220,260p' backend/app/services/config_service.py`

Confirm `_compute_diff` input expectations (flattened vs nested). Recon indicates it expects flattened dot-path dicts.

- [ ] **1.2 Check for existing flatten helper**

Run: `grep -n "def _flatten\|def flatten" backend/app/services/config_service.py`

If a helper exists, reuse it. Otherwise add one below.

- [ ] **1.3 Write failing tests**

Create `backend/tests/test_config_snapshot.py`:

```python
from __future__ import annotations

import pytest
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.services.config_service import (
    compute_config_diff,
    serialize_config_yaml_snapshot,
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


def test_compute_config_diff_reports_changed_and_added() -> None:
    diff = compute_config_diff(old_yaml=_BASE_YAML, new_yaml=_CHANGED_YAML)
    assert diff["changed"]["training.learning_rate"] == {"old": 0.0002, "new": 0.0003}
    assert diff["added"]["training.epochs"] == 3
    assert diff["removed"] == {}


def test_serialize_config_yaml_snapshot_round_trips() -> None:
    out = serialize_config_yaml_snapshot(raw_yaml=_BASE_YAML)
    assert "project:" in out
    assert "learning_rate: 0.0002" in out
```

- [ ] **1.4 Run failing test**

Run: `cd backend && pytest tests/test_config_snapshot.py -v`
Expected: ImportError on `compute_config_diff` / `serialize_config_yaml_snapshot`.

- [ ] **1.5 Implement helpers**

Append to `backend/app/services/config_service.py`:

```python
from typing import Any

import yaml


def _flatten_dict(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten_dict(v, key))
        else:
            out[key] = v
    return out


def compute_config_diff(*, old_yaml: str, new_yaml: str) -> dict[str, Any]:
    old = _flatten_dict(yaml.safe_load(old_yaml) or {})
    new = _flatten_dict(yaml.safe_load(new_yaml) or {})
    return _compute_diff(old, new)


def serialize_config_yaml_snapshot(*, raw_yaml: str) -> str:
    from app.schemas.workbench_config import WorkbenchConfig

    raw = yaml.safe_load(raw_yaml)
    validated = WorkbenchConfig.model_validate(raw)
    return yaml.safe_dump(validated.model_dump(mode="json"), sort_keys=False)
```

If `_flatten_dict` already exists under a different name (from step 1.2), delete this one and call the existing. If `_compute_diff` already flattens internally, pass raw dicts directly.

- [ ] **1.6 Run tests pass**

Run: `cd backend && pytest tests/test_config_snapshot.py -v`
Expected: both tests PASS.

- [ ] **1.7 Type check**

Run: `cd backend && ruff check app/services/config_service.py`

- [ ] **1.8 Commit**

```bash
git add backend/app/services/config_service.py backend/tests/test_config_snapshot.py
git commit -m "add: compute_config_diff and serialize_config_yaml_snapshot public helpers in config_service"
```

---

## Task 2 — Orchestrator writes config snapshot artifact on run start

**Files:**
- Modify: `backend/app/services/orchestrator.py`
- Test: `backend/tests/test_config_snapshot.py`

- [ ] **2.1 Read create_run and confirm insertion point**

Run: `sed -n '147,242p' backend/app/services/orchestrator.py`

Confirm the `session.commit()` line around line 202 and the trainer dispatch point around line 232. Also run `grep -n "yaml_blob\|config_yaml\|yaml_content" backend/app/models/config_version.py` to confirm the YAML column name.

- [ ] **2.2 Write failing integration test**

Append to `backend/tests/test_config_snapshot.py`:

```python
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
    project = (await client.post("/api/v1/projects", json={"name": "snap", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    expected = tmp_path / project["id"] / "runs" / run["id"] / "config.yaml"
    assert expected.exists()

    from sqlalchemy import select
    from app.models.artifact import Artifact

    rows = (
        await db_session.execute(
            select(Artifact).where(
                Artifact.run_id == run["id"],
                Artifact.artifact_type == "config_snapshot",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].file_path == str(expected)
    assert rows[0].is_retained == 1
```

- [ ] **2.3 Run failing test**

Run: `cd backend && pytest tests/test_config_snapshot.py::test_create_run_writes_config_snapshot_artifact -v`
Expected: FAIL on `expected.exists()`.

- [ ] **2.4 Add helper to orchestrator**

In `backend/app/services/orchestrator.py`, near `_record_artifact`, add:

```python
from pathlib import Path

from app.core.config import settings
from app.services.config_service import serialize_config_yaml_snapshot


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
    effective_yaml = serialize_config_yaml_snapshot(raw_yaml=config_yaml)
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

Verify `Artifact`, `uuid`, `datetime`, `UTC`, `AsyncSession` are already imported at module top.

- [ ] **2.5 Call helper from create_run**

After the existing `session.commit()` at ~line 202 and before the trainer subprocess dispatch at ~line 232:

```python
await _write_config_snapshot(
    session=session,
    run_id=run.id,
    project_id=project_id,
    config_yaml=config_version.yaml_blob,
)
```

Use the exact column name confirmed in step 2.1.

- [ ] **2.6 Run test**

Run: `cd backend && pytest tests/test_config_snapshot.py -v`
Expected: all PASS.

- [ ] **2.7 Regression sweep**

Run: `cd backend && pytest tests/test_projects.py tests/test_configs.py -v`
Expected: all PASS.

- [ ] **2.8 Type check + commit**

Run: `cd backend && ruff check app/services/orchestrator.py`

```bash
git add backend/app/services/orchestrator.py backend/tests/test_config_snapshot.py
git commit -m "add: config snapshot artifact written on run start in create_run"
```

---

## Task 3 — Response schemas for run observability

**Files:**
- Create: `backend/app/schemas/run_observability.py`

- [ ] **3.1 Write the schemas**

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


class MetricNamesResponse(BaseModel):
    metric_names: list[str]


class RunSummaryResponse(BaseModel):
    run_id: str
    status: str
    final_train_loss: float | None
    final_eval_loss: float | None
    wall_clock_ms: int
    step_count: int
    train_loss_sparkline: list[float]


class RunSummaryBatchResponse(BaseModel):
    runs: list[RunSummaryResponse]
```

- [ ] **3.2 Type check + commit**

Run: `cd backend && ruff check app/schemas/run_observability.py`

```bash
git add backend/app/schemas/run_observability.py
git commit -m "add: run observability pydantic schemas for config snapshot, metric names, and run summary"
```

---

## Task 4 — `GET /runs/{run_id}/config-snapshot` endpoint

**Files:**
- Modify: `backend/app/services/run_service.py`
- Modify: `backend/app/api/routes/runs.py`
- Test: `backend/tests/test_config_snapshot.py`

- [ ] **4.1 Confirm RunNotFoundError path**

Run: `grep -rn "class RunNotFoundError" backend/app/`

Note the module path. Expected: `backend/app/services/run_service.py` or `backend/app/services/run_service_exceptions.py`.

- [ ] **4.2 Write failing tests**

Append to `backend/tests/test_config_snapshot.py`:

```python
async def test_get_config_snapshot_returns_yaml_and_diff(client: AsyncClient) -> None:
    project = (await client.post("/api/v1/projects", json={"name": "d", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    resp = await client.get(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}/config-snapshot"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run["id"]
    assert body["parent_config_version_id"] == project["active_config_version_id"]
    assert "project:" in body["yaml"]
    assert "changed" in body["diff"]


async def test_get_config_snapshot_404_for_missing_run(client: AsyncClient) -> None:
    project = (await client.post("/api/v1/projects", json={"name": "n", "description": ""})).json()
    resp = await client.get(f"/api/v1/projects/{project['id']}/runs/bogus/config-snapshot")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"
```

- [ ] **4.3 Run failing tests**

Run: `cd backend && pytest tests/test_config_snapshot.py::test_get_config_snapshot_returns_yaml_and_diff -v`
Expected: 404.

- [ ] **4.4 Implement service function**

Append to `backend/app/services/run_service.py`:

```python
from pathlib import Path

from sqlalchemy import select

from app.models.artifact import Artifact
from app.models.config_version import ConfigVersion
from app.schemas.run_observability import ConfigDiff, ConfigSnapshotResponse
from app.services.config_service import compute_config_diff


async def get_config_snapshot(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
) -> ConfigSnapshotResponse:
    run = await get_run(session=session, run_id=run_id, project_id=project_id)

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

- [ ] **4.5 Implement route**

In `backend/app/api/routes/runs.py`, next to `list_checkpoints`:

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

- [ ] **4.6 Run tests**

Run: `cd backend && pytest tests/test_config_snapshot.py -v`
Expected: all PASS.

- [ ] **4.7 Type check + commit**

Run: `cd backend && ruff check app/services/run_service.py app/api/routes/runs.py`

```bash
git add backend/app/services/run_service.py backend/app/api/routes/runs.py backend/tests/test_config_snapshot.py
git commit -m "add: get run config-snapshot endpoint returning effective yaml and diff against parent version"
```

---

## Task 5 — Frontend config snapshot types, API, hook

**Files:**
- Create: `frontend/src/types/config-snapshot.ts`
- Create: `frontend/src/api/config-snapshot.ts`
- Create: `frontend/src/hooks/useConfigSnapshot.ts`

- [ ] **5.1 Write types**

`frontend/src/types/config-snapshot.ts`:

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

- [ ] **5.2 Write API client**

`frontend/src/api/config-snapshot.ts`:

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

- [ ] **5.3 Write hook**

`frontend/src/hooks/useConfigSnapshot.ts`:

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

- [ ] **5.4 Type check + commit**

Run: `cd frontend && npx tsc --noEmit`

```bash
git add frontend/src/types/config-snapshot.ts frontend/src/api/config-snapshot.ts frontend/src/hooks/useConfigSnapshot.ts
git commit -m "add: config snapshot types, api client, and tanstack query hook"
```

---

## Task 6 — Config tab component + runs-page integration

**Files:**
- Create: `frontend/src/components/runs/config-snapshot-tab.tsx`
- Modify: `frontend/src/pages/runs-page.tsx`

- [ ] **6.1 Build component**

`frontend/src/components/runs/config-snapshot-tab.tsx`:

```tsx
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

- [ ] **6.2 Find tabs block**

Run: `grep -n "TabsList\|TabsTrigger\|TabsContent" frontend/src/pages/runs-page.tsx | head -30`

- [ ] **6.3 Add Config tab**

In `frontend/src/pages/runs-page.tsx`:

1. Add import:

```typescript
import { ConfigSnapshotTab } from "@/components/runs/config-snapshot-tab";
```

2. Inside `<TabsList>`, insert before Checkpoints:

```tsx
<TabsTrigger value="config">Config</TabsTrigger>
```

3. Inside tabs container:

```tsx
<TabsContent value="config" className="space-y-3">
  {activeProjectId && selectedRunId ? (
    <ConfigSnapshotTab projectId={activeProjectId} runId={selectedRunId} />
  ) : (
    <div className="text-xs text-muted-foreground">Select a run to view its config.</div>
  )}
</TabsContent>
```

Confirm variable names with `grep -n "activeProjectId\|selectedRunId" frontend/src/pages/runs-page.tsx | head -5`.

- [ ] **6.4 Type check + lint**

Run: `cd frontend && npx tsc --noEmit && npx eslint src/components/runs/config-snapshot-tab.tsx src/pages/runs-page.tsx`

- [ ] **6.5 Commit**

```bash
git add frontend/src/components/runs/config-snapshot-tab.tsx frontend/src/pages/runs-page.tsx
git commit -m "add: config tab on runs page showing effective yaml and diff against parent config version"
```

---

## Task 7 — Trainer runs real final eval instead of no-op stage 11

**Files:**
- Modify: `backend/app/services/trainer.py` (~lines 1294–1314)
- Test: `backend/tests/test_final_eval_stage.py` (new)

- [ ] **7.1 Read current no-op block + eval dataset wiring**

Run: `sed -n '1280,1340p' backend/app/services/trainer.py`
Run: `grep -n "eval_dataset\s*=" backend/app/services/trainer.py | head -10`

You want the variable name holding the eval dataset and whether it's conditionally None.

- [ ] **7.2 Write failing tests**

Create `backend/tests/test_final_eval_stage.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def test_final_eval_emits_stage_and_final_prefixed_metrics(capsys) -> None:
    from app.services import trainer

    fake = MagicMock()
    fake.state.log_history = [{"loss": 0.5, "epoch": 1.0}]
    fake.state.global_step = 100
    fake.state.epoch = 1.0
    fake.evaluate.return_value = {"eval_loss": 0.42, "eval_runtime": 0.1}

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_final_evaluation(hf_trainer=fake, has_eval_dataset=True)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    types_in_order = [e["type"] for e in events]
    assert types_in_order.index("stage_enter") < types_in_order.index("metric")
    assert types_in_order.index("metric") < types_in_order.index("stage_complete")

    enter = next(e for e in events if e["type"] == "stage_enter")
    assert enter["stage_name"] == "evaluation"
    assert enter["stage_order"] == 11

    metric_event = next(e for e in events if e["type"] == "metric")
    assert metric_event["metrics"]["final_eval_loss"] == 0.42

    complete = next(e for e in events if e["type"] == "stage_complete")
    assert "skipped" not in complete["output_summary"].lower()


def test_final_eval_marks_stage_skipped_when_no_eval_dataset(capsys) -> None:
    from app.services import trainer

    fake = MagicMock()
    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_final_evaluation(hf_trainer=fake, has_eval_dataset=False)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    complete = next(e for e in events if e["type"] == "stage_complete")
    assert "skipped" in complete["output_summary"].lower()
    fake.evaluate.assert_not_called()


def test_callback_evaluation_stage_name_still_used(capsys) -> None:
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
    assert "evaluation" not in stage_names
```

- [ ] **7.3 Run failing tests**

Run: `cd backend && pytest tests/test_final_eval_stage.py -v`
Expected: AttributeError on `_emit_final_evaluation`.

- [ ] **7.4 Add helper function**

In `backend/app/services/trainer.py`, above `def main(`:

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
        final_key = key if key.startswith("final_") else f"final_{key}"
        final_metrics[final_key] = float(value)

    if final_metrics:
        _emit_metric(step=step, epoch=epoch, metrics=final_metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    _emit_stage_complete(
        stage_name="evaluation",
        duration_ms=duration_ms,
        output_summary=f"final eval at step {step}; {len(final_metrics)} metrics emitted",
    )
```

- [ ] **7.5 Replace the no-op block**

At trainer.py lines ~1300–1314, replace:

```python
# Stage 11 is a reserved no-op placeholder in v4...
_emit_stage_enter(stage_name="evaluation", stage_order=11)
_emit_stage_complete(
    stage_name="evaluation",
    duration_ms=0,
    output_summary="reserved no-op; v4 eval runs manually via UI or CLI",
)
```

With:

```python
_emit_final_evaluation(
    hf_trainer=trainer,
    has_eval_dataset=eval_dataset is not None,
)
```

Use the actual variable names (confirmed in step 7.1).

- [ ] **7.6 Run tests pass**

Run: `cd backend && pytest tests/test_final_eval_stage.py tests/test_trainer_accelerate.py tests/test_trainer_rank_aware.py -v`
Expected: all PASS.

- [ ] **7.7 Type check + commit**

Run: `cd backend && ruff check app/services/trainer.py`

```bash
git add backend/app/services/trainer.py backend/tests/test_final_eval_stage.py
git commit -m "update: trainer runs real final evaluation stage emitting final prefixed metrics, replaces reserved no-op"
```

---

# Part B — Resource capacity detection

---

## Task 8 — Extend `_collect_system_resources` with totals, drop GPU util

**Files:**
- Modify: `backend/app/api/websocket/stream.py`
- Modify: `backend/app/schemas/websocket.py` (or the file defining `ResourceUpdatePayload` — verify first)
- Test: `backend/tests/test_resource_capacity.py`

- [ ] **8.1 Locate ResourceUpdatePayload**

Run: `grep -rn "ResourceUpdatePayload\|resource_update" backend/app/schemas/`
Run: `grep -rn "gpu_utilization_pct" backend/app/`

Confirm the payload's canonical definition. If no Pydantic model exists today (events are raw dicts), declare it in `backend/app/schemas/websocket.py`.

- [ ] **8.2 Write failing test**

Create `backend/tests/test_resource_capacity.py`:

```python
from __future__ import annotations

import pytest

from app.api.websocket.stream import _collect_system_resources


def test_collect_system_resources_includes_ram_total() -> None:
    payload = _collect_system_resources()
    assert "ram_total_mb" in payload
    assert payload["ram_total_mb"] > 0
    assert payload["ram_used_mb"] <= payload["ram_total_mb"]


def test_collect_system_resources_has_vram_total_field() -> None:
    payload = _collect_system_resources()
    assert "vram_total_mb" in payload
    # None is acceptable on non-CUDA platforms (MPS/CPU)


def test_collect_system_resources_drops_gpu_utilization_pct() -> None:
    payload = _collect_system_resources()
    assert "gpu_utilization_pct" not in payload
```

- [ ] **8.3 Run failing tests**

Run: `cd backend && pytest tests/test_resource_capacity.py -v`
Expected: KeyError / assertion failures.

- [ ] **8.4 Update `_collect_system_resources`**

In `backend/app/api/websocket/stream.py`, replace the function body:

```python
def _collect_system_resources() -> dict[str, float | None]:
    cpu_pct = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()

    gpu_memory_used_mb = 0.0
    vram_total_mb: float | None = None

    try:
        import torch

        if torch.cuda.is_available():
            gpu_memory_used_mb = torch.cuda.memory_allocated() / (1024 * 1024)
            vram_total_mb = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
        elif torch.backends.mps.is_available():
            gpu_memory_used_mb = torch.mps.current_allocated_memory() / (1024 * 1024)
    except Exception:  # noqa: BLE001 — torch not installed or device unavailable
        pass

    return {
        "gpu_memory_used_mb": gpu_memory_used_mb,
        "vram_total_mb": vram_total_mb,
        "cpu_pct": cpu_pct,
        "ram_used_mb": ram.used / (1024 * 1024),
        "ram_total_mb": ram.total / (1024 * 1024),
    }
```

- [ ] **8.5 Create/update `ResourceUpdatePayload`**

Recon confirmed no Pydantic class exists today — events are raw dicts. Create the schema at `backend/app/schemas/websocket.py` (if the file exists, append; otherwise create):

```python
# backend/app/schemas/websocket.py
from pydantic import BaseModel


class ResourceUpdatePayload(BaseModel):
    gpu_memory_used_mb: float
    vram_total_mb: float | None
    cpu_pct: float
    ram_used_mb: float
    ram_total_mb: float
```

If an existing `ResourceUpdatePayload` shows up (run `grep -rn "class ResourceUpdatePayload" backend/`) — update in place: drop `gpu_utilization_pct`, add the two totals.

- [ ] **8.6 Run tests**

Run: `cd backend && pytest tests/test_resource_capacity.py -v`
Expected: all PASS.

- [ ] **8.7 Type check + commit**

Run: `cd backend && ruff check app/api/websocket/stream.py app/schemas/websocket.py`

```bash
git add backend/app/api/websocket/stream.py backend/app/schemas/websocket.py backend/tests/test_resource_capacity.py
git commit -m "update: emit ram and vram totals in resource_update payload, drop gpu_utilization_pct"
```

---

## Task 9 — Frontend reads real totals, removes GPU util panel

**Files:**
- Modify: `frontend/src/types/websocket.ts`
- Modify: `frontend/src/hooks/useRunStream.ts`
- Modify: `frontend/src/stores/run-stream-store.ts`
- Modify: `frontend/src/components/runs/system-resource-monitor.tsx`

- [ ] **9.1 Update TS payload type**

In `frontend/src/types/websocket.ts`, modify the `ResourceUpdatePayload` interface:

```typescript
export interface ResourceUpdatePayload {
  readonly gpuMemoryUsedMb: number;
  readonly vramTotalMb: number | null;
  readonly cpuPct: number;
  readonly ramUsedMb: number;
  readonly ramTotalMb: number;
}
```

Remove `gpuUtilizationPct` field.

- [ ] **9.2 Update store shape**

In `frontend/src/stores/run-stream-store.ts`, find the `SystemResources` type and update:

```typescript
interface SystemResources {
  readonly gpuMemoryUsedMb: number;
  readonly vramTotalMb: number | null;
  readonly cpuPct: number;
  readonly ramUsedMb: number;
  readonly ramTotalMb: number;
}
```

Remove `gpuUtilizationPct` field throughout the store.

- [ ] **9.3 Update `useRunStream.ts` resource handler**

In `frontend/src/hooks/useRunStream.ts`:

```typescript
if (envelope.event === "resource_update") {
  const payload = envelope.payload as ResourceUpdatePayload;
  setSystemResources({
    gpuMemoryUsedMb: payload.gpuMemoryUsedMb,
    vramTotalMb: payload.vramTotalMb,
    cpuPct: payload.cpuPct,
    ramUsedMb: payload.ramUsedMb,
    ramTotalMb: payload.ramTotalMb,
  });
}
```

- [ ] **9.4 Rewrite `SystemResourceMonitor`**

In `frontend/src/components/runs/system-resource-monitor.tsx`:

1. **Remove** `VRAM_TOTAL_GB_FALLBACK` and `RAM_TOTAL_GB_FALLBACK` constants.
2. **Remove** the GPU utilization tile entirely.
3. **Read real totals** from props/store:

```tsx
interface SystemResourceMonitorProps {
  readonly resources: SystemResources | null;
}

export function SystemResourceMonitor({ resources }: SystemResourceMonitorProps) {
  if (resources === null) {
    return <div className="text-xs text-muted-foreground">Awaiting resources…</div>;
  }

  const vramPct =
    resources.vramTotalMb !== null && resources.vramTotalMb > 0
      ? (resources.gpuMemoryUsedMb / resources.vramTotalMb) * 100
      : null;
  const ramPct = (resources.ramUsedMb / resources.ramTotalMb) * 100;

  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
      <ResourceTile
        label="VRAM"
        used={formatGb(resources.gpuMemoryUsedMb)}
        total={
          resources.vramTotalMb !== null
            ? formatGb(resources.vramTotalMb)
            : "unavailable"
        }
        pct={vramPct}
        hint={
          resources.vramTotalMb === null
            ? "VRAM total unavailable on this platform (MPS/CPU)"
            : null
        }
      />
      <ResourceTile
        label="RAM"
        used={formatGb(resources.ramUsedMb)}
        total={formatGb(resources.ramTotalMb)}
        pct={ramPct}
        hint={null}
      />
      <ResourceTile label="CPU" used={`${resources.cpuPct.toFixed(0)}%`} total={null} pct={resources.cpuPct} hint={null} />
    </div>
  );
}

function formatGb(mb: number): string {
  return `${(mb / 1024).toFixed(1)} GB`;
}

interface ResourceTileProps {
  readonly label: string;
  readonly used: string;
  readonly total: string | null;
  readonly pct: number | null;
  readonly hint: string | null;
}

function ResourceTile({ label, used, total, pct, hint }: ResourceTileProps) {
  return (
    <div className="rounded-md border border-border bg-muted/20 p-3">
      <div className="flex items-baseline justify-between text-[11px] font-mono uppercase tracking-wider">
        <span className="text-muted-foreground">{label}</span>
        <span className="text-foreground">
          {used}
          {total !== null ? <span className="text-muted-foreground"> / {total}</span> : null}
        </span>
      </div>
      {pct !== null ? (
        <div className="mt-2 h-1 rounded bg-muted">
          <div className="h-full rounded bg-foreground" style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
        </div>
      ) : null}
      {hint !== null ? (
        <div className="mt-1 text-[10px] text-muted-foreground">{hint}</div>
      ) : null}
    </div>
  );
}
```

Update the export/import surface to remove any remaining GPU utilization references.

- [ ] **9.5 Type check**

Run: `cd frontend && npx tsc --noEmit`
Fix any remaining `gpuUtilizationPct` references.

- [ ] **9.6 Commit**

```bash
git add frontend/src/types/websocket.ts frontend/src/hooks/useRunStream.ts frontend/src/stores/run-stream-store.ts frontend/src/components/runs/system-resource-monitor.tsx
git commit -m "update: system resource monitor reads real ram and vram totals from backend, removes gpu utilization panel"
```

---

# Part C — Dynamic metrics + history summaries

---

## Task 10 — `GET /runs/{run_id}/metrics/names` endpoint

**Files:**
- Modify: `backend/app/services/run_service.py`
- Modify: `backend/app/api/routes/runs.py`
- Test: `backend/tests/test_metric_names_endpoint.py`

- [ ] **10.1 Write failing test**

Create `backend/tests/test_metric_names_endpoint.py`:

```python
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.metric_point import MetricPoint


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


async def _make_run(client: AsyncClient) -> tuple[str, str]:
    project = (await client.post("/api/v1/projects", json={"name": "m", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()
    return project["id"], run["id"]


async def test_metric_names_returns_distinct(client: AsyncClient, db_session) -> None:
    project_id, run_id = await _make_run(client)
    import uuid
    from datetime import UTC, datetime

    for name in ["train_loss", "train_loss", "eval_loss", "custom_metric"]:
        db_session.add(MetricPoint(
            id=str(uuid.uuid4()),
            run_id=run_id,
            step=1,
            epoch=0.0,
            metric_name=name,
            metric_value=0.1,
            stage_name=None,
            recorded_at=datetime.now(UTC).isoformat(),
        ))
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project_id}/runs/{run_id}/metrics/names")
    assert resp.status_code == 200
    names = resp.json()["metric_names"]
    assert set(names) == {"train_loss", "eval_loss", "custom_metric"}


async def test_metric_names_empty_for_new_run(client: AsyncClient) -> None:
    project_id, run_id = await _make_run(client)
    resp = await client.get(f"/api/v1/projects/{project_id}/runs/{run_id}/metrics/names")
    assert resp.status_code == 200
    assert resp.json()["metric_names"] == []
```

- [ ] **10.2 Run failing test**

Run: `cd backend && pytest tests/test_metric_names_endpoint.py -v`
Expected: 404.

- [ ] **10.3 Implement service function**

Append to `backend/app/services/run_service.py`:

```python
from sqlalchemy import distinct

from app.models.metric_point import MetricPoint
from app.schemas.run_observability import MetricNamesResponse


async def list_metric_names(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
) -> MetricNamesResponse:
    await get_run(session=session, run_id=run_id, project_id=project_id)
    result = await session.execute(
        select(distinct(MetricPoint.metric_name))
        .where(MetricPoint.run_id == run_id)
        .order_by(MetricPoint.metric_name)
    )
    names = [row[0] for row in result.all()]
    return MetricNamesResponse(metric_names=names)
```

- [ ] **10.4 Implement route**

In `backend/app/api/routes/runs.py`:

```python
from app.schemas.run_observability import MetricNamesResponse


@router.get(
    "/{project_id}/runs/{run_id}/metrics/names",
    response_model=MetricNamesResponse,
)
async def list_run_metric_names(
    project_id: str,
    run_id: str,
    session: DbSession,
) -> MetricNamesResponse:
    try:
        return await run_service.list_metric_names(
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

- [ ] **10.5 Run tests + type check**

Run: `cd backend && pytest tests/test_metric_names_endpoint.py -v && ruff check app/services/run_service.py app/api/routes/runs.py`

- [ ] **10.6 Commit**

```bash
git add backend/app/services/run_service.py backend/app/api/routes/runs.py backend/tests/test_metric_names_endpoint.py
git commit -m "add: metric names endpoint returning distinct metric name list per run"
```

---

## Task 11 — "Other metrics" collapsed section

**Files:**
- Create: `frontend/src/types/metric-names.ts`
- Create: `frontend/src/api/metric-names.ts`
- Create: `frontend/src/hooks/useMetricNames.ts`
- Create: `frontend/src/components/runs/other-metrics-section.tsx`
- Modify: `frontend/src/components/runs/live-metrics-charts.tsx`

- [ ] **11.1 Types**

`frontend/src/types/metric-names.ts`:

```typescript
export interface MetricNames {
  readonly metricNames: ReadonlyArray<string>;
}
```

- [ ] **11.2 API client**

`frontend/src/api/metric-names.ts`:

```typescript
import type { MetricNames } from "@/types/metric-names";
import { fetchApi } from "./client";

interface RawMetricNames {
  readonly metric_names: ReadonlyArray<string>;
}

export async function fetchMetricNames({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<MetricNames> {
  const raw = await fetchApi<RawMetricNames>({
    path: `/projects/${projectId}/runs/${runId}/metrics/names`,
  });
  return { metricNames: raw.metric_names };
}
```

- [ ] **11.3 Hook**

`frontend/src/hooks/useMetricNames.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import { fetchMetricNames } from "@/api/metric-names";
import type { MetricNames } from "@/types/metric-names";

export const METRIC_NAMES_KEY = (projectId: string, runId: string) =>
  ["projects", projectId, "runs", runId, "metrics", "names"] as const;

export function useMetricNames({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}) {
  return useQuery<MetricNames>({
    queryKey: METRIC_NAMES_KEY(projectId, runId),
    queryFn: () => fetchMetricNames({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}
```

- [ ] **11.4 Other metrics section component**

`frontend/src/components/runs/other-metrics-section.tsx`:

```tsx
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { Sparkline } from "@/components/shared/sparkline";
import { ChartBox } from "@/components/charts/chart-box";
import { useMetricNames } from "@/hooks/useMetricNames";
import type { MetricPoint } from "@/types/run";

const CANONICAL_METRICS: ReadonlySet<string> = new Set([
  "train_loss",
  "eval_loss",
  "grad_norm",
  "learning_rate",
]);

interface OtherMetricsSectionProps {
  readonly projectId: string;
  readonly runId: string;
  readonly metricPoints: ReadonlyArray<MetricPoint>;
}

export function OtherMetricsSection({
  projectId,
  runId,
  metricPoints,
}: OtherMetricsSectionProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedName, setExpandedName] = useState<string | null>(null);
  const { data } = useMetricNames({ projectId, runId });

  const otherNames = (data?.metricNames ?? []).filter(
    (name) => !CANONICAL_METRICS.has(name),
  );

  if (otherNames.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 rounded-md border border-border bg-muted/10">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-[11px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
      >
        {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Other metrics ({otherNames.length})
      </button>
      {isOpen ? (
        <div className="divide-y divide-border">
          {otherNames.map((name) => (
            <OtherMetricRow
              key={name}
              name={name}
              expanded={expandedName === name}
              onToggle={() =>
                setExpandedName((current) => (current === name ? null : name))
              }
              metricPoints={metricPoints}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

interface OtherMetricRowProps {
  readonly name: string;
  readonly expanded: boolean;
  readonly onToggle: () => void;
  readonly metricPoints: ReadonlyArray<MetricPoint>;
}

function OtherMetricRow({ name, expanded, onToggle, metricPoints }: OtherMetricRowProps) {
  const series = metricPoints
    .filter((p) => p.metricName === name)
    .sort((a, b) => a.step - b.step);
  const values = series.map((p) => p.metricValue);
  const latest = values.length > 0 ? values[values.length - 1] : null;

  return (
    <div className="px-3 py-2">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 text-left"
      >
        <span className="flex-1 font-mono text-xs text-foreground">{name}</span>
        {latest !== null ? (
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {latest.toFixed(4)}
          </span>
        ) : null}
        <Sparkline data={values} className="h-6 w-24" />
      </button>
      {expanded && series.length > 0 ? (
        <div className="mt-2">
          <ChartBox
            title={name}
            data={series.map((p) => ({ x: p.step, y: p.metricValue }))}
            color="oklch(0.70 0.12 200)"
          />
        </div>
      ) : null}
    </div>
  );
}
```

If `ChartBox` props differ, adjust by reading `grep -n "interface ChartBoxProps\|type ChartBoxProps" frontend/src/components/charts/chart-box.tsx`.

- [ ] **11.5 Integrate into LiveMetricsCharts**

In `frontend/src/components/runs/live-metrics-charts.tsx`, at the bottom of the render, add:

```tsx
<OtherMetricsSection
  projectId={projectId}
  runId={runId}
  metricPoints={metricPoints}
/>
```

Add `projectId` and `runId` as required props of `LiveMetricsCharts`. Update the component interface and all call sites.

- [ ] **11.6 Type check**

Run: `cd frontend && npx tsc --noEmit`
Fix any call-site compilation errors from the new required props.

- [ ] **11.7 Commit**

```bash
git add frontend/src/types/metric-names.ts frontend/src/api/metric-names.ts frontend/src/hooks/useMetricNames.ts frontend/src/components/runs/other-metrics-section.tsx frontend/src/components/runs/live-metrics-charts.tsx
git commit -m "add: other metrics collapsible section below canonical charts surfacing custom metrics emitted by trainer"
```

---

## Task 12 — Metric downsample utility + batch run summary endpoint

**Files:**
- Create: `backend/app/services/metrics_service.py`
- Modify: `backend/app/services/run_service.py`
- Modify: `backend/app/api/routes/runs.py`
- Test: `backend/tests/test_run_summary_endpoint.py`

- [ ] **12.1 Write failing unit tests for downsampler**

Create `backend/tests/test_run_summary_endpoint.py`:

```python
from __future__ import annotations

import pytest

from app.services.metrics_service import downsample_to_n


def test_downsample_returns_original_when_smaller() -> None:
    result = downsample_to_n(points=[1.0, 2.0, 3.0], n=40)
    assert result == [1.0, 2.0, 3.0]


def test_downsample_averages_buckets_when_larger() -> None:
    result = downsample_to_n(points=list(range(100)), n=10)
    assert len(result) == 10
    assert result[0] < result[-1]


def test_downsample_zero_n_returns_empty() -> None:
    assert downsample_to_n(points=[1.0], n=0) == []
```

- [ ] **12.2 Run failing tests**

Run: `cd backend && pytest tests/test_run_summary_endpoint.py -v`
Expected: ImportError.

- [ ] **12.3 Implement utility**

Create `backend/app/services/metrics_service.py`:

```python
from __future__ import annotations


def downsample_to_n(*, points: list[float], n: int) -> list[float]:
    if n <= 0:
        return []
    if len(points) <= n:
        return list(points)
    bucket_size = len(points) / n
    out: list[float] = []
    for i in range(n):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)
        bucket = points[start:end] if end > start else [points[start]]
        out.append(sum(bucket) / len(bucket))
    return out
```

- [ ] **12.4 Run tests pass**

Run: `cd backend && pytest tests/test_run_summary_endpoint.py -v`
Expected: all three PASS.

- [ ] **12.5 Write failing integration test for batch endpoint**

Append to `backend/tests/test_run_summary_endpoint.py`:

```python
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


async def test_run_summary_batch_returns_per_run_entries(client: AsyncClient, db_session) -> None:
    project = (await client.post("/api/v1/projects", json={"name": "s", "description": ""})).json()
    run_a = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "a"},
        )
    ).json()
    run_b = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "b"},
        )
    ).json()

    import uuid
    from datetime import UTC, datetime
    from app.models.metric_point import MetricPoint

    for run, loss in ((run_a, 0.5), (run_b, 0.3)):
        for step in range(0, 100, 10):
            db_session.add(MetricPoint(
                id=str(uuid.uuid4()),
                run_id=run["id"],
                step=step,
                epoch=0.0,
                metric_name="train_loss",
                metric_value=loss,
                stage_name=None,
                recorded_at=datetime.now(UTC).isoformat(),
            ))
    await db_session.commit()

    ids = f"{run_a['id']},{run_b['id']}"
    resp = await client.get(f"/api/v1/projects/{project['id']}/runs/summary?ids={ids}")
    assert resp.status_code == 200
    body = resp.json()
    run_ids = {r["run_id"] for r in body["runs"]}
    assert run_ids == {run_a["id"], run_b["id"]}
    for entry in body["runs"]:
        assert "final_train_loss" in entry
        assert "train_loss_sparkline" in entry
        assert len(entry["train_loss_sparkline"]) <= 40
```

- [ ] **12.6 Run failing test**

Run: `cd backend && pytest tests/test_run_summary_endpoint.py::test_run_summary_batch_returns_per_run_entries -v`
Expected: 404.

- [ ] **12.7 Implement service function**

Append to `backend/app/services/run_service.py`:

```python
from app.schemas.run_observability import RunSummaryBatchResponse, RunSummaryResponse
from app.services.metrics_service import downsample_to_n


async def get_run_summaries(
    *,
    session: AsyncSession,
    project_id: str,
    run_ids: list[str],
) -> RunSummaryBatchResponse:
    summaries: list[RunSummaryResponse] = []
    for run_id in run_ids:
        run = (
            await session.execute(
                select(Run).where(Run.id == run_id, Run.project_id == project_id)
            )
        ).scalar_one_or_none()
        if run is None:
            continue

        train_points = (
            await session.execute(
                select(MetricPoint)
                .where(
                    MetricPoint.run_id == run_id,
                    MetricPoint.metric_name == "train_loss",
                )
                .order_by(MetricPoint.step)
            )
        ).scalars().all()

        eval_points = (
            await session.execute(
                select(MetricPoint)
                .where(
                    MetricPoint.run_id == run_id,
                    MetricPoint.metric_name == "eval_loss",
                )
                .order_by(MetricPoint.step)
            )
        ).scalars().all()

        final_train = train_points[-1].metric_value if train_points else None
        final_eval = eval_points[-1].metric_value if eval_points else None
        wall_clock_ms = _compute_wall_clock_ms(run)
        step_count = max((p.step for p in train_points), default=0)
        sparkline = downsample_to_n(
            points=[p.metric_value for p in train_points],
            n=40,
        )
        summaries.append(
            RunSummaryResponse(
                run_id=run_id,
                status=run.status,
                final_train_loss=final_train,
                final_eval_loss=final_eval,
                wall_clock_ms=wall_clock_ms,
                step_count=step_count,
                train_loss_sparkline=sparkline,
            )
        )
    return RunSummaryBatchResponse(runs=summaries)


def _compute_wall_clock_ms(run: Run) -> int:
    if run.started_at is None or run.completed_at is None:
        return 0
    from datetime import datetime
    start = datetime.fromisoformat(run.started_at)
    end = datetime.fromisoformat(run.completed_at)
    return int((end - start).total_seconds() * 1000)
```

If the `Run` model's timestamp fields are named differently (e.g. `start_time`, `end_time`), update the helper. Run `grep -n "started_at\|start_time\|completed_at\|end_time" backend/app/models/run.py` to verify.

- [ ] **12.8 Implement route**

In `backend/app/api/routes/runs.py`:

```python
from app.schemas.run_observability import RunSummaryBatchResponse


@router.get(
    "/{project_id}/runs/summary",
    response_model=RunSummaryBatchResponse,
)
async def get_run_summaries(
    project_id: str,
    ids: str,
    session: DbSession,
) -> RunSummaryBatchResponse:
    run_ids = [s for s in ids.split(",") if s]
    return await run_service.get_run_summaries(
        session=session,
        project_id=project_id,
        run_ids=run_ids,
    )
```

**Route ordering (load-bearing):** FastAPI matches in declaration order. Declare `get_run_summaries` **before** any `/{project_id}/runs/{run_id}/...` route in `runs.py`, otherwise FastAPI will capture `summary` as a `run_id` path parameter and the endpoint will 404. If a textual reorder is impractical, rename the path to `/{project_id}/runs-summary?ids=...` to avoid the collision entirely.

- [ ] **12.9 Run tests + regression**

Run: `cd backend && pytest tests/test_run_summary_endpoint.py tests/test_projects.py -v`

- [ ] **12.10 Commit**

```bash
git add backend/app/services/metrics_service.py backend/app/services/run_service.py backend/app/api/routes/runs.py backend/tests/test_run_summary_endpoint.py
git commit -m "add: run summary batch endpoint with downsampled train loss sparkline per run"
```

---

## Task 13 — Training history sparklines

**Files:**
- Create: `frontend/src/types/run-summary.ts`
- Create: `frontend/src/api/run-summary.ts`
- Create: `frontend/src/hooks/useRunSummaries.ts`
- Create: `frontend/src/components/runs/run-history-sparkline.tsx`
- Modify: `frontend/src/pages/training-page.tsx`

- [ ] **13.1 Types**

`frontend/src/types/run-summary.ts`:

```typescript
export interface RunSummary {
  readonly runId: string;
  readonly status: string;
  readonly finalTrainLoss: number | null;
  readonly finalEvalLoss: number | null;
  readonly wallClockMs: number;
  readonly stepCount: number;
  readonly trainLossSparkline: ReadonlyArray<number>;
}
```

- [ ] **13.2 API + hook**

`frontend/src/api/run-summary.ts`:

```typescript
import type { RunSummary } from "@/types/run-summary";
import { fetchApi } from "./client";

interface RawRunSummary {
  readonly run_id: string;
  readonly status: string;
  readonly final_train_loss: number | null;
  readonly final_eval_loss: number | null;
  readonly wall_clock_ms: number;
  readonly step_count: number;
  readonly train_loss_sparkline: ReadonlyArray<number>;
}

export async function fetchRunSummaries({
  projectId,
  runIds,
}: {
  projectId: string;
  runIds: ReadonlyArray<string>;
}): Promise<ReadonlyArray<RunSummary>> {
  if (runIds.length === 0) return [];
  const raw = await fetchApi<{ runs: ReadonlyArray<RawRunSummary> }>({
    path: `/projects/${projectId}/runs/summary?ids=${runIds.join(",")}`,
  });
  return raw.runs.map((r) => ({
    runId: r.run_id,
    status: r.status,
    finalTrainLoss: r.final_train_loss,
    finalEvalLoss: r.final_eval_loss,
    wallClockMs: r.wall_clock_ms,
    stepCount: r.step_count,
    trainLossSparkline: r.train_loss_sparkline,
  }));
}
```

`frontend/src/hooks/useRunSummaries.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import { fetchRunSummaries } from "@/api/run-summary";
import type { RunSummary } from "@/types/run-summary";

export function useRunSummaries({
  projectId,
  runIds,
}: {
  projectId: string;
  runIds: ReadonlyArray<string>;
}) {
  return useQuery<ReadonlyArray<RunSummary>>({
    queryKey: ["projects", projectId, "runs", "summary", [...runIds]],
    queryFn: () => fetchRunSummaries({ projectId, runIds }),
    enabled: Boolean(projectId) && runIds.length > 0,
  });
}
```

- [ ] **13.3 Sparkline row component**

`frontend/src/components/runs/run-history-sparkline.tsx`:

```tsx
import { Sparkline } from "@/components/shared/sparkline";
import type { RunSummary } from "@/types/run-summary";

interface RunHistorySparklineProps {
  readonly summary: RunSummary;
}

export function RunHistorySparkline({ summary }: RunHistorySparklineProps) {
  return (
    <div className="flex items-center gap-3">
      <Sparkline data={summary.trainLossSparkline} className="h-6 w-28" />
      <div className="flex gap-3 font-mono text-[11px] tabular-nums text-muted-foreground">
        <span>
          train{" "}
          <span className="text-foreground">
            {summary.finalTrainLoss !== null
              ? summary.finalTrainLoss.toFixed(4)
              : "—"}
          </span>
        </span>
        <span>
          eval{" "}
          <span className="text-foreground">
            {summary.finalEvalLoss !== null
              ? summary.finalEvalLoss.toFixed(4)
              : "—"}
          </span>
        </span>
        <span>
          {summary.stepCount} steps · {(summary.wallClockMs / 1000).toFixed(0)}s
        </span>
      </div>
    </div>
  );
}
```

- [ ] **13.4 Wire into training-page.tsx**

In `frontend/src/pages/training-page.tsx`, replace the empty `metricsByRun` memo (lines ~119–121):

```tsx
import { useRunSummaries } from "@/hooks/useRunSummaries";
import { RunHistorySparkline } from "@/components/runs/run-history-sparkline";
// ...

const runIds = React.useMemo(() => trainingHistory.map((r) => r.id), [trainingHistory]);
const { data: summaries } = useRunSummaries({
  projectId: activeProjectId ?? "",
  runIds,
});
const summariesByRun = React.useMemo(() => {
  const map = new Map<string, typeof summaries[number]>();
  (summaries ?? []).forEach((s) => map.set(s.runId, s));
  return map;
}, [summaries]);
```

Delete the old `metricsByRun` memo.

Inside each history card render, add:

```tsx
{summariesByRun.get(run.id) ? (
  <RunHistorySparkline summary={summariesByRun.get(run.id)!} />
) : null}
```

Place this where the card currently shows run metadata (adjust to match existing card layout).

- [ ] **13.5 Type check + commit**

Run: `cd frontend && npx tsc --noEmit`

```bash
git add frontend/src/types/run-summary.ts frontend/src/api/run-summary.ts frontend/src/hooks/useRunSummaries.ts frontend/src/components/runs/run-history-sparkline.tsx frontend/src/pages/training-page.tsx
git commit -m "add: run history sparklines on training history tab with final train and eval loss"
```

---

# Part D — Checkpoint retention enforcement

---

## Task 14 — Alembic migration: `is_best` on artifacts, flip retention default

**Files:**
- Create: `backend/alembic/versions/0004_is_best_and_retention_defaults.py`
- Modify: `backend/app/models/artifact.py`
- Modify: `backend/app/schemas/workbench_config.py`

- [ ] **14.1 Check current migration count**

Run: `ls backend/alembic/versions/`

Expected: three files (`0001`, `0002`, `0003`). Next is `0004`.

- [ ] **14.2 Find the latest revision id**

Run: `grep -n "down_revision\|revision" backend/alembic/versions/0003_*.py | head -5`

Note the `revision` value — that's your `down_revision`.

- [ ] **14.3 Write migration**

Create `backend/alembic/versions/0004_is_best_and_retention_defaults.py`:

```python
"""add is_best to artifacts"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_is_best_and_retention_defaults"
down_revision = "<revision id from step 14.2>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column("is_best", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("artifacts", "is_best")
```

- [ ] **14.4 Update SQLAlchemy model**

In `backend/app/models/artifact.py`, add:

```python
is_best: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

Place it next to `is_retained`.

- [ ] **14.5 Flip retention default**

In `backend/app/schemas/workbench_config.py`, `CheckpointRetentionConfig`:

```python
class CheckpointRetentionConfig(BaseModel):
    keep_last_n: int = 3
    always_keep_best_eval: bool = True
    always_keep_final: bool = True
    delete_intermediates_after_completion: bool = False
```

Flip the last value from `True` to `False`.

- [ ] **14.6 Run migration against test DB + run tests**

Run: `cd backend && alembic upgrade head`
Run: `cd backend && pytest tests/test_projects.py -v`

Expected: migration applies cleanly; tests still pass (is_best=0 defaults).

- [ ] **14.7 Commit**

```bash
git add backend/alembic/versions/0004_is_best_and_retention_defaults.py backend/app/models/artifact.py backend/app/schemas/workbench_config.py
git commit -m "add: is_best column on artifacts, flip delete_intermediates default to false"
```

---

## Task 15 — Promote `_apply_retention_for_run` to public + add convenience wrapper

**Files:**
- Modify: `backend/app/services/storage_manager.py`
- Test: `backend/tests/test_retention_hooks.py`

- [ ] **15.1 Read existing retention implementation**

Run: `sed -n '165,251p' backend/app/services/storage_manager.py`

Confirm signature, return type, and internal logic.

- [ ] **15.2 Write failing tests**

Create `backend/tests/test_retention_hooks.py`:

```python
from __future__ import annotations

import pytest
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


async def test_apply_retention_after_checkpoint_keeps_last_n(
    client: AsyncClient,
    db_session,
    tmp_path,
) -> None:
    from app.services.storage_manager import apply_retention_after_checkpoint
    from app.models.artifact import Artifact
    from sqlalchemy import select
    import uuid
    from datetime import UTC, datetime

    project = (await client.post("/api/v1/projects", json={"name": "ret", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    for step in (10, 20, 30, 40, 50):
        ckpt_path = tmp_path / project["id"] / "runs" / run["id"] / f"checkpoint-{step}"
        ckpt_path.mkdir(parents=True, exist_ok=True)
        (ckpt_path / "marker.txt").write_text("x")
        db_session.add(Artifact(
            id=str(uuid.uuid4()),
            run_id=run["id"],
            project_id=project["id"],
            artifact_type="checkpoint",
            file_path=str(ckpt_path),
            file_size_bytes=10,
            is_retained=1,
            is_best=0,
            created_at=datetime.now(UTC).isoformat(),
        ))
    await db_session.commit()

    result = await apply_retention_after_checkpoint(
        session=db_session,
        run_id=run["id"],
    )

    rows = (
        await db_session.execute(
            select(Artifact).where(
                Artifact.run_id == run["id"],
                Artifact.artifact_type == "checkpoint",
            )
        )
    ).scalars().all()
    retained = [r for r in rows if r.is_retained == 1]
    assert len(retained) == 3  # keep_last_n default
    assert "kept" in result and "pruned" in result
```

- [ ] **15.3 Run failing test**

Run: `cd backend && pytest tests/test_retention_hooks.py::test_apply_retention_after_checkpoint_keeps_last_n -v`
Expected: ImportError on `apply_retention_after_checkpoint`.

- [ ] **15.4 Promote and add wrapper**

In `backend/app/services/storage_manager.py`:

1. **Rename** `_apply_retention_for_run` to `apply_retention_for_run` (remove leading underscore). Update any internal call sites accordingly.

2. **Add** a new public convenience wrapper:

```python
async def apply_retention_after_checkpoint(
    *,
    session: AsyncSession,
    run_id: str,
) -> dict[str, list[int]]:
    """Evaluate retention policy immediately after a checkpoint save.
    Returns {kept: [steps], pruned: [steps]}."""
    from app.models.config_version import ConfigVersion
    from app.models.run import Run
    from app.core.config import settings

    run = (
        await session.execute(select(Run).where(Run.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        return {"kept": [], "pruned": []}

    cfg_row = await session.get(ConfigVersion, run.config_version_id)
    if cfg_row is None:
        return {"kept": [], "pruned": []}

    import yaml
    cfg = yaml.safe_load(cfg_row.yaml_blob)
    retention = cfg.get("checkpoint_retention", {}) if isinstance(cfg, dict) else {}
    project_dir = str(Path(settings.projects_dir) / run.project_id)

    before = set(await _retained_steps_for_run(session=session, run_id=run_id))
    await apply_retention_for_run(
        session=session,
        run=run,
        project_directory=project_dir,
        keep_last_n=retention.get("keep_last_n", 3),
        always_keep_best_eval=retention.get("always_keep_best_eval", True),
        always_keep_final=retention.get("always_keep_final", True),
        delete_intermediates=False,
    )
    after = set(await _retained_steps_for_run(session=session, run_id=run_id))
    return {
        "kept": sorted(after),
        "pruned": sorted(before - after),
    }


async def _retained_steps_for_run(
    *, session: AsyncSession, run_id: str
) -> list[int]:
    from app.models.artifact import Artifact
    import re

    rows = (
        await session.execute(
            select(Artifact).where(
                Artifact.run_id == run_id,
                Artifact.artifact_type == "checkpoint",
                Artifact.is_retained == 1,
            )
        )
    ).scalars().all()
    steps: list[int] = []
    for r in rows:
        match = re.search(r"checkpoint-(\d+)", r.file_path)
        if match:
            steps.append(int(match.group(1)))
    return steps
```

If the existing retention function signature differs from recon, adjust kwargs. The recon showed `(*, session, run, project_directory, keep_last_n, always_keep_best_eval, always_keep_final, delete_intermediates)`.

- [ ] **15.5 Run tests**

Run: `cd backend && pytest tests/test_retention_hooks.py -v`
Expected: PASS.

- [ ] **15.6 Commit**

```bash
git add backend/app/services/storage_manager.py backend/tests/test_retention_hooks.py
git commit -m "refactor: promote apply_retention_for_run to public, add apply_retention_after_checkpoint wrapper"
```

---

## Task 16 — Trainer tracks best eval loss + emits `is_best_eval` on checkpoint

**Files:**
- Modify: `backend/app/services/trainer.py`
- Test: `backend/tests/test_retention_hooks.py`

- [ ] **16.1 Read trainer checkpoint emission**

Run: `grep -n "_emit_checkpoint\|checkpoint.*event" backend/app/services/trainer.py | head -10`

Confirm the helper signature and where it's called.

- [ ] **16.2 Write failing test**

Append to `backend/tests/test_retention_hooks.py`:

```python
def test_trainer_best_eval_tracker_emits_is_best_eval(capsys) -> None:
    import json
    from unittest.mock import MagicMock, patch
    from app.services import trainer

    tracker = trainer._BestEvalTracker()
    assert tracker.update(step=10, eval_loss=0.9) is True  # first wins
    assert tracker.update(step=20, eval_loss=1.0) is False  # worse
    assert tracker.update(step=30, eval_loss=0.5) is True  # better

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_checkpoint(step=30, path="/tmp/ckpt", size_bytes=1024, is_best_eval=True)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    ckpt_event = next(e for e in events if e["type"] == "checkpoint")
    assert ckpt_event["is_best_eval"] is True
```

- [ ] **16.3 Run failing test**

Run: `cd backend && pytest tests/test_retention_hooks.py::test_trainer_best_eval_tracker_emits_is_best_eval -v`
Expected: AttributeError on `_BestEvalTracker`.

- [ ] **16.4 Add tracker + update emit helper**

In `backend/app/services/trainer.py`, near the top:

```python
class _BestEvalTracker:
    def __init__(self) -> None:
        self.best_loss: float = float("inf")
        self.best_step: int | None = None

    def update(self, *, step: int, eval_loss: float) -> bool:
        if eval_loss < self.best_loss:
            self.best_loss = eval_loss
            self.best_step = step
            return True
        return False
```

Modify `_emit_checkpoint` to accept `is_best_eval` (and include it in the event payload):

```python
def _emit_checkpoint(
    *,
    step: int,
    path: str,
    size_bytes: int,
    is_best_eval: bool = False,
) -> None:
    if not _is_main_process():
        return
    _emit({
        "type": "checkpoint",
        "step": step,
        "path": path,
        "size_bytes": size_bytes,
        "is_best_eval": is_best_eval,
    })
```

Instantiate `_BestEvalTracker` once at the start of `main()` (or wherever the training loop is driven from). In the `on_evaluate` callback, call `tracker.update(...)`. At each checkpoint save, compare `step == tracker.best_step` to determine `is_best_eval`.

Example wiring (adjust to the real variable names in `main`):

```python
best_tracker = _BestEvalTracker()

# inside on_evaluate callback:
if metrics and isinstance(metrics.get("eval_loss"), (int, float)):
    best_tracker.update(step=state.global_step, eval_loss=float(metrics["eval_loss"]))

# at checkpoint save:
_emit_checkpoint(
    step=step,
    path=ckpt_path,
    size_bytes=_dir_size(ckpt_path),
    is_best_eval=(step == best_tracker.best_step),
)
```

- [ ] **16.5 Run tests**

Run: `cd backend && pytest tests/test_retention_hooks.py tests/test_trainer_accelerate.py tests/test_trainer_rank_aware.py -v`
Expected: PASS.

- [ ] **16.6 Commit**

```bash
git add backend/app/services/trainer.py backend/tests/test_retention_hooks.py
git commit -m "add: best eval tracker in trainer, emit is_best_eval in checkpoint event"
```

---

## Task 17 — Orchestrator retention lifecycle hooks + is_best artifact flag

**Files:**
- Modify: `backend/app/services/orchestrator.py`
- Test: `backend/tests/test_retention_hooks.py`

- [ ] **17.1 Read checkpoint event branch + run termination blocks**

Run: `sed -n '526,600p' backend/app/services/orchestrator.py`
Run: `sed -n '770,830p' backend/app/services/orchestrator.py`

Confirm exact call sites for `_record_artifact` and run termination branches.

- [ ] **17.2 Write failing test**

Append to `backend/tests/test_retention_hooks.py`:

```python
async def test_checkpoint_event_with_is_best_eval_sets_artifact_flag(
    client: AsyncClient,
    db_session,
    tmp_path,
) -> None:
    from app.services import orchestrator
    from app.models.artifact import Artifact
    from sqlalchemy import select

    project = (await client.post("/api/v1/projects", json={"name": "be", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    ckpt_dir = tmp_path / project["id"] / "runs" / run["id"] / "checkpoint-100"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    await orchestrator._process_trainer_event(
        run_id=run["id"],
        project_id=project["id"],
        event={
            "type": "checkpoint",
            "step": 100,
            "path": str(ckpt_dir),
            "size_bytes": 2048,
            "is_best_eval": True,
        },
    )

    rows = (
        await db_session.execute(
            select(Artifact).where(
                Artifact.run_id == run["id"],
                Artifact.artifact_type == "checkpoint",
            )
        )
    ).scalars().all()
    assert any(r.is_best == 1 for r in rows)
```

- [ ] **17.3 Run failing test**

Run: `cd backend && pytest tests/test_retention_hooks.py::test_checkpoint_event_with_is_best_eval_sets_artifact_flag -v`

- [ ] **17.4 Update `_record_artifact`**

In `backend/app/services/orchestrator.py`, modify the `_record_artifact` signature to accept `is_best: int = 0`:

```python
async def _record_artifact(
    *,
    run_id: str,
    project_id: str,
    artifact_type: str,
    file_path: str,
    size_bytes: int,
    is_best: int = 0,
) -> None:
    async with async_session_factory() as session:
        now = datetime.now(UTC).isoformat()
        artifact = Artifact(
            id=str(uuid.uuid4()),
            run_id=run_id,
            project_id=project_id,
            artifact_type=artifact_type,
            file_path=file_path,
            file_size_bytes=size_bytes,
            is_retained=1,
            is_best=is_best,
            created_at=now,
        )
        session.add(artifact)
        await session.commit()
```

- [ ] **17.5 Update checkpoint event branch**

In `_process_trainer_event`, for `event_type == "checkpoint"`:

```python
elif event_type == "checkpoint":
    step = event["step"]
    path = event["path"]
    size_bytes = event.get("size_bytes", 0)
    is_best_eval = bool(event.get("is_best_eval", False))

    await _update_run_status(run_id=run_id, status="running", last_checkpoint_path=path)
    await _record_artifact(
        run_id=run_id,
        project_id=project_id,
        artifact_type="checkpoint",
        file_path=path,
        size_bytes=size_bytes,
        is_best=1 if is_best_eval else 0,
    )

    async with async_session_factory() as session:
        retention_result = await apply_retention_after_checkpoint(
            session=session,
            run_id=run_id,
        )
    await event_bus.publish({
        "channel": "system",
        "event": "retention_applied",
        "payload": {
            "runId": run_id,
            "kept": retention_result["kept"],
            "pruned": retention_result["pruned"],
        },
    })
    # existing checkpoint_saved publish continues here
```

Add import: `from app.services.storage_manager import apply_retention_after_checkpoint`.

- [ ] **17.6 Hook run termination**

In the three termination branches (completed / cancelled / failed, around lines 775–824), add after each status update:

```python
async with async_session_factory() as session:
    await _run_final_retention_sweep(session=session, run_id=run_id, project_id=project_id)
```

Add the helper near `_record_artifact`:

```python
from app.services.storage_manager import run_project_cleanup


async def _run_final_retention_sweep(
    *,
    session: AsyncSession,
    run_id: str,
    project_id: str,
) -> None:
    await run_project_cleanup(session=session, project_id=project_id)
```

The full aggressive cleanup honors `delete_intermediates_after_completion` (now defaulting to False — only deletes if the user opted in).

- [ ] **17.7 Run tests**

Run: `cd backend && pytest tests/test_retention_hooks.py -v`
Expected: PASS.

- [ ] **17.8 Commit**

```bash
git add backend/app/services/orchestrator.py backend/tests/test_retention_hooks.py
git commit -m "add: retention lifecycle hooks in orchestrator on checkpoint save and run termination, persist is_best on checkpoint artifacts"
```

---

## Task 18 — Frontend retention UI: BEST/Pruned badges + toast

**Files:**
- Modify: `frontend/src/types/artifact.ts`
- Modify: `frontend/src/types/websocket.ts`
- Modify: `frontend/src/hooks/useRunStream.ts`
- Modify: `frontend/src/components/runs/checkpoint-list.tsx`

- [ ] **18.1 Extend checkpoint type**

In `frontend/src/types/artifact.ts`, ensure `Checkpoint` / Artifact has `isBest: boolean` field. Add if missing.

- [ ] **18.2 Add WS event type**

In `frontend/src/types/websocket.ts`:

```typescript
export interface RetentionAppliedPayload {
  readonly runId: string;
  readonly kept: ReadonlyArray<number>;
  readonly pruned: ReadonlyArray<number>;
}
```

- [ ] **18.3 Handle event in useRunStream**

In `frontend/src/hooks/useRunStream.ts`, add handler:

```typescript
if (envelope.channel === "system" && envelope.event === "retention_applied") {
  const payload = envelope.payload as RetentionAppliedPayload;
  if (payload.pruned.length > 0) {
    toast.info(
      `Pruned ${payload.pruned.length} checkpoint${payload.pruned.length === 1 ? "" : "s"} per retention policy`,
    );
  }
  queryClient.invalidateQueries({
    queryKey: ["projects", projectId, "runs", runId, "checkpoints"],
  });
}
```

If `toast` isn't imported yet, use whatever toast primitive the project uses (`sonner`? Check `grep -rn "import.*toast" frontend/src/ | head -3`).

- [ ] **18.4 Add badges to CheckpointList**

In `frontend/src/components/runs/checkpoint-list.tsx`, for each row:

```tsx
{checkpoint.isBest ? (
  <Badge variant="secondary" className="bg-emerald-600/20 text-emerald-700">
    BEST EVAL
  </Badge>
) : null}
{!checkpoint.isRetained ? (
  <Badge variant="outline" className="line-through text-muted-foreground">
    Pruned
  </Badge>
) : null}
```

When `isRetained` is false, also apply `line-through` to the whole row (so users see the file is gone but row stays for audit).

- [ ] **18.5 Type check + commit**

Run: `cd frontend && npx tsc --noEmit`

```bash
git add frontend/src/types/artifact.ts frontend/src/types/websocket.ts frontend/src/hooks/useRunStream.ts frontend/src/components/runs/checkpoint-list.tsx
git commit -m "add: best eval and pruned badges on checkpoint list, retention applied toast"
```

---

# Part E — Weights observability (tier B)

---

## Task 19 — Alembic migration: layers_json + weight_snapshots table

**Files:**
- Create: `backend/alembic/versions/0005_weight_observability.py`
- Modify: `backend/app/models/model_profile.py`
- Create: `backend/app/models/weight_snapshot.py`

- [ ] **19.1 Write migration**

Create `backend/alembic/versions/0005_weight_observability.py`:

```python
"""weight observability: layers_json on model_profiles, new weight_snapshots table"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_weight_observability"
down_revision = "0004_is_best_and_retention_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_profiles",
        sa.Column("layers_json", sa.Text(), nullable=True),
    )
    op.create_table(
        "weight_snapshots",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("layer_name", sa.Text(), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("std", sa.Float(), nullable=False),
        sa.Column("norm", sa.Float(), nullable=False),
        sa.Column("min_val", sa.Float(), nullable=False),
        sa.Column("max_val", sa.Float(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("run_id", "step", "layer_name"),
    )
    op.create_index(
        "idx_weight_snapshots_run_layer_step",
        "weight_snapshots",
        ["run_id", "layer_name", "step"],
    )


def downgrade() -> None:
    op.drop_index("idx_weight_snapshots_run_layer_step", table_name="weight_snapshots")
    op.drop_table("weight_snapshots")
    op.drop_column("model_profiles", "layers_json")
```

- [ ] **19.2 Update `ModelProfile`**

In `backend/app/models/model_profile.py`, add:

```python
layers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **19.3 Create `WeightSnapshot` model**

Create `backend/app/models/weight_snapshot.py`:

```python
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WeightSnapshot(Base):
    __tablename__ = "weight_snapshots"
    __table_args__ = (PrimaryKeyConstraint("run_id", "step", "layer_name"),)

    run_id: Mapped[str] = mapped_column(Text, ForeignKey("runs.id"), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    layer_name: Mapped[str] = mapped_column(Text, nullable=False)
    mean: Mapped[float] = mapped_column(Float, nullable=False)
    std: Mapped[float] = mapped_column(Float, nullable=False)
    norm: Mapped[float] = mapped_column(Float, nullable=False)
    min_val: Mapped[float] = mapped_column(Float, nullable=False)
    max_val: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
```

If `backend/app/models/__init__.py` re-exports models, add `WeightSnapshot` there.

- [ ] **19.4 Run migration**

Run: `cd backend && alembic upgrade head`

- [ ] **19.5 Run regression suite**

Run: `cd backend && pytest tests/test_projects.py tests/test_configs.py -v`

- [ ] **19.6 Commit**

```bash
git add backend/alembic/versions/0005_weight_observability.py backend/app/models/model_profile.py backend/app/models/weight_snapshot.py backend/app/models/__init__.py
git commit -m "add: layers_json column on model_profiles, weight_snapshots table with indexed layer history"
```

---

## Task 20 — Trainer emits model profile on run start

**Files:**
- Modify: `backend/app/services/trainer.py`
- Test: `backend/tests/test_model_profile.py`

- [ ] **20.1 Locate model instantiation point**

Run: `grep -n "from_pretrained\|adapter" backend/app/services/trainer.py | head -15`

Find the line where the fully-prepared model (post-LoRA attachment) is available. Recon shows line 747 for base model, line 1094 for adapter attachment.

- [ ] **20.2 Write failing test**

Create `backend/tests/test_model_profile.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import torch
import torch.nn as nn


def test_emit_model_profile_walks_named_parameters(capsys) -> None:
    from app.services import trainer

    model = nn.Sequential(
        nn.Linear(10, 20),
        nn.Linear(20, 5),
    )

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_model_profile(model=model)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    profile = next(e for e in events if e["type"] == "model_profile")
    assert profile["total_params"] > 0
    assert profile["trainable_params"] > 0
    assert len(profile["layers"]) >= 2
    first_layer = profile["layers"][0]
    assert "name" in first_layer
    assert "shape" in first_layer
    assert "param_count" in first_layer
    assert first_layer["trainable"] in (True, False)
    assert first_layer["dtype"]


def test_emit_model_profile_captures_frozen_layers() -> None:
    from app.services import trainer

    model = nn.Linear(10, 5)
    for p in model.parameters():
        p.requires_grad = False

    captured: list[dict] = []
    with patch.object(trainer, "_emit", side_effect=lambda e: captured.append(e)):
        with patch.object(trainer, "_is_main_process", return_value=True):
            trainer._emit_model_profile(model=model)

    profile = next(e for e in captured if e["type"] == "model_profile")
    assert profile["trainable_params"] == 0
    assert all(layer["trainable"] is False for layer in profile["layers"])
```

- [ ] **20.3 Run failing tests**

Run: `cd backend && pytest tests/test_model_profile.py -v`
Expected: AttributeError.

- [ ] **20.4 Implement emitter**

In `backend/app/services/trainer.py`, add helper:

```python
def _emit_model_profile(*, model: Any) -> None:
    if not _is_main_process():
        return

    layers: list[dict[str, Any]] = []
    total_params = 0
    trainable_params = 0
    for name, param in model.named_parameters():
        count = int(param.numel())
        total_params += count
        if param.requires_grad:
            trainable_params += count
        layers.append({
            "name": name,
            "shape": list(param.shape),
            "param_count": count,
            "trainable": bool(param.requires_grad),
            "dtype": str(param.dtype).replace("torch.", ""),
        })

    _emit({
        "type": "model_profile",
        "total_params": total_params,
        "trainable_params": trainable_params,
        "layers": layers,
    })
```

- [ ] **20.5 Wire into `main()`**

In `main()` (after model + adapter attachment, before `trainer.train()`), add:

```python
_emit_model_profile(model=model)
```

Variable name `model` should match the recon confirmation. If the post-adapter model is stored under a different name, use that.

- [ ] **20.6 Run tests**

Run: `cd backend && pytest tests/test_model_profile.py -v`

- [ ] **20.7 Commit**

```bash
git add backend/app/services/trainer.py backend/tests/test_model_profile.py
git commit -m "add: model profile emission on run start walks named parameters for per-layer stats"
```

---

## Task 21 — Trainer emits weight stats at checkpoint save

**Files:**
- Modify: `backend/app/services/trainer.py`
- Test: `backend/tests/test_weight_snapshots.py`

- [ ] **21.1 Write failing test**

Create `backend/tests/test_weight_snapshots.py`:

```python
from __future__ import annotations

import json
from unittest.mock import patch

import torch.nn as nn


def test_emit_weight_stats_computes_per_layer_stats(capsys) -> None:
    from app.services import trainer

    model = nn.Linear(10, 5)

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_weight_stats(model=model, step=100)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    event = next(e for e in events if e["type"] == "weight_stats")
    assert event["step"] == 100
    assert len(event["stats"]) >= 1
    first_layer_name = next(iter(event["stats"]))
    stats = event["stats"][first_layer_name]
    for key in ("mean", "std", "norm", "min", "max"):
        assert key in stats
        assert isinstance(stats[key], (int, float))
```

- [ ] **21.2 Run failing test**

Run: `cd backend && pytest tests/test_weight_snapshots.py -v`
Expected: AttributeError.

- [ ] **21.3 Implement emitter**

In `backend/app/services/trainer.py`:

```python
def _emit_weight_stats(*, model: Any, step: int) -> None:
    if not _is_main_process():
        return

    stats: dict[str, dict[str, float]] = {}
    for name, param in model.named_parameters():
        data = param.data
        stats[name] = {
            "mean": float(data.mean().item()),
            "std": float(data.std().item()) if data.numel() > 1 else 0.0,
            "norm": float(data.norm().item()),
            "min": float(data.min().item()),
            "max": float(data.max().item()),
        }

    _emit({"type": "weight_stats", "step": step, "stats": stats})
```

- [ ] **21.4 Call after atomic checkpoint write**

In `trainer.py`, find where `_atomic_checkpoint_write` is called (step detail from recon). After the write returns successfully and `_emit_checkpoint` has run, add:

```python
_emit_weight_stats(model=model, step=step)
```

- [ ] **21.5 Run tests**

Run: `cd backend && pytest tests/test_weight_snapshots.py -v`

- [ ] **21.6 Commit**

```bash
git add backend/app/services/trainer.py backend/tests/test_weight_snapshots.py
git commit -m "add: per-layer weight stats emission after checkpoint write for norm and range tracking"
```

---

## Task 22 — Orchestrator handles `model_profile` and `weight_stats` events

**Files:**
- Modify: `backend/app/services/orchestrator.py`
- Test: `backend/tests/test_model_profile.py`, `backend/tests/test_weight_snapshots.py`

- [ ] **22.1 Write failing tests**

Append to `backend/tests/test_model_profile.py`:

```python
import pytest
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


async def test_model_profile_event_persists_layers_json(client: AsyncClient, db_session) -> None:
    from sqlalchemy import select
    from app.models.model_profile import ModelProfile
    from app.services import orchestrator

    project = (await client.post("/api/v1/projects", json={"name": "mp", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    await orchestrator._process_trainer_event(
        run_id=run["id"],
        project_id=project["id"],
        event={
            "type": "model_profile",
            "total_params": 100,
            "trainable_params": 50,
            "layers": [
                {"name": "lin.weight", "shape": [5, 10], "param_count": 50, "trainable": True, "dtype": "float32"},
            ],
        },
    )

    rows = (
        await db_session.execute(select(ModelProfile).where(ModelProfile.project_id == project["id"]))
    ).scalars().all()
    assert len(rows) >= 1
    assert rows[0].layers_json is not None
```

Append to `backend/tests/test_weight_snapshots.py`:

```python
import pytest
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


async def test_weight_stats_event_persists_rows(client: AsyncClient, db_session) -> None:
    from sqlalchemy import select
    from app.models.weight_snapshot import WeightSnapshot
    from app.services import orchestrator

    project = (await client.post("/api/v1/projects", json={"name": "ws", "description": ""})).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"config_version_id": project["active_config_version_id"], "name": "r"},
        )
    ).json()

    await orchestrator._process_trainer_event(
        run_id=run["id"],
        project_id=project["id"],
        event={
            "type": "weight_stats",
            "step": 100,
            "stats": {
                "layer1.weight": {"mean": 0.1, "std": 0.2, "norm": 1.0, "min": -0.3, "max": 0.5},
                "layer2.weight": {"mean": 0.0, "std": 0.1, "norm": 0.5, "min": -0.2, "max": 0.2},
            },
        },
    )

    rows = (
        await db_session.execute(select(WeightSnapshot).where(WeightSnapshot.run_id == run["id"]))
    ).scalars().all()
    assert len(rows) == 2
    assert {r.layer_name for r in rows} == {"layer1.weight", "layer2.weight"}
```

- [ ] **22.2 Run failing tests**

Run: `cd backend && pytest tests/test_model_profile.py tests/test_weight_snapshots.py -v`

- [ ] **22.3 Implement event handlers**

In `backend/app/services/orchestrator.py`, inside `_process_trainer_event`, add branches:

```python
elif event_type == "model_profile":
    await _persist_model_profile(
        run_id=run_id,
        project_id=project_id,
        total_params=event["total_params"],
        trainable_params=event["trainable_params"],
        layers=event["layers"],
    )
    await event_bus.publish({
        "channel": "system",
        "event": "model_profile_ready",
        "payload": {
            "runId": run_id,
            "layerCount": len(event["layers"]),
            "totalParams": event["total_params"],
            "trainableParams": event["trainable_params"],
        },
    })

elif event_type == "weight_stats":
    await _persist_weight_stats(
        run_id=run_id,
        step=event["step"],
        stats=event["stats"],
    )
    await event_bus.publish({
        "channel": "system",
        "event": "weight_stats_recorded",
        "payload": {
            "runId": run_id,
            "step": event["step"],
            "layerCount": len(event["stats"]),
        },
    })
```

Add helpers:

```python
import json as _json

from app.models.model_profile import ModelProfile
from app.models.weight_snapshot import WeightSnapshot


async def _persist_model_profile(
    *,
    run_id: str,
    project_id: str,
    total_params: int,
    trainable_params: int,
    layers: list[dict[str, Any]],
) -> None:
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return

        existing = (
            await session.execute(
                select(ModelProfile).where(
                    ModelProfile.project_id == project_id,
                    ModelProfile.model_id == run.model_id,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            session.add(ModelProfile(
                id=str(uuid.uuid4()),
                project_id=project_id,
                source=run.model_source or "",
                model_id=run.model_id or "",
                family=run.model_family or "",
                parameter_count=total_params,
                trainable_count=trainable_params,
                layers_json=_json.dumps(layers),
            ))
        elif existing.layers_json is None:
            existing.layers_json = _json.dumps(layers)
            existing.parameter_count = existing.parameter_count or total_params
            existing.trainable_count = existing.trainable_count or trainable_params

        await session.commit()


async def _persist_weight_stats(
    *,
    run_id: str,
    step: int,
    stats: dict[str, dict[str, float]],
) -> None:
    async with async_session_factory() as session:
        now = datetime.now(UTC).isoformat()
        session.add_all([
            WeightSnapshot(
                run_id=run_id,
                step=step,
                layer_name=layer_name,
                mean=values["mean"],
                std=values["std"],
                norm=values["norm"],
                min_val=values["min"],
                max_val=values["max"],
                created_at=now,
            )
            for layer_name, values in stats.items()
        ])
        await session.commit()
```

If `Run` model doesn't have `model_source`, `model_id`, `model_family` columns, derive them from the run's `ConfigVersion` YAML. Run `grep -n "model_id\|model_source\|model_family" backend/app/models/run.py` to verify. Fallback pattern when columns are absent:

```python
cfg_row = await session.get(ConfigVersion, run.config_version_id)
import yaml
cfg = yaml.safe_load(cfg_row.yaml_blob) if cfg_row else {}
model_block = cfg.get("model", {}) if isinstance(cfg, dict) else {}
model_id = model_block.get("model_id", "")
model_source = model_block.get("source", "")
model_family = model_block.get("family", "")
```

Use these values in the `ModelProfile` insert instead of `run.model_id` etc.

**Internal session note:** `_process_trainer_event` opens new sessions via `async_session_factory()`. In tests using an in-memory engine, the factory may still point at the production engine. If the test in step 22.1 fails due to session mismatch, monkey-patch `orchestrator.async_session_factory` to return the test's factory, or call the event branch directly with an explicit session parameter refactor.

- [ ] **22.4 Run tests**

Run: `cd backend && pytest tests/test_model_profile.py tests/test_weight_snapshots.py -v`

- [ ] **22.5 Commit**

```bash
git add backend/app/services/orchestrator.py backend/tests/test_model_profile.py backend/tests/test_weight_snapshots.py
git commit -m "add: orchestrator handlers for model_profile and weight_stats events, persist to model_profiles and weight_snapshots tables"
```

---

## Task 23 — Model profile + weight snapshot REST endpoints

**Files:**
- Create: `backend/app/schemas/weights.py`
- Modify: `backend/app/services/run_service.py`
- Modify: `backend/app/api/routes/runs.py`

- [ ] **23.1 Define schemas**

Create `backend/app/schemas/weights.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class LayerProfile(BaseModel):
    name: str
    shape: list[int]
    param_count: int
    trainable: bool
    dtype: str


class ModelProfileResponse(BaseModel):
    run_id: str
    total_params: int
    trainable_params: int
    layers: list[LayerProfile]


class LayerWeightStats(BaseModel):
    step: int
    mean: float
    std: float
    norm: float
    min_val: float
    max_val: float


class WeightSnapshotResponse(BaseModel):
    run_id: str
    layer_name: str | None
    points: list[LayerWeightStats]


class WeightSnapshotAllResponse(BaseModel):
    run_id: str
    snapshots_by_layer: dict[str, list[LayerWeightStats]]
```

- [ ] **23.2 Service functions**

Append to `backend/app/services/run_service.py`:

```python
import json as _json

from app.models.model_profile import ModelProfile
from app.models.weight_snapshot import WeightSnapshot
from app.schemas.weights import (
    LayerProfile,
    LayerWeightStats,
    ModelProfileResponse,
    WeightSnapshotAllResponse,
    WeightSnapshotResponse,
)


async def get_model_profile(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
) -> ModelProfileResponse:
    run = await get_run(session=session, run_id=run_id, project_id=project_id)

    profile = (
        await session.execute(
            select(ModelProfile).where(
                ModelProfile.project_id == project_id,
                ModelProfile.model_id == run.model_id,
            )
        )
    ).scalar_one_or_none()
    if profile is None or profile.layers_json is None:
        raise RunNotFoundError(f"no model profile for run {run_id}")

    raw_layers = _json.loads(profile.layers_json)
    return ModelProfileResponse(
        run_id=run_id,
        total_params=profile.parameter_count or 0,
        trainable_params=profile.trainable_count or 0,
        layers=[LayerProfile(**layer) for layer in raw_layers],
    )


async def list_weight_snapshots(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
    layer_name: str | None,
) -> WeightSnapshotResponse | WeightSnapshotAllResponse:
    await get_run(session=session, run_id=run_id, project_id=project_id)
    query = select(WeightSnapshot).where(WeightSnapshot.run_id == run_id)
    if layer_name is not None:
        query = query.where(WeightSnapshot.layer_name == layer_name)
    query = query.order_by(WeightSnapshot.step)
    rows = (await session.execute(query)).scalars().all()

    if layer_name is not None:
        return WeightSnapshotResponse(
            run_id=run_id,
            layer_name=layer_name,
            points=[
                LayerWeightStats(
                    step=r.step, mean=r.mean, std=r.std, norm=r.norm,
                    min_val=r.min_val, max_val=r.max_val,
                )
                for r in rows
            ],
        )

    by_layer: dict[str, list[LayerWeightStats]] = {}
    for r in rows:
        by_layer.setdefault(r.layer_name, []).append(
            LayerWeightStats(
                step=r.step, mean=r.mean, std=r.std, norm=r.norm,
                min_val=r.min_val, max_val=r.max_val,
            )
        )
    return WeightSnapshotAllResponse(run_id=run_id, snapshots_by_layer=by_layer)
```

- [ ] **23.3 Routes**

In `backend/app/api/routes/runs.py`:

```python
from app.schemas.weights import (
    ModelProfileResponse,
    WeightSnapshotAllResponse,
    WeightSnapshotResponse,
)


@router.get(
    "/{project_id}/runs/{run_id}/model-profile",
    response_model=ModelProfileResponse,
)
async def get_run_model_profile(
    project_id: str,
    run_id: str,
    session: DbSession,
) -> ModelProfileResponse:
    try:
        return await run_service.get_model_profile(
            session=session,
            project_id=project_id,
            run_id=run_id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.get(
    "/{project_id}/runs/{run_id}/weight-snapshots",
    response_model=WeightSnapshotAllResponse | WeightSnapshotResponse,
)
async def get_run_weight_snapshots(
    project_id: str,
    run_id: str,
    session: DbSession,
    layer: str | None = None,
) -> WeightSnapshotAllResponse | WeightSnapshotResponse:
    try:
        return await run_service.list_weight_snapshots(
            session=session,
            project_id=project_id,
            run_id=run_id,
            layer_name=layer,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "RUN_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
```

- [ ] **23.4 Type check + commit**

Run: `cd backend && ruff check app/schemas/weights.py app/services/run_service.py app/api/routes/runs.py`

```bash
git add backend/app/schemas/weights.py backend/app/services/run_service.py backend/app/api/routes/runs.py
git commit -m "add: model-profile and weight-snapshots endpoints returning per-layer architecture and time-series stats"
```

---

## Task 24 — Frontend weights types, API clients, hooks

**Files:**
- Create: `frontend/src/types/model-profile.ts`
- Create: `frontend/src/types/weight-snapshot.ts`
- Create: `frontend/src/api/model-profile.ts`
- Create: `frontend/src/api/weight-snapshots.ts`
- Create: `frontend/src/hooks/useModelProfile.ts`
- Create: `frontend/src/hooks/useWeightSnapshots.ts`

- [ ] **24.1 Types**

`frontend/src/types/model-profile.ts`:

```typescript
export interface LayerProfile {
  readonly name: string;
  readonly shape: ReadonlyArray<number>;
  readonly paramCount: number;
  readonly trainable: boolean;
  readonly dtype: string;
}

export interface ModelProfile {
  readonly runId: string;
  readonly totalParams: number;
  readonly trainableParams: number;
  readonly layers: ReadonlyArray<LayerProfile>;
}
```

`frontend/src/types/weight-snapshot.ts`:

```typescript
export interface LayerWeightStats {
  readonly step: number;
  readonly mean: number;
  readonly std: number;
  readonly norm: number;
  readonly minVal: number;
  readonly maxVal: number;
}

export interface WeightSnapshotsByLayer {
  readonly runId: string;
  readonly snapshotsByLayer: Readonly<Record<string, ReadonlyArray<LayerWeightStats>>>;
}

export interface WeightSnapshotForLayer {
  readonly runId: string;
  readonly layerName: string;
  readonly points: ReadonlyArray<LayerWeightStats>;
}
```

- [ ] **24.2 API clients**

`frontend/src/api/model-profile.ts`:

```typescript
import type { LayerProfile, ModelProfile } from "@/types/model-profile";
import { fetchApi } from "./client";

interface RawLayer {
  readonly name: string;
  readonly shape: ReadonlyArray<number>;
  readonly param_count: number;
  readonly trainable: boolean;
  readonly dtype: string;
}

interface RawModelProfile {
  readonly run_id: string;
  readonly total_params: number;
  readonly trainable_params: number;
  readonly layers: ReadonlyArray<RawLayer>;
}

export async function fetchModelProfile({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<ModelProfile> {
  const raw = await fetchApi<RawModelProfile>({
    path: `/projects/${projectId}/runs/${runId}/model-profile`,
  });
  return {
    runId: raw.run_id,
    totalParams: raw.total_params,
    trainableParams: raw.trainable_params,
    layers: raw.layers.map((r): LayerProfile => ({
      name: r.name,
      shape: r.shape,
      paramCount: r.param_count,
      trainable: r.trainable,
      dtype: r.dtype,
    })),
  };
}
```

`frontend/src/api/weight-snapshots.ts`:

```typescript
import type {
  LayerWeightStats,
  WeightSnapshotForLayer,
  WeightSnapshotsByLayer,
} from "@/types/weight-snapshot";
import { fetchApi } from "./client";

interface RawStats {
  readonly step: number;
  readonly mean: number;
  readonly std: number;
  readonly norm: number;
  readonly min_val: number;
  readonly max_val: number;
}

function toLayerStats(raw: RawStats): LayerWeightStats {
  return {
    step: raw.step,
    mean: raw.mean,
    std: raw.std,
    norm: raw.norm,
    minVal: raw.min_val,
    maxVal: raw.max_val,
  };
}

export async function fetchWeightSnapshotsAll({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<WeightSnapshotsByLayer> {
  const raw = await fetchApi<{
    readonly run_id: string;
    readonly snapshots_by_layer: Readonly<Record<string, ReadonlyArray<RawStats>>>;
  }>({ path: `/projects/${projectId}/runs/${runId}/weight-snapshots` });
  const mapped: Record<string, ReadonlyArray<LayerWeightStats>> = {};
  for (const [name, points] of Object.entries(raw.snapshots_by_layer)) {
    mapped[name] = points.map(toLayerStats);
  }
  return { runId: raw.run_id, snapshotsByLayer: mapped };
}

export async function fetchWeightSnapshotsForLayer({
  projectId,
  runId,
  layerName,
}: {
  projectId: string;
  runId: string;
  layerName: string;
}): Promise<WeightSnapshotForLayer> {
  const raw = await fetchApi<{
    readonly run_id: string;
    readonly layer_name: string;
    readonly points: ReadonlyArray<RawStats>;
  }>({
    path: `/projects/${projectId}/runs/${runId}/weight-snapshots?layer=${encodeURIComponent(layerName)}`,
  });
  return {
    runId: raw.run_id,
    layerName: raw.layer_name,
    points: raw.points.map(toLayerStats),
  };
}
```

- [ ] **24.3 Hooks**

`frontend/src/hooks/useModelProfile.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import { fetchModelProfile } from "@/api/model-profile";
import type { ModelProfile } from "@/types/model-profile";

export function useModelProfile({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}) {
  return useQuery<ModelProfile>({
    queryKey: ["projects", projectId, "runs", runId, "model-profile"],
    queryFn: () => fetchModelProfile({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}
```

`frontend/src/hooks/useWeightSnapshots.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import {
  fetchWeightSnapshotsAll,
  fetchWeightSnapshotsForLayer,
} from "@/api/weight-snapshots";
import type {
  WeightSnapshotForLayer,
  WeightSnapshotsByLayer,
} from "@/types/weight-snapshot";

export function useWeightSnapshotsAll({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}) {
  return useQuery<WeightSnapshotsByLayer>({
    queryKey: ["projects", projectId, "runs", runId, "weight-snapshots", "all"],
    queryFn: () => fetchWeightSnapshotsAll({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}

export function useWeightSnapshotsForLayer({
  projectId,
  runId,
  layerName,
}: {
  projectId: string;
  runId: string;
  layerName: string | null;
}) {
  return useQuery<WeightSnapshotForLayer>({
    queryKey: ["projects", projectId, "runs", runId, "weight-snapshots", layerName],
    queryFn: () => {
      if (layerName === null) throw new Error("layerName required");
      return fetchWeightSnapshotsForLayer({ projectId, runId, layerName });
    },
    enabled: Boolean(projectId) && Boolean(runId) && layerName !== null,
  });
}
```

- [ ] **24.4 Type check + commit**

Run: `cd frontend && npx tsc --noEmit`

```bash
git add frontend/src/types/model-profile.ts frontend/src/types/weight-snapshot.ts frontend/src/api/model-profile.ts frontend/src/api/weight-snapshots.ts frontend/src/hooks/useModelProfile.ts frontend/src/hooks/useWeightSnapshots.ts
git commit -m "add: model profile and weight snapshot types, api clients, and tanstack query hooks"
```

---

## Task 25 — Layer tree + per-layer weight history components

**Files:**
- Create: `frontend/src/components/weights/layer-tree.tsx`
- Create: `frontend/src/components/weights/layer-weight-history.tsx`
- Modify: `frontend/src/pages/weights-page.tsx`
- Modify: `frontend/src/hooks/useRunStream.ts`

- [ ] **25.1 Layer tree**

`frontend/src/components/weights/layer-tree.tsx`:

```tsx
import { useMemo } from "react";

import { useModelProfile } from "@/hooks/useModelProfile";
import { useWeightSnapshotsAll } from "@/hooks/useWeightSnapshots";
import type { LayerProfile } from "@/types/model-profile";
import type { LayerWeightStats } from "@/types/weight-snapshot";

interface LayerTreeProps {
  readonly projectId: string;
  readonly runId: string;
  readonly selectedLayer: string | null;
  readonly onSelectLayer: (name: string) => void;
}

export function LayerTree({ projectId, runId, selectedLayer, onSelectLayer }: LayerTreeProps) {
  const { data: profile, isLoading } = useModelProfile({ projectId, runId });
  const { data: snapshots } = useWeightSnapshotsAll({ projectId, runId });

  const deadLayers = useMemo<ReadonlySet<string>>(() => {
    if (profile === undefined || snapshots === undefined) return new Set();
    const dead = new Set<string>();
    for (const layer of profile.layers) {
      if (!layer.trainable) continue;
      const series = snapshots.snapshotsByLayer[layer.name] ?? [];
      if (series.length < 2) continue;
      if (isLayerNotLearning(series)) dead.add(layer.name);
    }
    return dead;
  }, [profile, snapshots]);

  if (isLoading) {
    return <div className="text-xs text-muted-foreground">Loading profile…</div>;
  }
  if (profile === undefined) {
    return <div className="text-xs text-muted-foreground">No profile recorded for this run.</div>;
  }

  return (
    <div className="flex flex-col gap-1 font-mono text-xs">
      <div className="mb-2 text-[11px] uppercase tracking-wider text-muted-foreground">
        {profile.totalParams.toLocaleString()} params ·{" "}
        {profile.trainableParams.toLocaleString()} trainable (
        {profile.totalParams > 0
          ? ((profile.trainableParams / profile.totalParams) * 100).toFixed(1)
          : "0.0"}
        %)
      </div>
      {profile.layers.map((layer) => (
        <LayerRow
          key={layer.name}
          layer={layer}
          selected={selectedLayer === layer.name}
          isDead={deadLayers.has(layer.name)}
          onClick={() => onSelectLayer(layer.name)}
        />
      ))}
    </div>
  );
}

interface LayerRowProps {
  readonly layer: LayerProfile;
  readonly selected: boolean;
  readonly isDead: boolean;
  readonly onClick: () => void;
}

function LayerRow({ layer, selected, isDead, onClick }: LayerRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`grid grid-cols-[1fr_90px_80px_90px] gap-2 rounded border px-2 py-1.5 text-left ${
        selected ? "border-foreground bg-muted/40" : "border-transparent hover:bg-muted/20"
      } ${layer.trainable ? "" : "text-muted-foreground"}`}
    >
      <span className="truncate">{layer.name}</span>
      <span className="text-right tabular-nums">{layer.paramCount.toLocaleString()}</span>
      <span className="text-center">{layer.trainable ? "trainable" : "frozen"}</span>
      <span className="text-right">
        {isDead ? <span className="text-amber-600">not learning</span> : null}
      </span>
    </button>
  );
}

function isLayerNotLearning(series: ReadonlyArray<LayerWeightStats>): boolean {
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1].norm;
    const curr = series[i].norm;
    if (prev === 0) continue;
    if (Math.abs((curr - prev) / prev) >= 0.001) return false;
  }
  return true;
}
```

- [ ] **25.2 Per-layer history**

`frontend/src/components/weights/layer-weight-history.tsx`:

```tsx
import { useWeightSnapshotsForLayer } from "@/hooks/useWeightSnapshots";
import { ChartBox } from "@/components/charts/chart-box";

interface LayerWeightHistoryProps {
  readonly projectId: string;
  readonly runId: string;
  readonly layerName: string;
}

export function LayerWeightHistory({
  projectId,
  runId,
  layerName,
}: LayerWeightHistoryProps) {
  const { data } = useWeightSnapshotsForLayer({ projectId, runId, layerName });

  if (data === undefined || data.points.length === 0) {
    return (
      <div className="text-xs text-muted-foreground">
        No weight snapshots yet for {layerName}.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
        {layerName}
      </div>
      <ChartBox
        title="norm"
        data={data.points.map((p) => ({ x: p.step, y: p.norm }))}
        color="oklch(0.65 0.15 200)"
      />
      <ChartBox
        title="mean ± std"
        data={data.points.map((p) => ({ x: p.step, y: p.mean }))}
        color="oklch(0.65 0.15 140)"
      />
    </div>
  );
}
```

- [ ] **25.3 Wire into weights-page**

In `frontend/src/pages/weights-page.tsx`, add a new tab (or integrate into the existing "Tree" tab — check how tabs are defined in that file):

```tsx
import { LayerTree } from "@/components/weights/layer-tree";
import { LayerWeightHistory } from "@/components/weights/layer-weight-history";

// Inside the component:
const [selectedLayerName, setSelectedLayerName] = useState<string | null>(null);

// In the rendered JSX, in the Tree or new "Weights" tab:
<div className="grid grid-cols-[1fr_1.2fr] gap-4">
  <LayerTree
    projectId={activeProjectId ?? ""}
    runId={selectedRunId ?? ""}
    selectedLayer={selectedLayerName}
    onSelectLayer={setSelectedLayerName}
  />
  {selectedLayerName !== null ? (
    <LayerWeightHistory
      projectId={activeProjectId ?? ""}
      runId={selectedRunId ?? ""}
      layerName={selectedLayerName}
    />
  ) : (
    <div className="text-xs text-muted-foreground">Select a layer to view weight history.</div>
  )}
</div>
```

Determine the correct place to integrate by running `grep -n "TabsContent" frontend/src/pages/weights-page.tsx | head -10` and choosing the most fitting tab (likely "Tree" or "Parameters").

- [ ] **25.4 Handle new WS events**

In `frontend/src/hooks/useRunStream.ts`, add handlers for `model_profile_ready` and `weight_stats_recorded` — both invalidate the relevant query keys so fresh data is fetched:

```typescript
if (envelope.channel === "system" && envelope.event === "model_profile_ready") {
  queryClient.invalidateQueries({
    queryKey: ["projects", projectId, "runs", runId, "model-profile"],
  });
}
if (envelope.channel === "system" && envelope.event === "weight_stats_recorded") {
  queryClient.invalidateQueries({
    queryKey: ["projects", projectId, "runs", runId, "weight-snapshots"],
  });
}
```

- [ ] **25.5 Type check + commit**

Run: `cd frontend && npx tsc --noEmit`

```bash
git add frontend/src/components/weights/layer-tree.tsx frontend/src/components/weights/layer-weight-history.tsx frontend/src/pages/weights-page.tsx frontend/src/hooks/useRunStream.ts
git commit -m "add: layer tree and per-layer weight history on weights page with dead-layer heuristic"
```

---

# Final sweep

## Task 26 — Full verification

- [ ] **26.1 Backend full suite**

Run: `cd backend && pytest -v`
Expected: all existing + new tests PASS.

- [ ] **26.2 Backend lint**

Run: `cd backend && ruff check app/ tests/`
Expected: zero errors. Fix in place.

- [ ] **26.3 Backend type check**

Run: `cd backend && python -m mypy app/` (if mypy is configured — else skip)

- [ ] **26.4 Frontend type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: zero errors.

- [ ] **26.5 Frontend lint**

Run: `cd frontend && npx eslint src/`
Expected: zero errors. Fix in place.

- [ ] **26.6 Migrations clean**

Run: `cd backend && alembic upgrade head`
Expected: already at head, no pending migrations.

- [ ] **26.7 Manual verification (request from user)**

User starts dev servers. Verify:

1. Create a fresh project and run. The Runs page **Config** tab renders the YAML and "No differences" for the first run.
2. Edit the project config and create a second run. The Config tab diff shows the changed keys.
3. Observe resource tiles show real RAM and (on CUDA) VRAM totals. On MPS/CPU, VRAM tile shows "unavailable" hint.
4. Run progresses through 14 stages including a non-no-op "evaluation" stage. `final_eval_*` metrics appear in the "Other metrics" collapsed section.
5. Training history cards show sparklines + final loss numbers.
6. Checkpoints list shows a "BEST EVAL" badge on the best-eval checkpoint and "Pruned" badge on pruned rows after `keep_last_n` is exceeded.
7. Weights page shows the layer tree with trainable counts and total params. Selecting a layer shows its norm over checkpoint steps.

If any item fails, do not mark the task completed — open a follow-up issue and note which Part has the regression.

- [ ] **26.8 Final commit (if any lint/type fixes)**

```bash
git add <files touched by 26.2 or 26.5>
git commit -m "fix: resolve lint and type findings from final observability sweep"
```

---

## Acceptance criteria

**Part A — Config snapshot + final eval**
- New runs produce `projects/<pid>/runs/<rid>/config.yaml` + `config_snapshot` Artifact row with `is_retained=1`.
- `GET .../{run_id}/config-snapshot` returns yaml + diff against parent ConfigVersion.
- Runs page has a Config tab rendering yaml + diff panes.
- Final eval stage emits non-placeholder `stage_enter`/`stage_complete` and `final_eval_*` metric points.
- `callback_evaluation` stage name regression test passes.

**Part B — Resource capacity**
- `resource_update` WS payload includes `ram_total_mb` and `vram_total_mb`. `gpu_utilization_pct` removed.
- `SystemResourceMonitor` shows real RAM total. VRAM tile hides or shows "unavailable" on non-CUDA.
- No more `VRAM_TOTAL_GB_FALLBACK` / `RAM_TOTAL_GB_FALLBACK` constants in the frontend.

**Part C — Dynamic metrics + history**
- `GET .../{run_id}/metrics/names` returns distinct metric names.
- Live metrics has "Other metrics" collapsible listing every non-canonical metric with sparkline + expandable full chart.
- Training history cards render per-run sparklines and final loss values.
- `final_eval_*` metrics auto-appear in "Other metrics" after a run completes.

**Part D — Retention**
- `artifacts.is_best` column exists. Trainer marks the best-eval checkpoint via `is_best_eval` event field.
- Orchestrator calls `apply_retention_after_checkpoint` after every `checkpoint_saved`.
- Orchestrator calls `run_project_cleanup` on run completion/failure/cancellation.
- `retention_applied` WS event triggers frontend toast + query invalidation.
- `CheckpointRetentionConfig.delete_intermediates_after_completion` defaults to False.
- Checkpoint list shows "BEST EVAL" and "Pruned" badges.

**Part E — Weights (tier B)**
- `ModelProfile.layers_json` column exists. `weight_snapshots` table exists with expected indices.
- Trainer emits `model_profile` event after adapter attachment.
- Trainer emits `weight_stats` event after every atomic checkpoint write.
- Orchestrator persists both event types and publishes corresponding WS events.
- Weights page shows per-layer tree with trainable counts and per-layer norm history.
- Dead-layer heuristic flags trainable layers whose norm is stable across checkpoints.

## Out of scope (future plans)

- GPU utilization percent (platform-divergent; deferred).
- Activation snapshot collection (tier D). Existing `ActivationSnapshot` table and frontend components stay dormant — show "Activations not collected for this run" empty state only if they currently render as empty.
- Per-layer gradient norms per log step (tier C).
- User-composable chart builder.
- Syntax highlighting for Config tab YAML.
- Retention UI surface in config editor.

## Known risks

- **Trainer-loop regression:** every change to `trainer.py` risks training-side bugs. All trainer modifications are gated behind emit/event layers — no change to the training loop semantics beyond callback additions.
- **Route ordering:** FastAPI matches in declaration order. `/runs/summary` must be declared before `/runs/{run_id}` or it'll be captured as a run id.
- **Schema drift:** `ModelProfile.trainable_count` reflects the first run's state; subsequent runs record their trainable mask via the config snapshot artifact. Document this in the codebase where relevant.
- **Retention destructive action:** `delete_intermediates_after_completion=False` by default means the aggressive path is opt-in. Per-checkpoint pruning still occurs.
- **Dead-layer heuristic false positives:** a trainable layer whose weights are clipped or regularized aggressively may register as "not learning" while still learning in a LoRA adapter. Treat as advisory only.
