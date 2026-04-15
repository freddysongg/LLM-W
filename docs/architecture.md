# Architecture

This document is the engineering-facing complement to the [README](../README.md) diagrams. It names the actual code, routes, WS channels, and tables so the diagrams stay honest as the system evolves. For product-level decisions and data models, see [`SPEC.md`](../SPEC.md).

---

## Shape of the system

The workbench has four load-bearing boxes:

1. **Observability Core** — the event bus (`core/events.py`), the WebSocket `ConnectionManager` (`api/websocket/stream.py`), and SQLite (`core/database.py`). Every service writes into one of these.
2. **Training Runner** — the orchestrator drives a 14-stage lifecycle, but the actual training work runs in a separate Python subprocess (`backend/app/services/trainer.py`) launched by `training_dispatcher.py`. The subprocess emits newline-delimited JSON events on stdout; the orchestrator parses them, persists metric points, advances stages, and republishes to the event bus. This boundary is why a crashing HuggingFace kernel cannot take down the API server.
3. **Eval Harness** — a two-tier judge stack (Tier 1 deterministic + moderation, Tier 2 G-Eval CoT with ChainPoll N=3), all routed through a shared `openai_judge` with `instructor`-validated structured outputs, fed by versioned YAML rubrics.
4. **Feedback Loop** — failing cases (eval_calls with `passed = false`) are the raw material for regression datasets that feed back into the eval harness. The replay subsystem (`services/eval/replay.py`) re-runs stored `eval_call` triples and diffs response hashes to detect judge-model drift.

The frontend is a pure consumer — it speaks REST for CRUD and a single WebSocket (`/ws/{project_id}`) multiplexed over five channels.

---

## Frontend surface (`frontend/src/`)

Pages: `dashboard`, `projects`, `runs`, `training`, `datasets`, `models`, `adapters`, `weights`, `compare`, `eval`, `suggestions`, `artifacts`, `settings`.

