# Training Observability Design

**Date:** 2026-04-20
**Status:** Draft — pending user review before implementation plan
**Scope:** Close 7 observability gaps in the LLM Fine-Tuning Workbench training pipeline.

---

## Motivation

The training pipeline backend emits metrics, logs, stage transitions, and checkpoint events, and the WebSocket transport between backend and frontend works end-to-end. However, several observability signals are either hardcoded on the frontend, dormant in the backend despite existing scaffolding, or missing entirely. A prior version of the application had similar opacity problems; this design makes the full training workflow — hyperparameters, metrics, system performance, checkpoints, and weights — transparent to the user.

The key theme: most of this work is **wiring existing scaffolding**, not building new systems. The backend schema and frontend components are largely in place. Retention policy, sparkline components, config diffing, system capacity detection, and activation-snapshot display surfaces all exist. The work is to populate the empty half and connect the loose ends.

---

## Goals

1. Every run stores an immutable, auditable snapshot of its exact hyperparameters.
2. The pipeline has a structured final evaluation stage, distinct from mid-training callback evals.
3. The metrics UI reveals every numeric signal the trainer emits, not just a fixed list.
4. The training history page shows a sparkline summary per run without fetching full time series.
5. Resource panels read real capacity ceilings from the backend; no frontend-side hardcoded thresholds.
6. Model architecture and per-checkpoint weight statistics populate the Weights page.
7. Checkpoint retention policy is enforced at run time with visible decision logs.

## Non-goals

- GPU utilization percent — deferred. The UI panel is removed entirely; a future design will address CUDA/macOS divergence.
- Activation snapshots (tier D weights). The `activation_snapshots` table and frontend components stay dormant. Frontend views that depend on activation data will render an "Activations not collected for this run" empty state.
- Per-layer gradient norms per log step (tier C weights). Global grad norm continues as today.
- Custom metric chart builder UI. Dynamic metrics surface through a collapsed auto-discovery section; user-defined chart composition is out of scope.

---

## Phase overview

The design decomposes into seven phases. Phases 1–3 are strictly additive and independent. Phases 4–5 add new data. Phase 6 is a wiring phase with no new storage. Phase 7 requires a new table. Each phase lands independently and is verifiable on its own.

| Phase | Area | Primary work | New storage |
|---|---|---|---|
| 1 | Config snapshot per run | New artifact type, orchestrator emit on run start | None (uses `artifacts`) |
| 2 | Final evaluation stage | Trainer emits `stage_enter("evaluation")` post-training | None |
| 3 | Dynamic metrics UI | New endpoint for distinct names + frontend "Other metrics" section | None |
| 4 | History tab summaries | Batch summary endpoint + run history sparklines | None |
| 5 | Resource capacity in WS | Include ram/vram totals in `resource_update` payload; remove GPU util panel | None |
| 6 | Model profile + weight stats | Trainer emits profile + per-checkpoint stats; Weights page reads real data | Extend `ModelProfile` with `layers_json`; new `weight_snapshots` table |
| 7 | Checkpoint retention enforcement | Orchestrator hooks call existing `storage_manager` retention functions; trainer tracks best eval | None |

---

## Phase 1 — Hyperparameter snapshot per run

**Problem.** `Run` rows only FK to `ConfigVersion`. If the config is edited after a run, the exact hyperparameters used are lost.

**Design.**

- On run start, orchestrator resolves the effective config (the merged output after defaults, environment, and model-family adapters are applied) and serializes it to `projects/<project_id>/runs/<run_id>/config.yaml`.
- Orchestrator inserts an `Artifact` row: `artifact_type="config_snapshot"`, `path=<the yaml file>`, `size_bytes=<len>`, `is_retained=1` (snapshots are always retained).
- Add `"config_snapshot"` to the artifact type literal union used across schemas.
- New REST endpoint: `GET /api/v1/projects/{id}/runs/{run_id}/config-snapshot` returns `{yaml: string, parentVersionId: string, diff: ConfigDiff}`. The `diff` is computed by calling the existing `config_service._compute_diff()` against the parent `ConfigVersion`.
- Frontend adds a **Config** tab to the run detail page. Shows the raw YAML (read-only, syntax-highlighted) with a diff panel beside it. The diff UI reuses whatever pattern the existing config version diff uses (to be confirmed during implementation — if no pattern exists, a simple three-color inline diff is sufficient).

