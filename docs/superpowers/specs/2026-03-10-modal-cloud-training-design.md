# Modal Cloud Training Integration — Design Spec

## Problem

Local training is too slow on consumer hardware. Users need access to cloud GPUs (A100, H100) without leaving the workbench or changing their workflow. The existing 14-stage training pipeline, observability, and checkpoint management must work identically regardless of where training runs.

## Decision

Integrate Modal as the first cloud training provider. The existing trainer.py runs unmodified inside a Modal container. A dispatcher abstraction enables future providers without changing the orchestrator or frontend.

## User Experience

### Environment Selection

- Dropdown in the training config area near "Start Training": `Local | Modal Cloud`
- `Local` is the default — zero behavior change from today
- Selecting `Modal Cloud`:
  - If no API token configured → inline message: "Modal API token required. Add it in Settings to use cloud training."
  - If token configured → GPU tier selector appears with hourly pricing

### GPU Tier Options

| GPU | VRAM | $/hr |
|-----|------|------|
| T4 | 16 GB | $0.59 |
| A10 | 24 GB | $1.10 |
| A100 40GB | 40 GB | $2.10 |
| A100 80GB | 80 GB | $2.50 |
| H100 | 80 GB | $3.95 |

### API Token Management

- Primary location: Settings page, new "Cloud Training" section
- Token field uses the same pattern as existing AI provider API key (masked input, dedicated "Set Key" button)
- Connection validation on save — shows "Connected" or "Invalid token"
- Fallback: inline prompt when user selects Modal without a configured token

### Run Display

- Badge on run cards: "Local" or "Modal · A100 80GB"
- Stage timeline, metrics charts, log viewer, progress bar all unchanged — same event stream format

## Backend Architecture

### Execution Config Extension

Add `environment` field to `ExecutionConfig`:

```python
class ExecutionConfig(BaseModel):
    environment: Literal["local", "modal"] = "local"
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    modal_gpu_type: Literal["t4", "a10", "a100-40gb", "a100-80gb", "h100"] | None = None
    max_memory_gb: float | None = None
    num_workers: int = 2
```

Modal API token stored via `settings_service` (same as AI provider keys), not in the execution config.

### Training Dispatcher

New service: `backend/app/services/training_dispatcher.py`

Sits between the orchestrator and execution. The orchestrator calls the dispatcher instead of directly spawning a subprocess:

- `environment == "local"` → spawns subprocess exactly as today
- `environment == "modal"` → delegates to `ModalTrainingAdapter`

The dispatcher returns an abstract `TrainingProcess` handle that the orchestrator uses for event streaming and cancellation, regardless of backend.

### Modal Training Adapter

`backend/app/services/cloud/modal_adapter.py`

Responsibilities:

1. **Job submission** — packages trainer code + config into a Modal function call. The trainer.py 14-stage pipeline runs inside a Modal container with the specified GPU.
2. **Event relay** — captures JSON-lines stdout from the remote Modal process and feeds events back through the same `_process_trainer_event()` path the orchestrator already uses.
3. **Checkpoint handling** — training writes checkpoints to a Modal Volume. On completion (or on-demand), the adapter downloads checkpoint artifacts to local project storage.
4. **Cancellation** — maps the orchestrator's cancel request to Modal's job cancellation API.
5. **Heartbeat synthesis** — polls Modal job status periodically and synthesizes heartbeat updates for the watchdog, replacing the local heartbeat file.

### Event Flow

```
Modal Container                    Local Backend                 Frontend
┌──────────────┐                  ┌─────────────────┐          ┌──────────┐
│ trainer.py   │  JSON stdout     │ ModalAdapter     │          │          │
│ (14 stages)  │ ──────────────→  │ (event relay)    │          │          │
│              │                  │       │          │          │          │
│ checkpoints  │  Modal Volume    │       ▼          │   WS     │  Run     │
│ → volume     │ ◄─────────────→  │ orchestrator     │ ───────→ │  viewer  │
│              │                  │ _process_event() │          │          │
└──────────────┘                  │       │          │          │          │
                                  │       ▼          │          │          │
                                  │ DB + WebSocket   │          │          │
                                  └─────────────────┘          └──────────┘
```

The orchestrator's event processing, DB writes, and WebSocket broadcasting are completely unchanged. The only difference is the event source.

### What Stays Unchanged

- All 14 training stages and trainer.py logic
- HuggingFace TrainerCallback (WorkbenchCallback)
- Orchestrator event processing (`_process_trainer_event`)
- Watchdog crash recovery (receives adapted signals)
- All frontend run monitoring (WebSocket, metrics, logs, timeline)
- Model adapter pattern (CausalLMAdapter etc.)
- Checkpoint format and resume-from-checkpoint flow

## Frontend Changes

### Settings Page

New "Cloud Training" section in settings form:

- "Modal" subsection with:
  - API token field (masked, dedicated "Set Key" button)
  - Connection status indicator post-save

### Training Config Area

- Environment dropdown: `Local | Modal Cloud`
- GPU tier selector (visible when Modal selected and token configured)
- Each GPU option shows name, VRAM, and $/hr
- Selection persists per-project in execution config

### Run Cards

- Environment badge: "Local" or "Modal · {gpu_type}"
- No other display changes

## Scope

### In Scope

- Environment selector UI (local vs Modal)
- Modal API token management (settings + inline fallback)
- GPU tier selection with pricing
- Training dispatcher service abstraction
- Modal adapter (job submission, event relay, checkpoint download, cancellation)
- Heartbeat synthesis for watchdog compatibility
- Dataset upload to Modal for remote training

### Out of Scope

- Other cloud providers (adapter interface supports them, not implemented)
- Cost tracking or billing dashboard
- Multi-GPU or distributed training
- Pause/resume on cloud runs (cancel only — resume from checkpoint via new run)
- Remote dataset caching across runs

## Key Files to Create/Modify

### New Files

- `backend/app/services/training_dispatcher.py` — dispatcher abstraction
- `backend/app/services/cloud/__init__.py` — cloud provider package
- `backend/app/services/cloud/modal_adapter.py` — Modal integration
- `frontend/src/types/cloud.ts` — cloud training types
- `frontend/src/api/cloud.ts` — cloud training API client

### Modified Files

- `backend/app/schemas/workbench_config.py` — add environment + modal_gpu_type to ExecutionConfig
- `backend/app/services/orchestrator.py` — use dispatcher instead of direct subprocess spawn
- `backend/app/services/settings_service.py` — store Modal API token
- `backend/app/api/routes/runs.py` — pass environment config through
- `frontend/src/types/config.ts` — add environment and GPU type fields
- `frontend/src/components/config/` — environment selector + GPU picker
- `frontend/src/pages/` — settings page cloud training section
- `frontend/src/api/settings.ts` — Modal token API calls

## Risks

- **Modal SDK changes** — Modal is actively developing; pin SDK version
- **Network reliability** — event relay depends on stable connection to Modal; need reconnection/retry logic
- **Large dataset upload time** — first run with a new dataset pays upload cost; could cache on Modal Volume
- **Checkpoint download size** — LoRA adapters are small (~50-200MB), full model merges are large; default to LoRA-only download