Data flow is strict: **pages → hooks → api/ or ws/**. Components are pure renderers. Zustand stores hold only client-side UI state; server state is owned by TanStack Query.

REST clients (one file per resource): `artifacts.ts`, `cloud.ts`, `configs.ts`, `datasets.ts`, `eval.ts`, `health.ts`, `model-explorer.ts`, `models.ts`, `projects.ts`, `runs.ts`, `settings.ts`, `storage.ts`, `suggestions.ts`.

WebSocket clients: `ws/client.ts` (generic reconnecting client) and `ws/eval-stream.ts` (eval channel wrapper).

---

## Backend surface (`backend/app/`)

### Entry point

`app/main.py` wires routers, sets up CORS, defines the lifespan (creates tables, loads persisted settings overrides, recovers stale runs + eval runs, starts the resource poller), and registers three exception handlers that normalize errors into `{ error: { code, message, details } }`.

### Routers (`api/routes/`)

| Module | Prefix | Responsibility |
|---|---|---|
| `health.py` | `/healthz` | liveness + basic readiness |
| `projects.py` | `/projects` | project CRUD |
| `configs.py` | `/configs` | immutable config versions + diffs |
| `models.py` | `/models` | model profiles, introspection, layer inspection |
| `datasets.py` | `/datasets` | dataset profiles + sourcing |
| `settings.py` | `/settings` | app + provider settings with persisted overrides |
| `runs.py` | `/{project_id}/runs` | run CRUD, cancel, pause, resume, stages, metrics, checkpoints, logs, compare |
| `artifacts.py` | `/artifacts` | checkpoint + artifact listing |
| `storage.py` | `/storage` | storage records + disk budget |
| `suggestions.py` | `/suggestions` | AI config recommender outputs |
| `eval.py` | `/eval` | eval run lifecycle + call pagination |
| `rubrics.py` | `/rubrics` | rubric + rubric version management |

### WebSocket (`api/websocket/`)

One endpoint: `GET /ws/{project_id}?run_id=…&channels=…`. Frames follow a typed envelope validated by `schemas/websocket.py`. The `ConnectionManager`:

- Maintains per-connection subscription sets.
- Bridges `event_bus.publish("project.{id}.ws", …)` → per-connection async queues → `websocket.send_text`.
- Drops frames and logs a warning when the per-connection queue is full (backpressure).
- Runs a resource poller (5s) that publishes `channel=system, event=resource_update` with GPU/CPU/RAM stats.

Valid channels (enforced in `stream.py`):

```
run_state · metrics · logs · system · eval
```

Inbound frame types: `subscribe`, `unsubscribe`, `ping`. Outbound events include `connected`, `subscribed`, `pong`, `error`, plus anything the services publish on the above channels.

### Services (`services/`)

| Service | Role |
|---|---|
| `orchestrator.py` | 14-stage run lifecycle, reads trainer stdout, persists stages + metrics, publishes WS events |
| `training_dispatcher.py` | spawns local trainer subprocess; `modal` environment raises `UnsupportedEnvironmentError` |
| `trainer.py` | the subprocess entry point — loads model/adapter/dataset, runs training, emits stdout JSON, writes atomic checkpoints |
| `watchdog.py` | heartbeat monitoring + rank-aware kill, recovers stale runs on startup |
| `storage_manager.py` | atomic checkpoint writes (temp dir → rename), disk budget enforcement |
| `rule_engine.py` | declarative rules for config validation + warnings |
| `eval_runner.py` | eval run orchestration, in-flight task draining, stale-run recovery |
| `eval/tier1.py` | deterministic validators + OpenAI Moderation prescreen |
| `eval/geval.py` | Tier-2 G-Eval CoT judge (R1) |
| `eval/chainpoll.py` | N=3 majority-vote wrapper over a judge (R4) |
| `eval/openai_judge.py` | shared OpenAI client with `instructor`-validated structured outputs (R7) |
| `eval/rubric_loader.py` | versioned YAML rubric ingestion |
| `eval/replay.py` | replay stored `eval_call` triples and compare response hashes to detect judge drift |
| `project_service.py`, `config_service.py`, `config_validator.py` | project + config CRUD and validation |
| `dataset_service.py` | dataset profiling, sourcing, splits |
| `introspection.py` | layer + architecture introspection |
| `model_service.py` | model profile lookup + adapter selection |
| `ai_recommender.py` | AI config suggestions |
| `settings_service.py` | provider/app settings with persisted overrides |
| `suggestion_service.py` | suggestion persistence + querying |
| `cloud/modal_adapter.py` | stubbed Modal adapter (out of scope for v4) |

### Model adapters (`adapters/`)

- `base.py` — abstract `ModelAdapter` interface covering load, architecture metadata, introspection, training, eval, activation capture, checkpoint export.
- `causal_lm.py` — the HuggingFace causal-LM implementation used by every current run.

New families slot in by implementing `ModelAdapter`.

### ORM models (`models/`)

```
activation_snapshot · artifact · config_version · dataset_profile · decision_log
eval_call · eval_case · eval_run · metric_point · model_profile
project · rubric · rubric_version · run · run_stage · storage_record · suggestion
```

All schema changes go through Alembic. Metric points are batch-inserted during runs. Checkpoints live on disk; the DB stores paths, not blobs.

### CLI (`cli/`)

`app.cli.eval_replay` — re-runs stored `eval_call` triples for judge-drift detection. Entry point wired through `python -m app.cli`.

---

## Run lifecycle (plain English)

1. Frontend `POST /{project_id}/runs` with a config version id.
2. Route delegates to `run_service`; orchestrator inserts a `run` row and 14 `run_stages` rows and publishes `channel=run_state, event=run_created`.
3. Orchestrator calls `training_dispatcher.dispatch_training` which spawns the trainer subprocess (`python -u -m app.services.trainer …`) with stdout/stderr piped.
4. Watchdog starts tracking the run's heartbeat; stale-run recovery runs on API startup to clean up anything left dangling by a crash.
5. Trainer emits stdout lines like `{"event": "stage_enter", "stage": "…"}`, `{"event": "metric", "step": …, "loss": …}`, `{"event": "checkpoint", "path": "…"}`. Each checkpoint is written to a temp directory then atomically renamed into place.
6. Orchestrator parses each line, batch-inserts `metric_points`, updates `run_stages`, and publishes to `project.{id}.ws`. The `ConnectionManager` fans out to subscribed clients.
7. Terminal status (`completed | failed | cancelled`) is written to `runs.status` and emitted on `run_state`.

---

## Eval harness flow

1. `POST /eval/runs` creates an `eval_run`, enqueues cases.
2. `eval_runner` pulls cases, routes each through Tier 1 (deterministic + moderation). Failing-safety cases short-circuit.
3. Tier-2 cases go through `GEvalJudge` (CoT) or `ChainPollJudge` (N=3 majority) over `openai_judge`. All judge calls are recorded as `eval_call` rows with the request hash, response hash, and reasoning.
4. Results aggregate into `eval_cases` + the parent `eval_run`. WS events publish on `channel=eval`.
5. Replay (`services/eval/replay.py` / `cli/eval_replay.py`) re-runs a stored `eval_call` with the same inputs and compares response hashes to detect judge-model drift.

Failing cases (`eval_calls.passed = false`) are the input to the feedback loop: they are curated into a regression dataset, which re-enters the eval harness on future runs.

---

## Observability guarantees

- Trainer subprocess isolation means OOMs, segfaults, and CUDA errors never take down the API.
- WS frames are best-effort with per-connection backpressure — a slow client drops frames rather than blocking the event bus.
- Metric points are batch-inserted for throughput.
- Stale runs and in-flight eval tasks are recovered on lifespan startup and drained on shutdown.
- Checkpoint writes are atomic (temp → rename) so partial files never masquerade as complete.