**Data flow.**

```
orchestrator.start_run()
  → resolve effective config via config_service
  → write config.yaml to run directory
  → insert Artifact(artifact_type="config_snapshot")
  → publish artifact_created WS event (existing)
```

**Open implementation decisions.**

- Serialization fidelity: if the resolved config includes model-family-specific post-processing, verify that reserialized YAML round-trips without semantic loss. If not, serialize via the Pydantic model's `model_dump()` with YAML output.

---

## Phase 2 — Final evaluation stage

**Problem.** Stage 11 "evaluation" is pre-created in every run but never entered. Mid-training evals use a separate `callback_evaluation` stage name (workaround for issue #53) and don't satisfy the "final eval" signal.

**Design.**

- After the training loop completes successfully (before checkpoint finalization), trainer emits `stage_enter("evaluation", stage_order=11)`.
- Trainer invokes `Trainer.evaluate()` one more time on the eval dataset, using the final model weights.
- Each metric from this final pass is emitted with a `final_` prefix (`final_eval_loss`, `final_eval_accuracy`, etc.). This prevents collision with mid-training `eval_loss` points.
- Trainer emits `stage_complete("evaluation", duration_ms=...)` with a summary `{num_eval_samples, final_eval_loss}`.
- If no eval dataset is configured, trainer emits `stage_complete("evaluation", duration_ms=0, output_summary={"skipped": true, "reason": "no_eval_dataset"})` — the stage still completes, just as skipped.
- The `callback_evaluation` stage handling for mid-training evals stays completely untouched.

**Frontend.** The existing stage timeline already renders any stage that enters/completes. No frontend changes required for this phase beyond surfacing `final_eval_*` metrics (happens automatically in phase 3).

---

## Phase 3 — Dynamic metrics UI

**Problem.** `LiveMetricsCharts` has a hardcoded `CHART_SPECS` array of four metric names. Any custom metric emitted by the trainer is persisted to `metric_points` but never shown.

**Design.**

- New endpoint: `GET /api/v1/projects/{project_id}/runs/{run_id}/metrics/names` returns `{names: string[]}` — the distinct metric names ever recorded for that run.
- The live metrics component keeps its four canonical charts (`train_loss`, `eval_loss`, `grad_norm`, `learning_rate`) as the primary panel.
- Below the canonical panel, a collapsed "Other metrics" section lists every discovered name not in the canonical set. Each row has:
  - Metric name
  - Latest value (tabular)
  - Inline sparkline (uses existing `components/shared/sparkline.tsx`)
  - Click-to-expand into a full chart in-place
- The section header shows "(N other metrics)" to aid discoverability.
- The discovered-names query runs on run mount and re-queries whenever a `metric_recorded` WS event arrives with a metric not in the current set. (Cache-invalidation via TanStack Query `invalidateQueries` on that key.)

**Edge cases.**

- `final_eval_*` metrics from Phase 2 appear here automatically.
- Metric names with non-standard characters are rendered as-is; no assumption of snake_case parsing.

---

## Phase 4 — Training history summaries

**Problem.** The Training page history tab intentionally sets `metricsByRun = {}`. Users cannot see at a glance how each past run behaved.

**Design.**

- New endpoint: `GET /api/v1/projects/{id}/runs/summary?ids=<csv>` returns a batch summary for the requested run ids:

```ts
type RunSummary = {
  runId: string;
  status: RunStatus;
  finalTrainLoss: number | null;
  finalEvalLoss: number | null;
  wallClockMs: number;
  stepCount: number;
  trainLossSparkline: number[]; // downsampled to <=40 points
};
```

- Downsampling: backend reads `metric_points` where `metric_name = "train_loss"`, bucket-averages to at most 40 points. Implementation reuses the same bucketing approach used for the live metrics query if present; otherwise adds a small `downsample_linear(points: list, target: int)` utility to `services/metrics_service.py`.
- The frontend history tab card renders the sparkline using `components/shared/sparkline.tsx` and shows the two final-loss values and wall clock inline.
- Full charts still require clicking into a run; this endpoint is strictly for lean list rendering.

**Cache policy.** Summaries are derived and can be cached per run (keyed on `run.updated_at`). First pass: no caching — SQLite reads are cheap enough at current scale.

---

## Phase 5 — Real resource capacity

**Problem.** `SystemResourceMonitor` uses frontend constants `VRAM_TOTAL_GB_FALLBACK = 40` and `RAM_TOTAL_GB_FALLBACK = 64`. The GPU utilization panel always reads 0.0 because `_collect_system_resources()` can't compute it cross-platform.

**Design.**

- `_collect_system_resources()` in `api/websocket/stream.py` is extended to include:
  - `ram_total_mb` — `psutil.virtual_memory().total / 1024 / 1024`
  - `vram_total_mb` — `torch.cuda.get_device_properties(0).total_memory / 1024 / 1024` on CUDA; `None` on MPS/CPU
- The `ResourceUpdatePayload` schema gains these two nullable fields.
- `SystemResourceMonitor.tsx`:
  - Drops `VRAM_TOTAL_GB_FALLBACK` and `RAM_TOTAL_GB_FALLBACK`.
  - Reads `ramTotalMb` and `vramTotalMb` from the WS payload.
  - If `vramTotalMb` is `null`, the VRAM bar is hidden (not approximated). A small "VRAM total unavailable (MPS)" tooltip explains why.
  - The **GPU utilization percent panel is removed entirely** — no `gpuUtilizationPct` prop, no bar, no associated types.
- The backend stops emitting `gpu_utilization_pct` in `ResourceUpdatePayload` (field removed from schema).

**Migration.** No DB migration needed. The WS payload is a transient contract between backend and frontend; removing a field breaks nothing at rest.

---

## Phase 6 — Model profile + per-checkpoint weight stats (tier B)

**Problem.** `ModelProfile` and `ActivationSnapshot` tables exist but are never populated. The Weights page has no data to display.

**Design.**

### 6a. Static model profile on run start

- Schema change: add `layers_json: JSON` to `ModelProfile`. Stores a list of `{name: str, shape: list[int], param_count: int, dtype: str}` — architecture-level only.
- Trainer callback `_emit_model_profile()`:
  - Walks `model.named_parameters()`.
  - Computes `parameter_count`, `trainable_count` (using run's actual trainable state — may differ from ModelProfile's project-level values when LoRA is applied).
  - Emits a `model_profile` JSON event with the per-layer list and run-specific trainable mask.
- Orchestrator handles `model_profile` event:
  - If no `ModelProfile` row exists for the run's model, insert one with `layers_json` populated. Architecture data is shared across runs of the same model. Keying strategy must match the existing `ModelProfile` schema — verify during implementation (expected: `family` + `model_id`, but confirm before inserting).
  - Persists the **run-specific** trainable mask to the `config_snapshot` artifact's metadata (not a separate table). Trainable state is a property of the run's config, not the architecture.
  - If the existing `ModelProfile.trainable_count` column is populated at insert time, it reflects the first run to observe this model. Subsequent runs do not update it — they record their own trainable state via the config snapshot. Existing `trainable_count` should be treated as advisory at the project level, not authoritative per run.
- Publishes `model_profile_ready` WS event `{runId, modelProfileId, layerCount, totalParams, trainableParams}`.

- New REST endpoint: `GET /api/v1/projects/{id}/runs/{run_id}/model-profile` — returns `{layers: [...], trainableByLayer: {layerName: bool}, totalParams, trainableParams}`. The trainable map is sourced from the config_snapshot artifact; the layer list comes from `ModelProfile.layers_json`.

### 6b. Per-checkpoint weight statistics

- New table `weight_snapshots`:
  ```
  run_id: UUID FK
  step: int
  layer_name: str
  mean: float
  std: float
  norm: float
  min_val: float
  max_val: float
  created_at: datetime
  PRIMARY KEY (run_id, step, layer_name)
  INDEX (run_id, layer_name, step)
  ```
- After every atomic checkpoint write completes (trainer.py `_atomic_checkpoint_write()`), trainer computes per-layer weight stats over `model.named_parameters()`:
  ```
  for name, p in model.named_parameters():
      stats[name] = {
          "mean": p.data.mean().item(),
          "std": p.data.std().item(),
          "norm": p.data.norm().item(),
          "min": p.data.min().item(),
          "max": p.data.max().item(),
      }
  ```
- Trainer emits a `weight_stats` event `{step, stats: {layer_name: {mean, std, norm, min, max}}}`.
- Orchestrator batch-inserts one `weight_snapshots` row per layer per event.
- Publishes `weight_stats_recorded` WS event `{runId, step, layerCount}` — notification only; details fetched via REST.

- New REST endpoint: `GET /api/v1/projects/{id}/runs/{run_id}/weight-snapshots` with optional `?layer=<name>` filter returns the time series for that layer (or all layers indexed by name).

### 6c. Weights page surface

- Weights page receives a run id from the URL / selected-run store.
- Layer tree UI:
  - Renders `ModelProfile.layers_json` as a hierarchical tree (split on `.` in parameter names).
  - Each row shows param count, shape, trainable yes/no, dtype.
  - Trainable layers are highlighted; frozen layers are muted.
- Per-layer drill-down:
  - Click a layer → side panel shows `norm` over checkpoint steps as a line chart.
  - Dead-layer heuristic: a trainable layer whose `norm` changes by less than 0.1% between every pair of consecutive checkpoints is flagged with a "Not learning" badge. Applies only to layers marked trainable for the run; frozen layers never show the badge (their norm should not change by design). Advisory signal, not an alert.
- Existing activation-summary components (`activation-summary-view.tsx`, etc.) render an empty state "Activations not collected for this run" — unchanged in scope.

**Performance considerations.**

- Weight stat computation runs synchronously in trainer at checkpoint save time. For models with ~500 layers (a LoRA-adapted 7B), this adds ~1–2s per checkpoint. Acceptable — checkpoints are rare events.
- Batch insert uses SQLAlchemy `session.execute(insert(...), [list of row dicts])` to avoid per-row overhead.

---

## Phase 7 — Checkpoint retention enforcement

**Problem.** `storage_manager.py` has full retention logic (`run_project_cleanup()`, `_apply_retention_for_run()`, `DecisionLog` writes) but nothing calls it. The trainer never sets `is_retained=1` on the "best eval" checkpoint at save time, so even if retention ran, it couldn't identify the winner.

**Design.**

### 7a. Best-eval tracking at checkpoint save

- Trainer maintains in-memory `best_eval_loss: float = inf` and `best_eval_step: int | None = None`.
- After each mid-training eval callback, if the latest `eval_loss` is lower than `best_eval_loss`, update both trackers.
- When emitting a `checkpoint` event, trainer includes `is_best_eval: bool` in the payload. Orchestrator translates this into an `is_retained=1` hint and a `is_best=True` flag on the `Artifact` row.
- **Schema change (minor):** add `is_best: bool` default false to `artifacts` table for checkpoint artifacts. Makes "find the best checkpoint" a single indexed query rather than a scan of logs.

### 7b. Lifecycle hooks to invoke existing retention service

- After orchestrator persists a `checkpoint_saved` event, it calls `storage_manager._apply_retention_for_run(run_id)`:
  - Reads the run's retention config from the associated `ConfigVersion`.
  - Marks losers `is_retained=0` per policy (`keep_last_n`, `always_keep_best_eval`, `always_keep_final`).
  - Deletes disk artifacts for newly-unretained checkpoints.
  - Writes a `DecisionLog` entry per pruned checkpoint.
- On run completion/failure/cancel, orchestrator calls `storage_manager.run_project_cleanup(run_id)` which additionally honors `delete_intermediates_after_completion`.
- Publishes `retention_applied` WS event `{runId, kept: list[step], pruned: list[step]}` — lets the UI flash a toast.

### 7c. Defaults for new configs

Update the default `CheckpointRetentionConfig` in `schemas/workbench_config.py`:

```python
keep_last_n: int = 3
always_keep_best_eval: bool = True
always_keep_final: bool = True
delete_intermediates_after_completion: bool = False
```

These match the prior brainstorm agreement.

### 7d. UI feedback

- The checkpoint list on the run page shows:
  - `is_best` → "BEST EVAL" pill in green.
  - `is_retained = 0` → row rendered struck-through with an "Pruned" badge (the artifact row stays in the DB for audit; the file on disk is gone).
- When a `retention_applied` WS event arrives, a transient toast shows "Pruned 2 intermediate checkpoints per policy (keep_last_n=3)".

---

## Cross-cutting additions

### New artifact type literal

Extend the artifact type union:

```python
ArtifactType = Literal["checkpoint", "log_bundle", "metric_export", "config_snapshot"]
```

### New WS message types

| Event | Payload | Phase |
|---|---|---|
| `model_profile_ready` | `{runId, modelProfileId, layerCount, totalParams, trainableParams}` | 6 |
| `weight_stats_recorded` | `{runId, step, layerCount}` | 6 |
| `retention_applied` | `{runId, kept: int[], pruned: int[]}` | 7 |

All follow the existing `{type, payload}` envelope. Frontend handlers use TanStack Query invalidation for data refresh; no direct state mutation.

### New REST endpoints

| Method | Path | Phase |
|---|---|---|
| GET | `/api/v1/projects/{id}/runs/{run_id}/config-snapshot` | 1 |
| GET | `/api/v1/projects/{id}/runs/{run_id}/metrics/names` | 3 |
| GET | `/api/v1/projects/{id}/runs/summary?ids=...` | 4 |
| GET | `/api/v1/projects/{id}/runs/{run_id}/model-profile` | 6 |
| GET | `/api/v1/projects/{id}/runs/{run_id}/weight-snapshots?layer=<name>` | 6 |

### Schema changes summary

- **`ModelProfile`**: add `layers_json: JSON NULLABLE`. Alembic migration.
- **`Artifact`**: add `is_best: BOOLEAN NOT NULL DEFAULT FALSE`. Alembic migration.
- **New table `weight_snapshots`**: as specified in Phase 6b. Alembic migration.
- **`ResourceUpdatePayload`** (Pydantic, no DB): add `ram_total_mb: float | None`, `vram_total_mb: float | None`; remove `gpu_utilization_pct`.

### Files likely to be created

- `backend/app/services/metrics_service.py` — only if the downsample utility doesn't have a natural home elsewhere.
- `backend/alembic/versions/<timestamp>_add_weight_snapshots_and_profile_layers.py`
- `frontend/src/components/runs/other-metrics-section.tsx`
- `frontend/src/components/runs/config-snapshot-tab.tsx`
- `frontend/src/components/weights/layer-tree.tsx`
- `frontend/src/components/weights/layer-weight-history.tsx`
- `frontend/src/hooks/useConfigSnapshot.ts`
- `frontend/src/hooks/useMetricNames.ts`
- `frontend/src/hooks/useModelProfile.ts`
- `frontend/src/hooks/useWeightSnapshots.ts`
- `frontend/src/hooks/useRunSummaries.ts`
- `frontend/src/api/config-snapshot.ts`
- `frontend/src/api/model-profile.ts`
- `frontend/src/api/weight-snapshots.ts`
- `frontend/src/api/run-summary.ts`
- `frontend/src/types/model-profile.ts`
- `frontend/src/types/weight-snapshot.ts`

### Files likely to be modified

- `backend/app/services/trainer.py` — new emits: `model_profile`, `weight_stats`, `stage_enter("evaluation")` final, `is_best_eval` in checkpoint event.
- `backend/app/services/orchestrator.py` — new event handlers: `model_profile`, `weight_stats`; lifecycle hooks for retention; config snapshot creation at run start.
- `backend/app/services/storage_manager.py` — if any call-site signature needs to change for the new hooks.
- `backend/app/services/config_service.py` — helper to serialize resolved config YAML if not already present.
- `backend/app/api/websocket/stream.py` — `ram_total_mb`, `vram_total_mb` in resource payload; remove gpu util.
- `backend/app/api/routes/runs.py` — five new endpoints.
- `backend/app/models/model_profile.py` — `layers_json` column.
- `backend/app/models/artifact.py` — `is_best` column.
- `backend/app/models/weight_snapshot.py` — new model.
- `backend/app/schemas/workbench_config.py` — `CheckpointRetentionConfig` defaults.
- `backend/app/schemas/resources.py` (or wherever `ResourceUpdatePayload` lives) — add totals, remove gpu util.
- `backend/app/schemas/artifact.py` — add `config_snapshot` to type literal.
- `frontend/src/components/runs/live-metrics-charts.tsx` — integrate "Other metrics" section.
- `frontend/src/components/runs/system-resource-monitor.tsx` — drop fallback constants, remove GPU util bar.
- `frontend/src/components/runs/checkpoint-list.tsx` — "BEST EVAL" and "Pruned" badges.
- `frontend/src/pages/weights-page.tsx` — real data wiring.
- `frontend/src/pages/runs-page.tsx` — Config tab.
- `frontend/src/pages/training-page.tsx` — populate `metricsByRun` via summary endpoint.
- `frontend/src/hooks/useRunStream.ts` — handle new WS events.
- `frontend/src/stores/run-stream-store.ts` — store shape additions.

---

## Testing strategy

### Backend

- **Unit:** weight-stat computation for a tiny toy model; retention policy correctness given synthetic artifact fixtures; config diff output matches known-good diffs.
- **Integration (pytest + temp SQLite):** full run lifecycle with a tiny synthetic model (`distilbert-base-uncased` scaled down or a handcrafted `nn.Module`) — asserts that after a run ends: a config_snapshot artifact exists, an evaluation stage is marked complete, model_profile row has `layers_json`, weight_snapshots rows exist per checkpoint step, retention decisions logged in DecisionLog.
- **API:** each new endpoint has a happy-path test and a 404-on-missing-run test.
- **WebSocket:** verify `model_profile_ready`, `weight_stats_recorded`, `retention_applied` events are published in order.

### Frontend

- **Component tests** (whichever pattern is established — colocated `*.test.tsx` or `__tests__/`): layer tree rendering given a fixture profile; Other Metrics section toggles on empty/populated state; checkpoint list renders BEST and Pruned badges.
- **Integration via mock WS:** simulate a run emitting weight_stats + retention events; assert UI updates.
- **No e2e additions** — existing Playwright (or equivalent) run coverage is out of scope for this spec.

---

## Sequencing and risk

Phases are designed to land in this order:

1. **Phase 1 (config snapshot)** — lowest risk, purely additive. Ship first to establish the artifact-per-run pattern.
2. **Phase 5 (resource capacity)** — small surface, removes a known-broken panel. Quick win.
3. **Phase 3 (dynamic metrics)** — additive; one endpoint + one UI section.
4. **Phase 4 (history summaries)** — additive; one endpoint + existing sparkline.
5. **Phase 2 (final eval stage)** — touches trainer loop; needs careful co-existence with `callback_evaluation`.
6. **Phase 7 (retention enforcement)** — highest consequence (deletes files). Ship only after Phase 1 so config_snapshot is safely retained through pruning.
7. **Phase 6 (weights)** — largest surface (two schema changes, new table, new UI page wiring). Ship last.

**Risks and mitigations.**

- *Trainer loop divergence:* every change to `trainer.py` risks introducing training-side bugs. All trainer modifications are gated behind emit/event layers — no change to the training loop itself beyond callback additions.
- *Migration order:* Phase 6 and 7 both add columns. Bundle migrations carefully; rollback path requires dropping `weight_snapshots`, `layers_json`, `is_best` — all safe since the features won't ship without them.
- *Retention deletes real files:* default `delete_intermediates_after_completion = False` means the aggressive path is opt-in. Per-checkpoint pruning still occurs but only when `keep_last_n` is exceeded, so users can see the effect gradually.
- *Activation components stay dormant:* explicit empty state prevents "it looks broken" interpretation.

---

## Out of scope (for follow-up)

- GPU utilization percent (cross-platform strategy).
- Activation snapshot collection (tier D).
- Per-layer gradient norms per log step (tier C).
- User-composable metric chart builder.
- Training-history UI for metrics deeper than sparklines.
- Downsampling strategy for long runs on the live metrics chart (if they grow too dense).
- Retention UI surface in the config editor (today it's edit-YAML-to-change-defaults; a polished form is a future item).
