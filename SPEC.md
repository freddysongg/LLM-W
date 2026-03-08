# LLM Fine-Tuning Workbench -- Product and Technical Specification

**Version:** 1.0
**Date:** 2026-03-07
**Status:** Canonical Reference

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Vision](#2-vision)
3. [Core Product Goals](#3-core-product-goals)
4. [Product Scope](#4-product-scope)
5. [User Profile](#5-user-profile)
6. [Product Principles](#6-product-principles)
7. [System Composition](#7-system-composition)
8. [Architecture and Tech Stack](#8-architecture-and-tech-stack)
9. [Repo Structure](#9-repo-structure)
10. [Deployment Strategy](#10-deployment-strategy)
11. [Data Store and State Management](#11-data-store-and-state-management)
12. [Config System](#12-config-system)
13. [Data Models](#13-data-models)
14. [REST API Design](#14-rest-api-design)
15. [WebSocket Protocol](#15-websocket-protocol)
16. [Dataset Support](#16-dataset-support)
17. [Model Sources and Capability Contract](#17-model-sources-and-capability-contract)
18. [Fine-Tuning Strategy](#18-fine-tuning-strategy)
19. [Run Lifecycle](#19-run-lifecycle)
20. [Run Failure and Recovery](#20-run-failure-and-recovery)
21. [Observability](#21-observability)
22. [Storage Strategy](#22-storage-strategy)
23. [Weights and Architecture Explorer](#23-weights-and-architecture-explorer)
24. [AI Recommendation System](#24-ai-recommendation-system)
25. [Screen Architecture](#25-screen-architecture)
26. [UI Design Direction](#26-ui-design-direction)
27. [Quantization and Local Resource Strategy](#27-quantization-and-local-resource-strategy)
28. [Multi-Model Support Strategy](#28-multi-model-support-strategy)
29. [Non-Functional Requirements](#29-non-functional-requirements)
30. [Risks and Mitigations](#30-risks-and-mitigations)
31. [Phased Implementation Plan](#31-phased-implementation-plan)
32. [Resolved Design Decisions](#32-resolved-design-decisions)
33. [Open Design Questions](#33-open-design-questions)

---

## 1. Product Overview

### 1.1 Name

**LLM Fine-Tuning Workbench**

### 1.2 Product Summary

A local-first, browser-based application that enables a single user to configure, run, observe, compare, and refine LLM fine-tuning workflows from a clean interactive UI. The system is config-driven, execution-aware, and designed to support multiple model architectures over time without being hard-coded to a single model family.

This is not an MVP -- this is a full product build with all features in scope. It is for personal use; competitive differentiation is not a concern.

The application provides:

- Structured configuration management with YAML files and SQLite-backed versioning
- Run orchestration with 14 observable stages
- Detailed observability with real-time metric streaming
- Model architecture exploration with tiered activation inspection
- Limited expert-facing weight inspection and editing
- AI-assisted config recommendations via external LLM APIs
- Reproducible local experimentation
- Run failure recovery with atomic checkpoints and watchdog monitoring

### 1.3 Product Positioning

This product is **not** a cloud MLOps platform, team collaboration suite, or generic enterprise training orchestration tool.

This product **is**:

- A local single-user fine-tuning workbench
- An operator-facing UI for controlled experimentation
- An extensible foundation for more autonomous tuning later
- A visibility-first system for tracing model training behavior
- An operator-grade local fine-tuning workbench with enough visibility that it is naturally teachable

---

## 2. Vision

Build a local-first application that gives an ML engineer or technical operator a practical, inspectable, and flexible way to fine-tune LLMs while being able to see:

- What configuration is active
- What the model architecture looks like
- What stage the pipeline is in
- What metrics are changing
- What artifacts are being generated
- What parts of the model are being updated
- What suggestions an AI assistant would make next
- How one run differs from another

The system must feel like a **control room** for local fine-tuning rather than a static form-based dashboard.

---

## 3. Core Product Goals

### 3.1 Primary Goals

- Enable local fine-tuning through a UI instead of manual script editing
- Make each stage of fine-tuning observable and traceable
- Make all runs reproducible via config snapshots and logged metadata
- Support extensibility across model families and training methods
- Provide expert tooling for model architecture and parameter exploration
- Support AI-assisted refinement through explainable config diffs
- Implement robust failure recovery and crash resilience

### 3.2 Secondary Goals

- Make the system understandable enough to double as a learning tool
- Support future evolution into a more autonomous tuning platform
- Allow future expansion into non-LLM model categories where possible

### 3.3 Success Criteria

The product is successful if a single operator can:

- Select a model and dataset locally
- Configure a run without editing multiple scripts
- Inspect each step of the run lifecycle (all 14 stages)
- Compare runs and understand what changed
- Inspect the model architecture and selected layers
- Review AI-generated suggestions and apply them safely
- Reproduce a run from config and artifacts
- Resume a failed run from the last valid checkpoint
- Monitor storage usage and manage checkpoint retention

---

## 4. Product Scope

### 4.1 In Scope (Full Build)

- Local-first single-user execution
- Supervised fine-tuning as primary mode
- Parameter-efficient fine-tuning (LoRA, QLoRA)
- Support for causal decoder-only LMs as initial model category
- HuggingFace Hub and local file path model sources
- HuggingFace datasets, local JSONL, local CSV, custom formats, multi-turn conversation formats
- Config editing through dedicated screens and raw YAML editing
- YAML config files validated via Pydantic, versioned in SQLite
- Run orchestration with 14 stages
- Run timeline and observability
- Log and metric streaming via WebSocket
- Model architecture explorer
- Selected activation/layer inspection with tiered storage
- Limited expert-facing weight exploration
- AI-assisted config recommendations with approval flow (Claude and OpenAI-compatible APIs)
- Rule-based recommendation engine as fallback
- Run comparison
- Checkpoint and artifact visibility
- Storage budget tracking and cleanup
- Atomic checkpoints and crash recovery
- Docker Compose deployment with native execution support

### 4.2 Designed for Future Expansion

- Additional model categories (seq2seq, encoder-only, multimodal)
- Full fine-tuning
- Multiple fine-tuning strategies
- Quantization-aware local execution modes
- Automated multi-run search
- Ranking and recommendation engines
- Plugin-style trainer backends
- DPO, RLHF, reward modeling
- Team collaboration and shared runs
- Cloud or remote workers
- Auto-queue next run, bounded search over config space, stop conditions, rollback policies

### 4.3 Explicitly Out of Scope

- Multi-user collaboration
- Cloud orchestration
- Remote GPU fleet support
- Production model serving
- Multi-node training
- RLHF and DPO implementation
- Full autonomous retraining loops without approval
- Unrestricted arbitrary raw weight editing across all tensors by default

---

## 5. User Profile

### 5.1 Primary User

A technically capable single operator:

- ML engineer
- MLOps engineer
- Applied AI engineer
- Technical researcher
- Advanced builder experimenting locally

### 5.2 User Mindset

The user wants: control, traceability, reproducibility, observability, direct manipulation where useful, less script juggling, less hidden behavior, no forced cloud dependency.

### 5.3 User Expectations

The user expects the UI to:

- Expose real system behavior
- Not hide the training pipeline behind "magic"
- Make configuration and diffs explicit
- Support expert workflows
- Remain extensible rather than hard-coded

---

## 6. Product Principles

| Principle | Description |
|---|---|
| Local First | All core workflows run locally on a single machine |
| Config Is the Source of Truth | Every meaningful state change maps to a versioned config or logged system event |
| Observable by Default | Every stage produces status, timestamps, metrics, logs, artifacts, and structured metadata |
| Extensible by Design | The system is not architected around one fixed model family |
| Expert-Friendly | Advanced users can inspect layers, parameters, activations, and weight deltas |
| Safe Autonomy | AI can suggest or optionally apply bounded changes, but changes must be explainable and reviewable |
| Clean UI, Not Minimal Capability | Visual design is simple and clean, but product capability is deep |

---

## 7. System Composition

The application is a combination of five unified systems:

### 7.1 Configuration System

A structured config editor with versioning, validation, and diff support. YAML files validated via Pydantic models, versioned in SQLite with full history and diff tracking.

### 7.2 Orchestration System

A job runner that launches, monitors, pauses, stops, and records local fine-tuning runs. Includes watchdog heartbeat monitoring and crash recovery.

### 7.3 Observability System

A local telemetry layer that captures logs, metrics, stage transitions, artifacts, and comparisons. Real-time streaming via WebSocket.

### 7.4 Model Introspection System

A model explorer that shows architecture structure, inspects layers, samples activations (with tiered storage), and surfaces weight changes.

### 7.5 AI Recommendation System

An assistant that consumes run outputs and suggests config changes or next-step actions. Uses external LLM APIs (Claude or OpenAI-compatible) with a rule-based fallback engine.

These systems feel unified in the UI, not like separate disconnected tools.

---

## 8. Architecture and Tech Stack

### 8.1 System Layers

```
+---------------------------------------------------+
|                   UI Layer                         |
|    React + TypeScript + shadcn/ui + Tailwind CSS   |
|    Charts (recharts) + Tree views + Panels         |
+---------------------------------------------------+
|              Communication Layer                   |
|    REST (config CRUD, health) + WebSocket          |
|    (logs, metrics, run state streaming)            |
+---------------------------------------------------+
|              Application Layer                     |
|    Python FastAPI Service                          |
|    Config management, Run lifecycle, Event routing |
|    AI suggestion orchestration                     |
+---------------------------------------------------+
|              Execution Layer                       |
|    Trainer backend (HuggingFace Transformers +     |
|    PEFT + trl), Model adapter backend,             |
|    Local process orchestration                     |
+---------------------------------------------------+
|                Data Layer                          |
|    SQLite (structured data) + Filesystem           |
|    (configs, checkpoints, logs, artifacts)         |
+---------------------------------------------------+
|             Introspection Layer                    |
|    Model graph extraction, Layer metadata,         |
|    Activation capture hooks, Delta analysis        |
+---------------------------------------------------+
```

### 8.2 Frontend Stack

| Technology | Version | Purpose |
|---|---|---|
| React | 18.x | UI framework |
| TypeScript | 5.x | Type-safe development |
| Vite | 5.x | Build tooling and dev server |
| shadcn/ui | latest | Component library (Radix UI primitives) |
| Tailwind CSS | 3.x | Utility-first styling |
| recharts | 2.x | Metric charts and visualizations |
| @tanstack/react-query | 5.x | Server state management, REST caching |
| zustand | 4.x | Client state management |
| react-router-dom | 6.x | Client-side routing |
| cmdk | latest | Command palette |
| react-resizable-panels | latest | Resizable panel layouts |
| @monaco-editor/react | latest | YAML config editing with syntax highlighting |
| lucide-react | latest | Icon set (used by shadcn/ui) |

### 8.3 Backend Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime |
| FastAPI | 0.110+ | HTTP framework (REST + WebSocket) |
| uvicorn | 0.27+ | ASGI server |
| Pydantic | 2.x | Config validation and data models |
| SQLAlchemy | 2.x | ORM for SQLite |
| aiosqlite | 0.20+ | Async SQLite driver |
| PyYAML | 6.x | YAML parsing and serialization |
| transformers | 4.40+ | Model loading and training |
| peft | 0.10+ | LoRA and other PEFT methods |
| trl | 0.8+ | SFT trainer |
| datasets | 2.x | HuggingFace dataset loading |
| torch | 2.2+ | Training backend |
| bitsandbytes | 0.43+ | Quantization support |
| anthropic | 0.25+ | Claude API client |
| openai | 1.x | OpenAI-compatible API client |
| psutil | 5.x | System resource monitoring |
| watchdog | 4.x | File system monitoring |
| deepdiff | 7.x | Config diff computation |
| alembic | 1.13+ | Database migrations |

### 8.4 Communication Protocol

| Channel | Protocol | Use Cases |
|---|---|---|
| REST (HTTP) | JSON over HTTP | Config CRUD, project management, model/dataset metadata, run creation, artifact listing, AI suggestion management, health checks, storage stats |
| WebSocket | JSON frames over WS | Live log streaming, real-time metric streaming, run stage transitions, system resource updates, training progress updates |

---

## 9. Repo Structure

Monorepo layout:

```
llm-interactive/
  frontend/                     # React application
    src/
      components/               # Reusable UI components
        ui/                     # shadcn/ui components
        layout/                 # Shell, sidebar, panels
        charts/                 # Metric visualization
        config/                 # Config editors
        model/                  # Architecture explorer
        runs/                   # Run monitoring
      hooks/                    # Custom React hooks
      stores/                   # Zustand stores
      api/                      # REST client functions
      ws/                       # WebSocket client
      types/                    # TypeScript type definitions
      pages/                    # Route-level page components
      lib/                      # Utilities
    public/
    index.html
    vite.config.ts
    tsconfig.json
    tailwind.config.ts
    package.json

  backend/                      # Python FastAPI service
    app/
      main.py                   # FastAPI app entry point
      api/
        routes/                 # REST route modules
          projects.py
          configs.py
          models.py
          datasets.py
          runs.py
          artifacts.py
          suggestions.py
          settings.py
          storage.py
        websocket/              # WebSocket handlers
          stream.py
      core/
        config.py               # App configuration
        database.py             # SQLite connection and session
        events.py               # Event bus
      models/                   # SQLAlchemy ORM models
        project.py
        config_version.py
        run.py
        run_stage.py
        metric_point.py
        artifact.py
        suggestion.py
        decision_log.py
      schemas/                  # Pydantic request/response schemas
      services/                 # Business logic
        orchestrator.py         # Run lifecycle management
        trainer.py              # Training execution
        introspection.py        # Model inspection
        ai_recommender.py       # AI suggestion engine
        rule_engine.py          # Rule-based recommendations
        watchdog.py             # Process health monitoring
        storage_manager.py      # Storage tracking and cleanup
        config_validator.py     # YAML validation via Pydantic
      adapters/                 # Model adapter interface
        base.py                 # Abstract model adapter
        causal_lm.py            # Causal LM adapter
      workers/                  # Background task runners
    alembic/                    # Database migrations
    tests/
    pyproject.toml
    requirements.txt

  shared/                       # Shared definitions
    config_schema/              # Canonical YAML schema docs
    types/                      # Shared type definitions (reference)

  docker-compose.yml
  Dockerfile.frontend
  Dockerfile.backend
  .env.example
```

---

## 10. Deployment Strategy

### 10.1 Primary: Docker Compose

Docker Compose is the primary deployment method. It is a convenience wrapper -- same ports, same behavior as native execution.

```yaml
# docker-compose.yml
version: "3.9"

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data        # SQLite DB, configs, artifacts
      - ./projects:/app/projects
    environment:
      - DATABASE_URL=sqlite:///app/data/workbench.db
      - PROJECTS_DIR=/app/projects

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "5173:80"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_WS_URL=ws://localhost:8000
```

### 10.2 Native Execution

Both frontend and backend can run natively without Docker.

**Important macOS note:** GPU acceleration via MPS (Metal Performance Shaders) is only accessible when running natively. Docker on macOS cannot pass through MPS. When running under Docker on macOS, training falls back to CPU.

```bash
# Backend (native)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (native)
cd frontend && npm run dev
```

No distinction is made in the application between Docker and native modes -- same ports, same API surface, same behavior.

---

## 11. Data Store and State Management

### 11.1 SQLite as Structured Data Store

All structured data lives in a single SQLite database. SQLite is the source of truth for **what did happen** (run history, metrics, decisions, config versions).

Database location: `data/workbench.db`

### 11.2 Runtime State Separation

| State Type | Where It Lives | Persistence | Access Pattern |
|---|---|---|---|
| Config (model, dataset, training params) | YAML file on disk, versioned in SQLite `config_versions` table | Persistent | Read on run start, UI edits write YAML, system reads and versions |
| Run state (status, stage, progress) | SQLite `runs` table | Persistent | Updated by orchestrator, read by frontend via REST and WebSocket |
| Live metrics (loss, grad norm, lr, etc.) | Written to SQLite `metric_points` in real-time | Persistent | Streamed to frontend via WebSocket, queryable via REST |
| System state (GPU available, model loaded) | Ephemeral -- queried on demand | Not persisted | Queried via REST health/status endpoints |
| Artifacts (checkpoints, logs, exports) | Filesystem with paths tracked in SQLite `artifacts` table | Persistent | Written by trainer, browsed via REST |

### 11.3 Source of Truth Rules

- **Config** is the source of truth for "what should happen"
- **SQLite** is the source of truth for "what did happen"
- **Filesystem** is where heavy artifacts live (checkpoints, model weights, log files)

---

## 12. Config System

### 12.1 Config Format

All configuration is stored as YAML files on disk. YAML files are validated against Pydantic models on every read and write.

### 12.2 Config Versioning (SQLite-Backed)

Each config save creates a new row in the `config_versions` table. The system never overwrites history.

**`config_versions` table schema:**

```sql
CREATE TABLE config_versions (
    id              TEXT PRIMARY KEY,           -- UUID
    project_id      TEXT NOT NULL REFERENCES projects(id),
    version_number  INTEGER NOT NULL,           -- Monotonically increasing per project
    yaml_blob       TEXT NOT NULL,              -- Full YAML content
    yaml_hash       TEXT NOT NULL,              -- SHA-256 of yaml_blob for dedup
    diff_from_prev  TEXT,                       -- JSON diff from previous version (null for first)
    source_tag      TEXT NOT NULL,              -- 'user' | 'ai_suggestion' | 'system'
    source_detail   TEXT,                       -- Optional: suggestion ID, migration name, etc.
    created_at      TEXT NOT NULL,              -- ISO 8601 timestamp
    UNIQUE(project_id, version_number)
);
```

**Versioning flow:**

1. User edits config in UI (form fields or Monaco YAML editor)
2. Frontend sends updated config to backend via REST
3. Backend validates YAML against Pydantic model
4. Backend computes diff from current version
5. Backend writes new YAML file to disk
6. Backend inserts new row in `config_versions` with full YAML blob, diff, and source tag
7. Backend returns new version ID to frontend

### 12.3 Config Schema (Pydantic Models)

```python
from pydantic import BaseModel, Field
from typing import Literal


class ProjectConfig(BaseModel):
    name: str
    description: str = ""
    mode: Literal["single_user_local"] = "single_user_local"


class ModelConfig(BaseModel):
    source: Literal["huggingface", "local"]
    model_id: str                                    # HF repo ID or local path
    family: Literal["causal_lm", "seq2seq", "encoder_only"] = "causal_lm"
    revision: str = "main"                           # Git revision for HF models
    trust_remote_code: bool = False
    torch_dtype: Literal["auto", "float16", "bfloat16", "float32"] = "auto"


class DatasetConfig(BaseModel):
    source: Literal["huggingface", "local_jsonl", "local_csv", "custom"]
    dataset_id: str                                  # HF dataset ID or local file path
    train_split: str = "train"
    eval_split: str | None = "validation"
    input_field: str = "prompt"
    target_field: str = "response"
    format: Literal["default", "sharegpt", "openai", "alpaca", "custom"] = "default"
    format_mapping: dict[str, str] | None = None     # Field remapping for custom formats
    filter_expression: str | None = None             # Optional filter for dataset subsets
    max_samples: int | None = None                   # Optional cap on sample count
    subset: str | None = None                        # HF dataset subset/config name


class PreprocessingConfig(BaseModel):
    max_seq_length: int = 512
    truncation: bool = True
    packing: bool = False
    padding: Literal["max_length", "longest", "do_not_pad"] = "longest"


class TrainingConfig(BaseModel):
    task_type: Literal["sft"] = "sft"
    epochs: int = 2
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    eval_steps: int = 50
    save_steps: int = 100
    logging_steps: int = 10
    seed: int = 42
    resume_from_checkpoint: str | None = None


class OptimizationConfig(BaseModel):
    optimizer: Literal["adamw", "adam", "sgd", "adafactor", "paged_adamw_8bit"] = "adamw"
    scheduler: Literal["cosine", "linear", "constant", "constant_with_warmup", "cosine_with_restarts"] = "cosine"
    warmup_ratio: float = 0.03
    warmup_steps: int = 0
    gradient_checkpointing: bool = True
    mixed_precision: Literal["no", "fp16", "bf16"] = "bf16"


class AdaptersConfig(BaseModel):
    enabled: bool = True
    type: Literal["lora", "qlora"] = "lora"
    rank: int = 8
    alpha: int = 16
    dropout: float = 0.05
    target_modules: list[str] = ["q_proj", "v_proj"]
    bias: Literal["none", "all", "lora_only"] = "none"
    task_type: Literal["CAUSAL_LM", "SEQ_2_SEQ_LM"] = "CAUSAL_LM"


class QuantizationConfig(BaseModel):
    enabled: bool = False
    mode: Literal["4bit", "8bit"] = "4bit"
    compute_dtype: Literal["float16", "bfloat16"] = "bfloat16"
    quant_type: Literal["nf4", "fp4"] = "nf4"
    double_quant: bool = True


class ObservabilityConfig(BaseModel):
    log_every_steps: int = 10
    capture_grad_norm: bool = True
    capture_memory: bool = True
    capture_activation_samples: bool = True
    capture_weight_deltas: bool = True
    observability_level: Literal["minimal", "standard", "deep", "expert"] = "standard"


class AIAssistantConfig(BaseModel):
    enabled: bool = True
    provider: Literal["anthropic", "openai_compatible"] = "anthropic"
    mode: Literal["suggest_only", "suggest_and_draft"] = "suggest_only"
    allow_config_diffs: bool = True
    auto_analyze_on_completion: bool = True


class ExecutionConfig(BaseModel):
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    max_memory_gb: float | None = None
    num_workers: int = 2


class CheckpointRetentionConfig(BaseModel):
    keep_last_n: int = 3
    always_keep_best_eval: bool = True
    always_keep_final: bool = True
    delete_intermediates_after_completion: bool = True


class IntrospectionConfig(BaseModel):
    architecture_view: bool = True
    editable_weight_scope: Literal["disabled", "bounded_expert_mode"] = "bounded_expert_mode"
    activation_probe_samples: int = 3
    activation_storage: Literal["summary_only", "on_demand_full"] = "summary_only"


class WorkbenchConfig(BaseModel):
    """Top-level config validated by Pydantic."""
    project: ProjectConfig
    model: ModelConfig
    dataset: DatasetConfig
    preprocessing: PreprocessingConfig
    training: TrainingConfig
    optimization: OptimizationConfig
    adapters: AdaptersConfig
    quantization: QuantizationConfig
    observability: ObservabilityConfig
    ai_assistant: AIAssistantConfig
    execution: ExecutionConfig
    checkpoint_retention: CheckpointRetentionConfig
    introspection: IntrospectionConfig
```

### 12.4 Full YAML Example

```yaml
project:
  name: my-sft-experiment
  description: "Fine-tuning Llama 3 on custom instruction data"
  mode: single_user_local

model:
  source: huggingface
  model_id: meta-llama/Meta-Llama-3-8B
  family: causal_lm
  revision: main
  trust_remote_code: false
  torch_dtype: auto

dataset:
  source: local_jsonl
  dataset_id: /path/to/training_data.jsonl
  train_split: train
  eval_split: validation
  input_field: prompt
  target_field: response
  format: sharegpt
  format_mapping:
    conversations: messages
    role_key: from
    content_key: value
  filter_expression: null
  max_samples: null
  subset: null

preprocessing:
  max_seq_length: 2048
  truncation: true
  packing: false
  padding: longest

training:
  task_type: sft
  epochs: 3
  batch_size: 4
  gradient_accumulation_steps: 4
  learning_rate: 0.0002
  weight_decay: 0.01
  max_grad_norm: 1.0
  eval_steps: 50
  save_steps: 100
  logging_steps: 10
  seed: 42
  resume_from_checkpoint: null

optimization:
  optimizer: paged_adamw_8bit
  scheduler: cosine
  warmup_ratio: 0.03
  warmup_steps: 0
  gradient_checkpointing: true
  mixed_precision: bf16

adapters:
  enabled: true
  type: lora
  rank: 16
  alpha: 32
  dropout: 0.05
  target_modules:
    - q_proj
    - k_proj
    - v_proj
    - o_proj
    - gate_proj
    - up_proj
    - down_proj
  bias: none
  task_type: CAUSAL_LM

quantization:
  enabled: true
  mode: 4bit
  compute_dtype: bfloat16
  quant_type: nf4
  double_quant: true

observability:
  log_every_steps: 10
  capture_grad_norm: true
  capture_memory: true
  capture_activation_samples: true
  capture_weight_deltas: true
  observability_level: standard

ai_assistant:
  enabled: true
  provider: anthropic
  mode: suggest_only
  allow_config_diffs: true
  auto_analyze_on_completion: true

execution:
  device: auto
  max_memory_gb: 24
  num_workers: 2

checkpoint_retention:
  keep_last_n: 3
  always_keep_best_eval: true
  always_keep_final: true
  delete_intermediates_after_completion: true

introspection:
  architecture_view: true
  editable_weight_scope: bounded_expert_mode
  activation_probe_samples: 3
  activation_storage: summary_only
```

---

## 13. Data Models

All models are stored in SQLite via SQLAlchemy ORM. IDs are UUIDs stored as TEXT. Timestamps are ISO 8601 strings.

### 13.1 Project

```sql
CREATE TABLE projects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL DEFAULT '',
    directory_path  TEXT NOT NULL,               -- Absolute path to project dir
    active_config_version_id TEXT REFERENCES config_versions(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
```

| Field | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| name | TEXT | Unique project name |
| description | TEXT | Human-readable description |
| directory_path | TEXT | Absolute filesystem path to project directory |
| active_config_version_id | TEXT (UUID, FK) | Currently active config version |
| created_at | TEXT (ISO 8601) | Creation timestamp |
| updated_at | TEXT (ISO 8601) | Last modification timestamp |

### 13.2 ConfigVersion

```sql
CREATE TABLE config_versions (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    version_number  INTEGER NOT NULL,
    yaml_blob       TEXT NOT NULL,
    yaml_hash       TEXT NOT NULL,
    diff_from_prev  TEXT,
    source_tag      TEXT NOT NULL CHECK(source_tag IN ('user', 'ai_suggestion', 'system')),
    source_detail   TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(project_id, version_number)
);
```

| Field | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| project_id | TEXT (UUID, FK) | Owning project |
| version_number | INTEGER | Monotonically increasing per project |
| yaml_blob | TEXT | Complete YAML config content |
| yaml_hash | TEXT | SHA-256 hash of yaml_blob for deduplication |
| diff_from_prev | TEXT (JSON) | Structured diff from previous version, null for first version |
| source_tag | TEXT | Origin: `user`, `ai_suggestion`, or `system` |
| source_detail | TEXT | Optional detail (suggestion ID, migration name) |
| created_at | TEXT (ISO 8601) | Creation timestamp |

### 13.3 ModelProfile

```sql
CREATE TABLE model_profiles (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    source              TEXT NOT NULL,           -- 'huggingface' | 'local'
    model_id            TEXT NOT NULL,           -- HF repo or local path
    family              TEXT NOT NULL,           -- 'causal_lm' | 'seq2seq' | 'encoder_only'
    architecture_name   TEXT,                    -- e.g. 'LlamaForCausalLM'
    parameter_count     INTEGER,                 -- Total parameter count
    trainable_count     INTEGER,                 -- Trainable parameter count (after adapter)
    tokenizer_type      TEXT,
    vocab_size          INTEGER,
    max_position_embeddings INTEGER,
    hidden_size         INTEGER,
    num_layers          INTEGER,
    num_attention_heads INTEGER,
    capabilities_json   TEXT,                    -- JSON: supported tasks, adapters, quant modes
    resource_estimate_json TEXT,                 -- JSON: estimated VRAM, memory, disk
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
```

### 13.4 DatasetProfile

```sql
CREATE TABLE dataset_profiles (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    source              TEXT NOT NULL,
    dataset_id          TEXT NOT NULL,
    fingerprint         TEXT,                    -- Hash for reproducibility
    train_size          INTEGER,
    eval_size           INTEGER,
    field_mapping_json  TEXT,                    -- JSON: field name mappings
    token_stats_json    TEXT,                    -- JSON: min, max, mean, median, p95 token lengths
    quality_warnings    TEXT,                    -- JSON: list of warnings (duplicates, malformed, etc.)
    format              TEXT NOT NULL DEFAULT 'default',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
```

### 13.5 Run

```sql
CREATE TABLE runs (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    config_version_id   TEXT NOT NULL REFERENCES config_versions(id),
    parent_run_id       TEXT REFERENCES runs(id),  -- Non-null if resumed from a previous run
    status              TEXT NOT NULL DEFAULT 'pending',
                        -- 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused'
    current_stage       TEXT,                    -- Name of current run stage
    current_step        INTEGER DEFAULT 0,
    total_steps         INTEGER,
    progress_pct        REAL DEFAULT 0.0,
    started_at          TEXT,
    completed_at        TEXT,
    failure_reason      TEXT,
    failure_stage       TEXT,
    last_checkpoint_path TEXT,
    heartbeat_path      TEXT,                    -- Path to heartbeat file
    pid                 INTEGER,                 -- Process ID of trainer
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX idx_runs_project ON runs(project_id);
CREATE INDEX idx_runs_status ON runs(status);
```

### 13.6 RunStage

```sql
CREATE TABLE run_stages (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    stage_name      TEXT NOT NULL,
    stage_order     INTEGER NOT NULL,            -- 1-14
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
    started_at      TEXT,
    completed_at    TEXT,
    duration_ms     INTEGER,
    warnings_json   TEXT,                        -- JSON array of warning strings
    output_summary  TEXT,                        -- Free-text summary of stage output
    log_tail        TEXT,                        -- Last N lines of stage-specific logs
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_run_stages_run ON run_stages(run_id);
```

### 13.7 MetricPoint

```sql
CREATE TABLE metric_points (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    step            INTEGER NOT NULL,
    epoch           REAL,
    metric_name     TEXT NOT NULL,
    metric_value    REAL NOT NULL,
    stage_name      TEXT,
    recorded_at     TEXT NOT NULL
);

CREATE INDEX idx_metrics_run_step ON metric_points(run_id, step);
CREATE INDEX idx_metrics_run_name ON metric_points(run_id, metric_name);
```

Metric names include: `train_loss`, `eval_loss`, `learning_rate`, `grad_norm`, `tokens_per_second`, `step_time_ms`, `gpu_memory_used_mb`, `gpu_memory_allocated_mb`, `cpu_memory_used_mb`.

### 13.8 Artifact

```sql
CREATE TABLE artifacts (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    project_id      TEXT NOT NULL REFERENCES projects(id),
    artifact_type   TEXT NOT NULL,
                    -- 'checkpoint' | 'config_snapshot' | 'eval_output' | 'metric_export'
                    -- | 'comparison_summary' | 'ai_recommendation' | 'log_file'
                    -- | 'activation_summary' | 'weight_delta'
    file_path       TEXT NOT NULL,               -- Relative to project directory
    file_size_bytes INTEGER,
    metadata_json   TEXT,                        -- JSON: type-specific metadata
    is_retained     INTEGER NOT NULL DEFAULT 1,  -- 0 = marked for cleanup
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_artifacts_run ON artifacts(run_id);
CREATE INDEX idx_artifacts_type ON artifacts(artifact_type);
```

### 13.9 AISuggestion

```sql
CREATE TABLE ai_suggestions (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    source_run_id   TEXT REFERENCES runs(id),    -- Run that triggered this suggestion
    provider        TEXT NOT NULL,               -- 'anthropic' | 'openai_compatible' | 'rule_engine'
    config_diff     TEXT NOT NULL,               -- JSON structured diff
    rationale       TEXT NOT NULL,
    evidence_json   TEXT,                        -- JSON: references to metrics, runs, etc.
    expected_effect TEXT,
    tradeoffs       TEXT,
    confidence      REAL,                        -- 0.0 to 1.0
    risk_level      TEXT,                        -- 'low' | 'medium' | 'high'
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- 'pending' | 'accepted' | 'rejected' | 'applied' | 'expired'
    applied_config_version_id TEXT REFERENCES config_versions(id),
    created_at      TEXT NOT NULL,
    resolved_at     TEXT
);

CREATE INDEX idx_suggestions_project ON ai_suggestions(project_id);
CREATE INDEX idx_suggestions_status ON ai_suggestions(status);
```

### 13.10 DecisionLog

```sql
CREATE TABLE decision_logs (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    action_type     TEXT NOT NULL,
                    -- 'config_edit' | 'suggestion_accepted' | 'suggestion_rejected'
                    -- | 'run_launched' | 'run_cancelled' | 'run_resumed'
                    -- | 'weight_edit' | 'checkpoint_deleted' | 'artifact_cleanup'
    actor           TEXT NOT NULL,               -- 'user' | 'system' | 'ai'
    target_type     TEXT,                        -- 'config' | 'run' | 'suggestion' | 'checkpoint'
    target_id       TEXT,                        -- ID of affected entity
    before_state    TEXT,                        -- JSON snapshot before
    after_state     TEXT,                        -- JSON snapshot after
    notes           TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_decisions_project ON decision_logs(project_id);
```

### 13.11 ActivationSnapshot

```sql
CREATE TABLE activation_snapshots (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    checkpoint_step INTEGER NOT NULL,
    layer_name      TEXT NOT NULL,
    summary_json    TEXT NOT NULL,               -- JSON: mean, std, min, max, histogram bins
    full_tensor_path TEXT,                       -- Filesystem path, null if not captured
    sample_input_hash TEXT,                      -- Hash of input used for activation
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_activations_run ON activation_snapshots(run_id);
CREATE INDEX idx_activations_layer ON activation_snapshots(layer_name);
```

### 13.12 StorageRecord

```sql
CREATE TABLE storage_records (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    category        TEXT NOT NULL,               -- 'checkpoints' | 'logs' | 'activations' | 'exports' | 'models'
    total_bytes     INTEGER NOT NULL DEFAULT 0,
    file_count      INTEGER NOT NULL DEFAULT 0,
    last_computed_at TEXT NOT NULL
);

CREATE INDEX idx_storage_project ON storage_records(project_id);
```

---

## 14. REST API Design

Base URL: `http://localhost:8000/api/v1`

All responses use JSON. Error responses follow the shape:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error description",
    "details": {}
  }
}
```

### 14.1 Health

| Method | Path | Description | Response |
|---|---|---|---|
| GET | `/health` | Basic health check | `{ "status": "ok", "version": "1.0.0" }` |
| GET | `/health/system` | System resource snapshot | GPU availability, memory, disk, loaded model info |

**GET /health/system response:**

```json
{
  "gpu_available": true,
  "gpu_name": "Apple M2 Max",
  "gpu_memory_total_mb": 32768,
  "gpu_memory_used_mb": 4096,
  "cpu_count": 12,
  "ram_total_mb": 65536,
  "ram_used_mb": 24000,
  "disk_free_gb": 150.5,
  "model_loaded": false,
  "active_run_id": null,
  "torch_device": "mps",
  "torch_version": "2.2.0",
  "cuda_available": false,
  "mps_available": true
}
```

### 14.2 Projects

| Method | Path | Description |
|---|---|---|
| GET | `/projects` | List all projects |
| POST | `/projects` | Create new project |
| GET | `/projects/{project_id}` | Get project details |
| PATCH | `/projects/{project_id}` | Update project metadata |
| DELETE | `/projects/{project_id}` | Delete project (with confirmation flag) |
| GET | `/projects/{project_id}/storage` | Get storage usage breakdown |

**POST /projects request:**

```json
{
  "name": "my-sft-experiment",
  "description": "Fine-tuning experiment with Llama 3"
}
```

**POST /projects response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "my-sft-experiment",
  "description": "Fine-tuning experiment with Llama 3",
  "directory_path": "/app/projects/my-sft-experiment",
  "active_config_version_id": "660e8400-e29b-41d4-a716-446655440001",
  "created_at": "2026-03-07T10:00:00Z",
  "updated_at": "2026-03-07T10:00:00Z"
}
```

### 14.3 Configs

| Method | Path | Description |
|---|---|---|
| GET | `/projects/{project_id}/configs` | List config versions (paginated) |
| GET | `/projects/{project_id}/configs/active` | Get active config version |
| GET | `/projects/{project_id}/configs/{version_id}` | Get specific config version |
| PUT | `/projects/{project_id}/configs` | Save new config version (validates, diffs, and stores) |
| GET | `/projects/{project_id}/configs/{version_id}/diff/{other_version_id}` | Diff two config versions |
| POST | `/projects/{project_id}/configs/{version_id}/validate` | Validate config without saving |
| GET | `/projects/{project_id}/configs/{version_id}/yaml` | Get raw YAML content |

**PUT /projects/{project_id}/configs request:**

```json
{
  "yaml_content": "project:\n  name: my-experiment\n  ...",
  "source_tag": "user",
  "source_detail": null
}
```

**PUT /projects/{project_id}/configs response:**

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "version_number": 5,
  "yaml_hash": "sha256:abc123...",
  "diff_from_prev": {
    "changed": {
      "training.learning_rate": { "old": 0.0002, "new": 0.0001 },
      "adapters.rank": { "old": 8, "new": 16 }
    }
  },
  "source_tag": "user",
  "created_at": "2026-03-07T14:30:00Z"
}
```

### 14.4 Models

| Method | Path | Description |
|---|---|---|
| POST | `/projects/{project_id}/models/resolve` | Resolve and profile a model (HF or local) |
| GET | `/projects/{project_id}/models/profile` | Get current model profile |
| GET | `/projects/{project_id}/models/architecture` | Get model architecture tree |
| GET | `/projects/{project_id}/models/layers/{layer_name}` | Get layer detail (params, dtype, shape) |
| POST | `/projects/{project_id}/models/activations` | Capture activations for a sample input |
| GET | `/projects/{project_id}/models/activations/{snapshot_id}` | Get activation snapshot |
| POST | `/projects/{project_id}/models/activations/{snapshot_id}/full` | Request full tensor capture |

**POST /projects/{project_id}/models/resolve request:**

```json
{
  "source": "huggingface",
  "model_id": "meta-llama/Meta-Llama-3-8B",
  "revision": "main",
  "trust_remote_code": false
}
```

**GET /projects/{project_id}/models/architecture response:**

```json
{
  "model_id": "meta-llama/Meta-Llama-3-8B",
  "architecture_name": "LlamaForCausalLM",
  "total_parameters": 8030000000,
  "trainable_parameters": 4194304,
  "tree": {
    "name": "LlamaForCausalLM",
    "type": "model",
    "children": [
      {
        "name": "model",
        "type": "module",
        "children": [
          {
            "name": "embed_tokens",
            "type": "Embedding",
            "params": 524288000,
            "trainable": false,
            "dtype": "bfloat16",
            "shape": [128256, 4096]
          },
          {
            "name": "layers",
            "type": "ModuleList",
            "children": ["...32 decoder layers..."]
          }
        ]
      }
    ]
  }
}
```

### 14.5 Datasets

| Method | Path | Description |
|---|---|---|
| POST | `/projects/{project_id}/datasets/resolve` | Resolve and profile a dataset |
| GET | `/projects/{project_id}/datasets/profile` | Get current dataset profile |
| GET | `/projects/{project_id}/datasets/samples` | Get sample rows (paginated) |
| GET | `/projects/{project_id}/datasets/token-stats` | Get token length statistics |
| POST | `/projects/{project_id}/datasets/preview-transform` | Preview preprocessing transformation |

### 14.6 Runs

| Method | Path | Description |
|---|---|---|
| GET | `/projects/{project_id}/runs` | List runs (paginated, filterable by status) |
| POST | `/projects/{project_id}/runs` | Launch new run from active config |
| GET | `/projects/{project_id}/runs/{run_id}` | Get run details |
| POST | `/projects/{project_id}/runs/{run_id}/cancel` | Cancel running run |
| POST | `/projects/{project_id}/runs/{run_id}/pause` | Pause running run |
| POST | `/projects/{project_id}/runs/{run_id}/resume` | Resume from last valid checkpoint (creates new run linked to parent) |
| GET | `/projects/{project_id}/runs/{run_id}/stages` | Get all stages for a run |
| GET | `/projects/{project_id}/runs/{run_id}/metrics` | Get metrics (filterable by name, step range) |
| GET | `/projects/{project_id}/runs/{run_id}/logs` | Get logs (paginated, filterable by severity/stage) |
| GET | `/projects/{project_id}/runs/compare` | Compare two or more runs (query params: `run_ids`) |

**POST /projects/{project_id}/runs request:**

```json
{
  "config_version_id": "770e8400-e29b-41d4-a716-446655440002"
}
```

**POST /projects/{project_id}/runs response:**

```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "config_version_id": "770e8400-e29b-41d4-a716-446655440002",
  "status": "pending",
  "current_stage": null,
  "created_at": "2026-03-07T15:00:00Z"
}
```

**POST /projects/{project_id}/runs/{run_id}/resume response:**

```json
{
  "new_run_id": "990e8400-e29b-41d4-a716-446655440004",
  "parent_run_id": "880e8400-e29b-41d4-a716-446655440003",
  "resume_from_checkpoint": "/projects/my-exp/checkpoints/checkpoint-500",
  "resume_from_step": 500,
  "status": "pending"
}
```

**GET /projects/{project_id}/runs/compare response:**

```json
{
  "runs": ["run_id_1", "run_id_2"],
  "config_diff": {
    "changed": {
      "training.learning_rate": { "run_1": 0.0002, "run_2": 0.0001 }
    }
  },
  "metric_comparison": {
    "train_loss": {
      "run_1": { "final": 0.45, "min": 0.42, "trend": "decreasing" },
      "run_2": { "final": 0.38, "min": 0.35, "trend": "decreasing" }
    }
  },
  "artifact_comparison": {
    "run_1": { "checkpoints": 5, "total_size_mb": 1200 },
    "run_2": { "checkpoints": 3, "total_size_mb": 800 }
  }
}
```

### 14.7 Artifacts

| Method | Path | Description |
|---|---|---|
| GET | `/projects/{project_id}/artifacts` | List artifacts (filterable by run, type) |
| GET | `/projects/{project_id}/artifacts/{artifact_id}` | Get artifact metadata |
| GET | `/projects/{project_id}/artifacts/{artifact_id}/download` | Download artifact file |
| DELETE | `/projects/{project_id}/artifacts/{artifact_id}` | Delete artifact |
| POST | `/projects/{project_id}/artifacts/cleanup` | Run retention policy cleanup |

### 14.8 AI Suggestions

| Method | Path | Description |
|---|---|---|
| GET | `/projects/{project_id}/suggestions` | List suggestions (filterable by status) |
| POST | `/projects/{project_id}/suggestions/generate` | Trigger suggestion generation for a run |
| GET | `/projects/{project_id}/suggestions/{suggestion_id}` | Get suggestion details |
| POST | `/projects/{project_id}/suggestions/{suggestion_id}/accept` | Accept suggestion (creates new config version) |
| POST | `/projects/{project_id}/suggestions/{suggestion_id}/reject` | Reject suggestion |

### 14.9 Settings

| Method | Path | Description |
|---|---|---|
| GET | `/settings` | Get global settings |
| PATCH | `/settings` | Update global settings |
| POST | `/settings/ai/test` | Test AI provider connectivity |

**GET /settings response:**

```json
{
  "ai_provider": "anthropic",
  "ai_api_key_set": true,
  "ai_model_id": "claude-sonnet-4-20250514",
  "ai_base_url": null,
  "default_projects_dir": "/app/projects",
  "storage_warning_threshold_gb": 50,
  "watchdog_stale_timeout_seconds": 120,
  "watchdog_heartbeat_interval_seconds": 10
}
```

### 14.10 Storage

| Method | Path | Description |
|---|---|---|
| GET | `/projects/{project_id}/storage` | Get storage breakdown for project |
| GET | `/storage/total` | Get total storage usage across all projects |
| POST | `/projects/{project_id}/storage/cleanup` | Run cleanup based on retention policy |

**GET /projects/{project_id}/storage response:**

```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_bytes": 5368709120,
  "breakdown": {
    "checkpoints": { "bytes": 4294967296, "file_count": 12 },
    "logs": { "bytes": 52428800, "file_count": 45 },
    "activations": { "bytes": 10485760, "file_count": 200 },
    "exports": { "bytes": 104857600, "file_count": 8 },
    "configs": { "bytes": 51200, "file_count": 30 }
  },
  "per_run": [
    {
      "run_id": "880e8400-e29b-41d4-a716-446655440003",
      "total_bytes": 1073741824,
      "checkpoint_count": 5,
      "status": "completed"
    }
  ],
  "retention_policy": {
    "keep_last_n": 3,
    "reclaimable_bytes": 2147483648,
    "reclaimable_checkpoints": 8
  }
}
```

---

## 15. WebSocket Protocol

### 15.1 Connection

Endpoint: `ws://localhost:8000/ws/{project_id}`

Optional query parameters:

- `run_id` -- subscribe only to events for a specific run
- `channels` -- comma-separated list of channels to subscribe to

### 15.2 Message Format

All WebSocket messages are JSON frames with the following envelope:

```json
{
  "channel": "metrics",
  "event": "metric_recorded",
  "run_id": "880e8400-e29b-41d4-a716-446655440003",
  "timestamp": "2026-03-07T15:05:23.456Z",
  "payload": {}
}
```

### 15.3 Channels and Events

#### Channel: `run_state`

| Event | Payload | Description |
|---|---|---|
| `run_created` | `{ run_id, config_version_id, status }` | New run created |
| `stage_entered` | `{ run_id, stage_name, stage_order }` | Run entered a new stage |
| `stage_completed` | `{ run_id, stage_name, duration_ms, output_summary }` | Stage completed |
| `stage_failed` | `{ run_id, stage_name, error_message }` | Stage failed |
| `progress_update` | `{ run_id, current_step, total_steps, progress_pct, epoch }` | Training progress |
| `run_completed` | `{ run_id, total_duration_ms, final_metrics }` | Run finished successfully |
| `run_failed` | `{ run_id, failure_reason, failure_stage, last_step }` | Run failed |
| `run_cancelled` | `{ run_id }` | Run was cancelled by user |
| `run_paused` | `{ run_id, paused_at_step }` | Run was paused |

#### Channel: `metrics`

| Event | Payload | Description |
|---|---|---|
| `metric_recorded` | `{ run_id, step, epoch, metrics: { name: value, ... } }` | Batch of metrics at a step |

Example payload:

```json
{
  "run_id": "880e8400-e29b-41d4-a716-446655440003",
  "step": 150,
  "epoch": 0.75,
  "metrics": {
    "train_loss": 0.423,
    "learning_rate": 0.000185,
    "grad_norm": 1.23,
    "tokens_per_second": 4500,
    "step_time_ms": 890,
    "gpu_memory_used_mb": 18432
  }
}
```

#### Channel: `logs`

| Event | Payload | Description |
|---|---|---|
| `log_line` | `{ run_id, severity, stage, message, source }` | Single log line |
| `log_batch` | `{ run_id, lines: [{ severity, stage, message, source }] }` | Batch of log lines |

Severity levels: `debug`, `info`, `warning`, `error`, `critical`

#### Channel: `system`

| Event | Payload | Description |
|---|---|---|
| `resource_update` | `{ gpu_memory_used_mb, gpu_utilization_pct, cpu_pct, ram_used_mb }` | Periodic system resource snapshot |
| `checkpoint_saved` | `{ run_id, step, path, size_bytes }` | Checkpoint written to disk |
| `artifact_created` | `{ run_id, artifact_type, path }` | New artifact created |

### 15.4 Client-to-Server Messages

| Message Type | Payload | Description |
|---|---|---|
| `subscribe` | `{ channels: ["metrics", "logs", "run_state", "system"] }` | Subscribe to channels |
| `unsubscribe` | `{ channels: ["logs"] }` | Unsubscribe from channels |
| `ping` | `{}` | Keepalive ping |

### 15.5 Connection Lifecycle

1. Client connects to `ws://localhost:8000/ws/{project_id}`
2. Server sends `{ "channel": "system", "event": "connected", "payload": { "project_id": "..." } }`
3. Client sends `subscribe` message with desired channels
4. Server streams events as they occur
5. Client can send `ping` for keepalive (server responds with `pong`)
6. On disconnect, all subscriptions are cleaned up

---

## 16. Dataset Support

### 16.1 Supported Sources

| Source | Identifier | Description |
|---|---|---|
| HuggingFace datasets | HF dataset ID (e.g., `tatsu-lab/alpaca`) | Loaded via `datasets` library |
| Local JSONL | Filesystem path (e.g., `/data/train.jsonl`) | Each line is a JSON object |
| Local CSV | Filesystem path (e.g., `/data/train.csv`) | Standard CSV with header row |
| Custom formats | Filesystem path + transformation config | Requires format mapping in config |

### 16.2 Multi-Turn Conversation Formats

The system supports multi-turn conversation data in two primary formats:

**ShareGPT format:**

```json
{
  "conversations": [
    { "from": "human", "value": "What is machine learning?" },
    { "from": "gpt", "value": "Machine learning is..." },
    { "from": "human", "value": "Can you give an example?" },
    { "from": "gpt", "value": "Sure, consider..." }
  ]
}
```

**OpenAI format:**

```json
{
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "What is machine learning?" },
    { "role": "assistant", "content": "Machine learning is..." }
  ]
}
```

The `format_mapping` field in `DatasetConfig` handles non-standard field names:

```yaml
dataset:
  format: sharegpt
  format_mapping:
    conversations: dialogues       # Map 'dialogues' -> 'conversations'
    role_key: speaker              # Map 'speaker' -> 'from'
    content_key: text              # Map 'text' -> 'value'
```

### 16.3 Filtered Subsets

Users can filter large datasets using the `filter_expression` field. This accepts a Python expression evaluated against each row:

```yaml
dataset:
  filter_expression: "len(row['response']) > 50 and row['category'] == 'science'"
  max_samples: 10000
```

### 16.4 Schema Flexibility

The dataset schema is intentionally loose. The system does not enforce a rigid schema but instead:

- Attempts to auto-detect field names
- Allows arbitrary field mapping via `format_mapping`
- Reports quality warnings for unmapped or unexpected fields
- Previews transformations before committing

### 16.5 Dataset Profiling

When a dataset is resolved, the backend profiles it and stores:

- Total row counts per split
- Token length statistics (min, max, mean, median, p95, p99)
- Duplicate detection (exact and near-duplicate)
- Malformed example identification (missing fields, empty values)
- Format validation results
- Truncation projections based on `max_seq_length`

---

## 17. Model Sources and Capability Contract

### 17.1 Supported Sources

| Source | Resolution | Description |
|---|---|---|
| HuggingFace Hub | `model_id` = HF repo ID (e.g., `meta-llama/Meta-Llama-3-8B`) | Downloaded and cached via `transformers` |
| Local file path | `model_id` = absolute filesystem path | Must contain valid model config and weights |

### 17.2 Model Capability Contract

Each model integration exposes a capability contract. The UI depends on this contract rather than assuming any specific model architecture.

```python
from abc import ABC, abstractmethod
from typing import Any


class ModelAdapter(ABC):
    """
    Abstract interface for model integrations.
    Each model family implements this contract.
    """

    @abstractmethod
    def load_model(self, config: ModelConfig) -> None: ...

    @abstractmethod
    def get_architecture_family(self) -> str: ...

    @abstractmethod
    def get_task_compatibility(self) -> list[str]: ...

    @abstractmethod
    def get_tokenizer_info(self) -> dict[str, Any]: ...

    @abstractmethod
    def get_supported_training_modes(self) -> list[str]: ...

    @abstractmethod
    def get_supported_adapter_methods(self) -> list[str]: ...

    @abstractmethod
    def get_quantization_support(self) -> list[str]: ...

    @abstractmethod
    def get_introspection_support(self) -> dict[str, bool]: ...

    @abstractmethod
    def discover_trainable_modules(self) -> list[str]: ...

    @abstractmethod
    def get_checkpoint_compatibility(self) -> dict[str, Any]: ...

    @abstractmethod
    def inspect_layers(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def attach_adapters(self, adapter_config: AdaptersConfig) -> None: ...

    @abstractmethod
    def run_train_step(self, batch: Any) -> dict[str, float]: ...

    @abstractmethod
    def run_eval_step(self, batch: Any) -> dict[str, float]: ...

    @abstractmethod
    def capture_activations(self, layer_names: list[str], sample_input: Any) -> dict[str, Any]: ...

    @abstractmethod
    def capture_deltas(self, checkpoint_before: str, checkpoint_after: str) -> dict[str, Any]: ...

    @abstractmethod
    def export_checkpoint(self, output_path: str) -> str: ...
```

### 17.3 Initial Model Categories

V1 implements the `CausalLMAdapter` for causal decoder-only language models. The interface is designed to accommodate future adapters for:

- Seq2seq models (e.g., T5, BART)
- Encoder-only task models (e.g., BERT, RoBERTa)
- Multimodal models (future)

### 17.4 Resource Estimation

On model resolution, the system computes and displays:

- Total parameter count
- Estimated VRAM usage at configured precision
- Estimated memory usage during training (with gradient accumulation)
- Estimated disk usage for checkpoints
- Throughput estimate (tokens/second) based on hardware

---

## 18. Fine-Tuning Strategy

### 18.1 V1 Operational Strategy

Primary mode: **Supervised Fine-Tuning (SFT)** with **parameter-efficient tuning (LoRA/QLoRA)**.

Rationale:

- Practical on local hardware
- Resource-aware
- Common workflow
- Easier to observe and compare
- Well-supported by PEFT and trl libraries

### 18.2 Training Pipeline

The training pipeline uses HuggingFace's `trl.SFTTrainer` with custom callback hooks for:

- Real-time metric emission to SQLite and WebSocket
- Stage transition recording
- Checkpoint management with atomic writes
- Activation sampling at configured intervals
- Heartbeat file updates for watchdog monitoring

### 18.3 Future Modes

The architecture accommodates future expansion to:

- Full fine-tuning (all parameters)
- QLoRA (quantized LoRA)
- Instruction tuning variants
- Classification tuning
- Preference optimization (DPO)
- RLHF-style pipelines

---

## 19. Run Lifecycle

### 19.1 Run Stages (All 14)

Every run follows a defined lifecycle with 14 stages. All 14 stages are visible in the UI, though the depth of detail varies by stage.

| Order | Stage Name | Description | Key Outputs |
|---|---|---|---|
| 1 | `config_validation` | Validate YAML config against Pydantic schema | Validation result, warnings |
| 2 | `environment_validation` | Check hardware, GPU, memory, dependencies | Device info, resource snapshot |
| 3 | `model_resolution` | Load or download model, extract metadata | Model profile, architecture tree |
| 4 | `dataset_resolution` | Load dataset, validate schema, map fields | Dataset profile, row counts |
| 5 | `dataset_profiling` | Token length analysis, quality checks, duplicate detection | Token stats, quality warnings |
| 6 | `tokenization_preprocessing` | Tokenize and preprocess dataset | Tokenized dataset, truncation stats |
| 7 | `training_preparation` | Configure trainer, set up callbacks, prepare dataloaders | Trainer object, training plan |
| 8 | `adapter_attachment` | Attach LoRA/PEFT adapters, freeze base model | Trainable param count, adapter info |
| 9 | `training_start` | Begin training loop, emit first metrics | Initial loss value |
| 10 | `training_progress` | Ongoing training with metric emission | Continuous metrics stream |
| 11 | `evaluation` | Run evaluation at configured intervals | Eval loss, eval metrics |
| 12 | `checkpoint_save` | Save model checkpoint (atomic write) | Checkpoint path, size |
| 13 | `artifact_finalization` | Export final artifacts, compute weight deltas | Artifacts manifest |
| 14 | `completion` | Mark run complete or record failure | Final status, summary |

### 19.2 Stage Recording

Each stage records:

| Field | Description |
|---|---|
| stage_name | Identifier from the 14 stages above |
| status | `pending`, `running`, `completed`, `failed`, `skipped` |
| started_at | ISO 8601 timestamp |
| completed_at | ISO 8601 timestamp |
| duration_ms | Wall-clock duration in milliseconds |
| warnings | JSON array of warning strings |
| output_summary | Free-text summary of stage output |
| log_tail | Last N lines of stage-specific logs |

### 19.3 Stage Transitions

Stage transitions are emitted via WebSocket (`run_state` channel, `stage_entered` and `stage_completed` events) and recorded in SQLite. The frontend renders a timeline visualization showing all 14 stages with their current status.

Stages 10-12 (training_progress, evaluation, checkpoint_save) may repeat multiple times during a run. Each repetition is recorded as a separate event but shares the same stage row (updated with latest timestamps).

---

## 20. Run Failure and Recovery

### 20.1 Atomic Checkpoints

Checkpoints are written atomically to prevent corruption:

1. Trainer writes checkpoint to a temporary directory: `checkpoints/.tmp-checkpoint-{step}/`
2. On successful write completion, atomic rename to final path: `checkpoints/checkpoint-{step}/`
3. If the process crashes during write, the `.tmp-` prefixed directory is cleaned up on next startup

This prevents the system from ever referencing a partially-written checkpoint.

### 20.2 Watchdog System

The watchdog monitors trainer process health:

**Heartbeat file:** The trainer writes a heartbeat file every N seconds (configurable, default 10 seconds):

```json
{
  "run_id": "880e8400-e29b-41d4-a716-446655440003",
  "pid": 12345,
  "current_step": 150,
  "total_steps": 1000,
  "timestamp": "2026-03-07T15:05:23.456Z",
  "stage": "training_progress",
  "metrics": {
    "train_loss": 0.423
  }
}
```

Heartbeat file location: `projects/{project_name}/.heartbeat`

**PID monitoring:** The watchdog periodically checks if the trainer process (identified by PID) is still alive using `psutil`.

**Stale timeout:** If the heartbeat file timestamp is older than the configurable stale timeout (default 120 seconds) AND the PID is no longer alive, the watchdog transitions the run to `failed` status.

### 20.3 Crash Recovery

On application startup, the system performs crash recovery:

1. Query SQLite for all runs with status `running`
2. For each running run:
   a. Read the heartbeat file (if it exists)
   b. Check if the PID from the heartbeat is still alive (`psutil.pid_exists()`)
   c. If PID is dead or heartbeat is stale:
      - Transition run status to `failed`
      - Record `failure_reason`: "Process terminated unexpectedly"
      - Record `failure_stage`: stage from heartbeat file
      - Record `last_checkpoint_path`: most recent valid (non-temp) checkpoint
      - Clean up any `.tmp-checkpoint-*` directories
   d. If PID is alive and heartbeat is fresh:
      - Reattach monitoring (reconnect WebSocket streams)
3. Log all recovery actions to the decision log

### 20.4 Resume Flow

A user can resume a failed (or completed) run from the last valid checkpoint:

1. User clicks "Resume" on a failed run in the UI
2. Backend identifies the last valid checkpoint (non-temp, successfully written)
3. Backend creates a **new run** with:
   - New run ID
   - `parent_run_id` set to the original run's ID
   - `config_version_id` set to the original (or a new) config version
   - `resume_from_checkpoint` path in the training config
4. The new run starts from the checkpoint step, not from scratch
5. All metrics from the new run are recorded separately (new run ID)
6. The UI shows the relationship between parent and child runs

Alternatively, the user can choose to start a completely fresh run with the same config.

---

## 21. Observability

### 21.1 Logs

| Capability | Description |
|---|---|
| Live stream | Real-time log streaming via WebSocket |
| Severity filtering | Filter by `debug`, `info`, `warning`, `error`, `critical` |
| Stage filtering | Filter logs by run stage |
| Structured events | JSON-structured event logs for machine parsing |
| Plain text logs | Human-readable log lines for display |
| Persistence | All logs written to files and indexed in SQLite |

### 21.2 Metrics

All metrics are written to SQLite `metric_points` table in real-time and streamed via WebSocket.

| Metric | Type | Description |
|---|---|---|
| `train_loss` | float | Training loss per logging step |
| `eval_loss` | float | Evaluation loss at eval intervals |
| `learning_rate` | float | Current learning rate |
| `grad_norm` | float | Gradient norm (if enabled) |
| `tokens_per_second` | float | Training throughput |
| `step_time_ms` | float | Wall-clock time per step |
| `gpu_memory_used_mb` | float | GPU memory usage |
| `gpu_memory_allocated_mb` | float | GPU memory allocated by PyTorch |
| `cpu_memory_used_mb` | float | System RAM usage |
| `epoch` | float | Current fractional epoch |
| Custom metrics | float | Any additional metrics from callbacks |

### 21.3 Observability Levels

Configurable via `observability.observability_level`:

| Level | What Is Captured |
|---|---|
| `minimal` | Loss, learning rate, basic stage transitions |
| `standard` | All core metrics, grad norm, memory, all stage details |
| `deep` | Standard + activation summaries, weight delta summaries, detailed system resources |
| `expert` | Deep + per-layer gradient stats, per-module parameter change tracking |

### 21.4 Artifacts

Every run produces and tracks artifacts:

| Artifact Type | Description | Storage |
|---|---|---|
| `config_snapshot` | Frozen YAML config for this run | Filesystem + SQLite ref |
| `checkpoint` | Model checkpoint (adapter weights + optimizer state) | Filesystem + SQLite ref |
| `eval_output` | Evaluation results (predictions, metrics) | Filesystem + SQLite ref |
| `metric_export` | Exported metric timeseries (CSV/JSON) | Filesystem + SQLite ref |
| `comparison_summary` | Run comparison report | Filesystem + SQLite ref |
| `ai_recommendation` | AI-generated suggestion with rationale | SQLite |
| `log_file` | Complete log file for the run | Filesystem + SQLite ref |
| `activation_summary` | Statistical summaries of layer activations | SQLite |
| `weight_delta` | Weight change magnitudes per layer | Filesystem + SQLite ref |

### 21.5 Traceability

The system must allow the user to answer:

- What changed? (config diffs between runs)
- When did it change? (versioned timestamps)
- Which run changed it? (run ID linkage)
- What did that change affect? (metric comparison)
- What part of the model was trainable? (adapter attachment info)
- What part of the model visibly changed? (weight delta analysis)

---

## 22. Storage Strategy

### 22.1 Checkpoint Retention Policy

Configured per project via `checkpoint_retention` in the config:

| Setting | Type | Default | Description |
|---|---|---|---|
| `keep_last_n` | int | 3 | Keep the N most recent checkpoints |
| `always_keep_best_eval` | bool | true | Never delete the checkpoint with lowest eval loss |
| `always_keep_final` | bool | true | Never delete the final checkpoint |
| `delete_intermediates_after_completion` | bool | true | Delete non-retained checkpoints after run completes |

Retention enforcement flow:

1. After each checkpoint save during training, evaluate retention policy
2. Mark non-retained checkpoints' `is_retained` flag to 0 in `artifacts` table
3. After run completion, if `delete_intermediates_after_completion` is true, delete non-retained checkpoint files
4. Update `storage_records` table
5. Log cleanup actions to `decision_logs`

### 22.2 Storage Budget with Visibility

The dashboard includes a storage panel showing:

- **Total usage** across all projects
- **Breakdown by type**: checkpoints, logs, activations, exports, configs
- **Per-run cost**: storage consumed by each run
- **Reclaimable space**: bytes that can be freed by running retention cleanup
- **Cleanup actions**: one-click cleanup based on retention policy

The backend computes storage stats on demand (not continuously polled) and caches them in `storage_records`.

### 22.3 Tiered Activation Snapshots

Activation inspection uses a tiered approach to balance observability with storage cost:

**Tier 1 -- Statistical summaries (always captured when enabled):**

- Mean, standard deviation, min, max per layer
- Histogram buckets (configurable, default 50 bins)
- Approximately 1KB per layer per snapshot
- Stored in SQLite `activation_snapshots` table (`summary_json` field)

**Tier 2 -- Full tensors (on explicit user request only):**

- Full activation tensors saved to filesystem as `.pt` files
- Path recorded in `activation_snapshots.full_tensor_path`
- User triggers capture via REST API (`POST /models/activations/{snapshot_id}/full`)
- Used for cross-checkpoint activation comparison

This approach allows activation comparison across checkpoints using Tier 1 summaries by default, with the option to drill into full tensors when needed.

---

## 23. Weights and Architecture Explorer

### 23.1 Purpose

Provide an exploded, inspectable view of the model that allows the user to understand structure and changes at a deeper level than config alone.

### 23.2 Modes of Exploration

#### Architecture Mode

Renders the model's module hierarchy. Presentation options:

- **Tree view**: Collapsible hierarchy of modules, blocks, layers
- **Graph view**: Visual DAG of module connections (future enhancement)
- **Searchable module list**: Flat list with search and filter

Shows for each module: name, type, parameter count, trainable/frozen status, dtype, shape.

#### Parameter Summary Mode

Tabular view showing:

- Parameter count by layer
- Trainable vs frozen breakdown
- dtype per parameter group
- Memory footprint per layer
- Adapter attachment points (which modules have LoRA attached)

#### Activation Inspection Mode

- Select a sample input from the dataset
- Select one or more layers to inspect
- View statistical summaries (Tier 1) or request full tensor capture (Tier 2)
- Compare activations across checkpoints of the same run or across runs
- Visualization: histograms, distribution plots, heatmaps

#### Delta Mode

Post-training analysis:

- Weight delta magnitude by layer (L2 norm of change)
- Trainable parameter changes (adapter weight analysis)
- Before/after statistical summaries
- Heatmap or ranked list of "most changed" modules
- Comparison across checkpoints within a run

#### Expert Edit Mode

Bounded parameter editing with safeguards:

- Only accessible in expert mode (explicit toggle)
- Scope selection: user must select specific parameters/tensors
- Checkpoint backup created automatically before any edit
- Dry-run validation: preview effect before applying
- Audit logging: all edits recorded in `decision_logs`
- Revert path: one-click revert to pre-edit checkpoint
- Not the primary tuning mechanism -- this is for surgical adjustments

---

## 24. AI Recommendation System

### 24.1 Architecture

External API calls only -- no local LLM inference for recommendations.

```
+------------------+      +-------------------+      +-------------------+
| Run Evidence     | ---> | Recommendation    | ---> | Suggestion Output |
| (metrics, config,|      | Engine            |      | (config diff,     |
|  dataset profile)|      |                   |      |  rationale, etc.) |
+------------------+      +------- -----------+      +-------------------+
                               |           |
                     +---------+           +-----------+
                     |                                 |
              +------v------+                  +-------v-------+
              | Rule-Based  |                  | Cloud LLM     |
              | Engine      |                  | (Claude /      |
              | (fallback)  |                  |  OpenAI-compat)|
              +-------------+                  +---------------+
```

### 24.2 Provider Configuration

Users configure their AI provider in Settings:

- **Provider selection**: `anthropic` or `openai_compatible`
- **API key**: stored securely in settings (not in config YAML)
- **Model ID**: e.g., `claude-sonnet-4-20250514` or `gpt-4o`
- **Base URL**: optional, for self-hosted OpenAI-compatible endpoints

### 24.3 Rule-Based Engine (Fallback)

For V1, a rule-based engine provides recommendations when no API key is configured or as a supplement to LLM suggestions:

| Signal | Rule | Recommendation |
|---|---|---|
| Loss plateauing | Loss change < 1% for 5+ eval steps | Reduce learning rate by 50% |
| Loss spiking | Loss increases > 20% step-over-step | Reduce learning rate, increase warmup |
| Grad norm exploding | Grad norm > 10x initial value | Reduce max_grad_norm, reduce learning rate |
| Eval loss diverging | Eval loss increasing while train loss decreasing | Reduce epochs, increase dropout, reduce rank |
| Very low loss | Train loss < 0.1 | Potential overfitting, suggest eval on held-out data |
| High truncation rate | > 20% samples truncated | Increase max_seq_length |
| Memory near limit | GPU memory > 90% allocated | Reduce batch size, enable gradient checkpointing |

### 24.4 Cloud LLM Integration

When configured, the system sends structured prompts to the cloud LLM with:

**Inputs:**

- Current config (YAML)
- Run metrics (loss curve, grad norms, eval results)
- Prior run diffs (if comparison runs exist)
- Dataset profile (token stats, quality warnings)
- Truncation stats
- User notes/preferences (if any)

**Expected output format:**

```json
{
  "config_diff": {
    "training.learning_rate": { "current": 0.0002, "suggested": 0.0001 },
    "adapters.rank": { "current": 8, "suggested": 16 }
  },
  "rationale": "The eval loss plateaued after step 200 while train loss continued to decrease, suggesting the model may benefit from increased adapter capacity and a lower learning rate to improve generalization.",
  "evidence": [
    "Eval loss flatlined at 0.82 from step 200-400",
    "Train loss continued decreasing to 0.35",
    "Gap between train and eval loss: 0.47"
  ],
  "expected_effect": "Lower learning rate should reduce overfitting. Higher rank provides more expressive adapter capacity.",
  "tradeoffs": "Higher rank increases memory usage by approximately 15%. Lower learning rate may require more epochs.",
  "confidence": 0.75,
  "risk_level": "low"
}
```

### 24.5 Recommendation Types

- Lower or raise learning rate
- Change LoRA rank, alpha, or dropout
- Alter eval frequency
- Adjust max sequence length
- Alter batch size or gradient accumulation
- Suggest freezing/unfreezing scope (target modules)
- Suggest data cleanup or filtering
- Suggest quantization or precision changes
- Suggest a different subset of trainable modules
- Suggest warmup ratio adjustments
- Suggest optimizer changes

### 24.6 Approval Flow

1. Recommendation engine generates suggestion (triggered automatically on run completion if `auto_analyze_on_completion` is true, or manually via UI)
2. Suggestion stored in `ai_suggestions` table with status `pending`
3. Frontend displays suggestion in AI Suggestions screen: config diff, rationale, evidence, tradeoffs, confidence, risk level
4. User reviews and either:
   - **Accepts**: system creates new config version with `source_tag: ai_suggestion`, stores `applied_config_version_id` on suggestion, logs decision
   - **Rejects**: suggestion status set to `rejected`, logged in decision history
5. User can then launch a new run from the accepted config

### 24.7 Interface Design for Extensibility

The recommendation engine interface is designed so the cloud LLM slots in cleanly:

```python
from abc import ABC, abstractmethod


class RecommendationEngine(ABC):
    """
    Interface for recommendation engines.
    Implementations: RuleBasedEngine, CloudLLMEngine
    """

    @abstractmethod
    async def generate_recommendations(
        self,
        config: WorkbenchConfig,
        run_metrics: list[dict[str, float]],
        dataset_profile: dict[str, Any],
        comparison_data: dict[str, Any] | None,
    ) -> list[AISuggestionCreate]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

---

## 25. Screen Architecture

### 25.1 Core Navigation

Left sidebar navigation with the following items:

1. **Dashboard**
2. **Projects**
3. **Models**
4. **Datasets**
5. **Training**
6. **Adapters and Optimization**
7. **Weights and Architecture**
8. **Runs**
9. **Compare**
10. **AI Suggestions**
11. **Artifacts**
12. **Settings**

### 25.2 Screen Definitions

#### Dashboard

**Purpose:** Entry point; summary of current project and latest runs.

**Components:**

| Component | Type | Content |
|---|---|---|
| ProjectSelector | Dropdown/combobox | Select active project |
| CurrentModelCard | Card | Model name, family, param count, device |
| CurrentDatasetCard | Card | Dataset name, split sizes, format |
| LatestRunStatusCard | Card | Run ID, status badge, stage progress bar, elapsed time |
| RecentRunsList | Table | Last 10 runs with status, duration, final loss |
| RecentConfigChanges | Timeline | Last 5 config version changes with diffs |
| ResourceSnapshot | Card | GPU/CPU/RAM utilization bars |
| StoragePanel | Card | Total usage, breakdown by type, reclaimable space, cleanup button |
| QuickLaunchActions | Button group | "New Run", "Open Config", "Compare Runs" |

#### Projects

**Purpose:** Create, browse, and manage projects.

**Components:**

| Component | Type | Content |
|---|---|---|
| ProjectList | Table/grid | All projects with name, description, last run date, run count |
| CreateProjectDialog | Dialog | Name, description input; creates project directory and initial config |
| ProjectDetailPanel | Drawer | Full project metadata, storage usage, run history summary |
| ImportExportActions | Button group | Import/export project metadata |
| DeleteProjectAction | Button (destructive) | Delete with confirmation dialog |

#### Models

**Purpose:** Model selection and architecture metadata.

**Components:**

| Component | Type | Content |
|---|---|---|
| ModelSourceSelector | Radio group | HuggingFace Hub or Local Path |
| ModelIdInput | Text input + search | HF model ID or local path browser |
| ResolveButton | Button | Trigger model resolution and profiling |
| ModelProfileCard | Card | Architecture name, family, param count, vocab size, hidden size |
| TokenizerInfo | Card | Tokenizer type, vocab size, special tokens |
| CapabilityBadges | Badge group | Supported tasks, adapter methods, quant modes |
| ResourceEstimate | Card | Estimated VRAM, memory, disk for training |
| LayerSummaryTable | Table | Top-level modules with param counts and types |

#### Datasets

**Purpose:** Dataset selection and structure inspection.

**Components:**

| Component | Type | Content |
|---|---|---|
| DatasetSourceSelector | Radio group | HuggingFace, Local JSONL, Local CSV, Custom |
| DatasetIdInput | Text input | Dataset ID or file path |
| FormatSelector | Select | default, sharegpt, openai, alpaca, custom |
| FieldMappingEditor | Form | Map source fields to expected fields |
| FilterExpressionInput | Text input | Optional filter expression |
| ResolveButton | Button | Trigger dataset resolution and profiling |
| SplitInfoCards | Card group | Train/eval split sizes |
| SamplePreview | Table | Sample rows with field values |
| TokenStatsChart | Chart (histogram) | Token length distribution with truncation line |
| QualityWarnings | Alert list | Duplicates, malformed examples, missing fields |
| PreprocessingPreview | Panel | Show transformed samples after tokenization |

#### Training

**Purpose:** Training workflow settings.

**Components:**

| Component | Type | Content |
|---|---|---|
| TaskTypeSelector | Select | SFT (expandable for future modes) |
| EpochsInput | Number input | Number of epochs |
| BatchSizeInput | Number input | Per-device batch size |
| AccumulationInput | Number input | Gradient accumulation steps |
| LearningRateInput | Number input (scientific) | Learning rate |
| WeightDecayInput | Number input | Weight decay |
| MaxGradNormInput | Number input | Max gradient norm for clipping |
| EvalStepsInput | Number input | Evaluation interval in steps |
| SaveStepsInput | Number input | Checkpoint save interval |
| LoggingStepsInput | Number input | Logging interval |
| SeedInput | Number input | Random seed |
| EffectiveBatchSizeDisplay | Read-only | Computed: batch_size * accumulation_steps |
| EstimatedStepsDisplay | Read-only | Computed: (dataset_size / effective_batch) * epochs |

#### Adapters and Optimization

**Purpose:** PEFT and optimizer-specific controls.

**Components:**

| Component | Type | Content |
|---|---|---|
| AdapterToggle | Switch | Enable/disable adapters |
| AdapterTypeSelector | Select | LoRA, QLoRA |
| RankInput | Number input | LoRA rank |
| AlphaInput | Number input | LoRA alpha |
| DropoutInput | Number input | LoRA dropout |
| TargetModulesSelector | Multi-select + custom input | Modules to attach adapters to |
| BiasSelector | Select | none, all, lora_only |
| OptimizerSelector | Select | AdamW, Adam, SGD, Adafactor, Paged AdamW 8-bit |
| SchedulerSelector | Select | Cosine, Linear, Constant, Constant with warmup |
| WarmupRatioInput | Number input | Warmup ratio |
| GradientCheckpointingToggle | Switch | Enable gradient checkpointing |
| MixedPrecisionSelector | Select | no, fp16, bf16 |
| QuantizationToggle | Switch | Enable quantization |
| QuantModeSelector | Select | 4-bit, 8-bit |
| QuantTypeSelector | Select | nf4, fp4 |
| TrainableParamsPreview | Card | Preview of trainable vs total params after adapter config |

#### Weights and Architecture

**Purpose:** Inspect model structure and optionally manipulate bounded parameters.

**Components:**

| Component | Type | Content |
|---|---|---|
| ViewModeSelector | Tab group | Architecture, Parameters, Activations, Deltas, Expert Edit |
| ArchitectureTree | Tree view | Collapsible module hierarchy with search |
| ModuleSearchInput | Command palette | Search modules by name |
| LayerDetailDrawer | Drawer (right) | Selected layer detail: name, type, params, dtype, shape, trainable status |
| ParameterSummaryTable | Table | All layers with param count, trainable flag, memory, adapter status |
| TrainableFrozenToggle | Filter | Show only trainable, only frozen, or all |
| ActivationSampleSelector | Select | Choose sample input for activation probing |
| ActivationLayerSelector | Multi-select | Choose layers to inspect |
| ActivationSummaryView | Chart group | Histograms, distribution stats for selected layers |
| ActivationCheckpointCompare | Side-by-side panel | Compare activations across checkpoints |
| RequestFullTensorButton | Button | Trigger Tier 2 full tensor capture |
| DeltaMagnitudeChart | Bar chart | Weight delta magnitude by layer (ranked) |
| DeltaHeatmap | Heatmap | Module-level change visualization |
| BeforeAfterSummary | Table | Statistical comparison pre/post training |
| ExpertModeToggle | Switch (gated) | Enable expert parameter editing |
| TensorEditor | Specialized editor | View and edit bounded tensor values |
| CheckpointBackupNotice | Alert | Confirmation that backup was created |
| RevertButton | Button | Revert to pre-edit checkpoint |

#### Runs

**Purpose:** Run lifecycle and execution monitoring.

**Components:**

| Component | Type | Content |
|---|---|---|
| RunList | Table | All runs with ID, status, duration, final loss, config version |
| ActiveRunBanner | Banner | Current running run with stage and progress |
| RunTimeline | Timeline visualization | All 14 stages with status indicators and durations |
| StageDetailPanel | Drawer | Selected stage: logs, warnings, output summary, timestamps |
| LiveMetricsCharts | Chart group (recharts) | Loss curve, learning rate, grad norm, throughput, memory |
| LogStream | Virtual scrolling log viewer | Real-time log stream with severity badges and stage filters |
| SystemResourceMonitor | Card group | GPU utilization, memory, CPU in real-time |
| CheckpointList | Table | Checkpoints with step, path, size, retained status |
| FailurePanel | Alert + detail | Failure reason, stage, last known metrics, recovery options |
| RunActions | Button group | Cancel, Pause, Resume |
| ResumeFromCheckpointDialog | Dialog | Select checkpoint to resume from, creates new run |

#### Compare

**Purpose:** Compare runs and explain differences.

**Components:**

| Component | Type | Content |
|---|---|---|
| RunSelector | Multi-select combobox | Select 2+ runs to compare |
| ConfigDiffViewer | Side-by-side diff | Config differences highlighted (Monaco diff editor) |
| MetricOverlayChart | Multi-line chart | Overlay loss curves, learning rates from multiple runs |
| MetricComparisonTable | Table | Side-by-side final metrics for each run |
| ArtifactComparisonPanel | Table | Artifact counts and sizes per run |
| OutputComparisonPanel | Panel | Side-by-side eval outputs (if available) |
| ActivationComparisonPanel | Panel | Cross-run activation summaries (Tier 1) for selected layers |
| AISummaryCard | Card | AI-generated summary of likely causes for performance differences |

#### AI Suggestions

**Purpose:** Recommendation inbox for config refinement.

**Components:**

| Component | Type | Content |
|---|---|---|
| SuggestionList | List with status badges | All suggestions with status (pending, accepted, rejected) |
| SuggestionDetail | Panel | Selected suggestion full view |
| ConfigDiffView | Diff viewer | Proposed config changes |
| EvidenceList | List | References to metrics, runs, data points |
| RationaleText | Text block | Explanation of why this change is suggested |
| ExpectedEffectText | Text block | What the suggestion aims to achieve |
| TradeoffsText | Text block | Potential downsides |
| ConfidenceBadge | Badge | Confidence score (0.0-1.0) |
| RiskBadge | Badge | Risk level: low, medium, high |
| ProviderBadge | Badge | Source: rule_engine, anthropic, openai_compatible |
| AcceptButton | Button (primary) | Accept suggestion, create new config version |
| RejectButton | Button (secondary) | Reject suggestion, log decision |
| GenerateButton | Button | Manually trigger suggestion generation for selected run |

#### Artifacts

**Purpose:** Inspect saved outputs and assets.

**Components:**

| Component | Type | Content |
|---|---|---|
| ArtifactTable | Table with filters | All artifacts: type, run, path, size, date |
| TypeFilter | Select/tabs | Filter by artifact type |
| RunFilter | Select | Filter by run |
| ArtifactDetailDrawer | Drawer | Selected artifact metadata, preview (if applicable) |
| DownloadButton | Button | Download artifact file |
| DeleteButton | Button (destructive) | Delete with confirmation |
| BulkCleanupButton | Button | Run retention policy cleanup |
| StorageSummary | Card | Total storage, breakdown pie chart |

#### Settings

**Purpose:** Local app preferences and integration options.

**Components:**

| Component | Type | Content |
|---|---|---|
| AIProviderSelector | Select | Anthropic, OpenAI-compatible |
| APIKeyInput | Password input | API key (masked) |
| AIModelIdInput | Text input | Model ID for AI provider |
| AIBaseUrlInput | Text input | Optional base URL for OpenAI-compatible |
| TestConnectionButton | Button | Test AI provider connectivity |
| DefaultProjectsDirInput | Path input | Default directory for new projects |
| StorageWarningThreshold | Number input | GB threshold for storage warnings |
| WatchdogStaleTimeout | Number input | Seconds before heartbeat is considered stale |
| WatchdogHeartbeatInterval | Number input | Seconds between heartbeat writes |
| DefaultRetentionPolicy | Form group | Default checkpoint retention settings for new projects |
| ExperimentRetentionDays | Number input | Days to retain completed experiment data |

### 25.3 Layout Structure

```
+--------+--------------------------------------------+----------+
|        |                                            |          |
|  Left  |            Central Workspace               |  Right   |
| Sidebar|                                            | Drawer   |
|  (nav) |                                            | (context,|
|        |                                            |  AI,     |
|        |                                            | metadata)|
|        |                                            |          |
|        +--------------------------------------------+          |
|        |         Bottom Panel (logs, terminal)      |          |
+--------+--------------------------------------------+----------+
```

- **Left sidebar**: Always visible, collapsible to icons. Contains navigation items.
- **Central workspace**: Main content area for the active screen.
- **Right drawer**: Contextual panel for detail views, AI suggestions, layer metadata. Toggleable.
- **Bottom panel**: Resizable panel for log streaming and terminal output. Collapsible.

---

## 26. UI Design Direction

### 26.1 Design Goals

- Simple, clean, professional
- Dense enough for expert use without feeling cramped
- Low visual noise
- Clear hierarchy through typography and spacing
- Minimal but meaningful motion

### 26.2 Component Library

All UI components built with shadcn/ui (Radix UI primitives + Tailwind CSS):

- Cards, Tabs, Drawers, Dialogs
- Tables (with sorting, filtering, pagination)
- Tree views (collapsible, searchable)
- Command palette (cmdk)
- Forms (with validation)
- Badges and status indicators
- Resizable panels (react-resizable-panels)
- Toast notifications
- Tooltips

### 26.3 Chart Library

recharts for all data visualizations:

- Line charts (loss curves, learning rate schedules)
- Bar charts (parameter counts, storage breakdown, delta magnitudes)
- Area charts (memory usage over time)
- Histograms (token length distributions, activation distributions)
- Composed charts (multi-metric overlays)

### 26.4 Motion and Animation

Keep animations subtle and purposeful:

- Panel transitions (slide in/out, 150ms ease)
- Loading states (skeleton screens, not spinners)
- Metric refresh (fade transitions on value updates)
- Diff highlights (background color flash on change)
- Stage progression (progress bar animation)
- Toast notifications (slide in from top-right)

### 26.5 Color and Status System

Status indicators use a consistent color language:

| Status | Color | Usage |
|---|---|---|
| Pending | Gray | Not yet started |
| Running | Blue | Currently active |
| Completed | Green | Successfully finished |
| Failed | Red | Error occurred |
| Cancelled | Orange | User-cancelled |
| Paused | Yellow | Temporarily stopped |
| Skipped | Light gray | Stage not applicable |

---

## 27. Quantization and Local Resource Strategy

### 27.1 Resource Visibility

The system estimates and displays:

- Expected VRAM usage at configured precision
- Memory risk assessment (safe, tight, exceeded)
- Active precision mode (fp32, fp16, bf16)
- Quantization mode (none, 4-bit, 8-bit)
- Throughput expectation (estimated tokens/second)
- Checkpoint storage cost per save

### 27.2 Quantization Support

| Mode | Library | Description |
|---|---|---|
| 4-bit (NF4) | bitsandbytes | QLoRA-compatible 4-bit quantization |
| 4-bit (FP4) | bitsandbytes | Alternative 4-bit format |
| 8-bit | bitsandbytes | 8-bit quantization |
| Double quantization | bitsandbytes | Quantize the quantization constants |

Warnings are surfaced for unsupported combinations (e.g., quantization on MPS, incompatible model architectures).

### 27.3 Local Constraints

The UI accounts for local hardware limitations:

- **Sampled views**: Not every layer can be fully inspected; activation capture uses sampling
- **Aggregated views**: Large weight maps are summarized (mean, std, histograms) rather than displayed raw
- **Drill-down on demand**: Full detail only when explicitly requested by the user
- **Memory-aware operations**: Activation capture and weight delta computation check available memory before proceeding

---

## 28. Multi-Model Support Strategy

### 28.1 Architectural Rule

The UI does not directly assume one fixed model type. It depends on the model capability contract (Section 17.2). All model-specific behavior is mediated through the `ModelAdapter` interface.

### 28.2 Initial Model Categories

V1 implements one category operationally while preparing the interface for others:

| Category | V1 Status | Examples |
|---|---|---|
| Causal decoder-only LMs | Fully implemented | Llama, Mistral, Phi, GPT-2 |
| Seq2seq models | Interface prepared | T5, BART, mBART |
| Encoder-only task models | Interface prepared | BERT, RoBERTa, DeBERTa |
| Multimodal models | Future | LLaVA, Qwen-VL |

### 28.3 Model Adapter Layer

New model families are added by implementing the `ModelAdapter` interface (Section 17.2). This requires:

- Implementing all abstract methods
- Registering the adapter with a factory that maps `family` strings to adapter classes
- Adding any family-specific config fields to the Pydantic schema

---

## 29. Non-Functional Requirements

### 29.1 Local Performance

- The frontend must remain responsive (< 100ms interaction latency) while a training run is active
- WebSocket streams must not block the UI event loop
- Metric chart rendering must handle 10,000+ data points without frame drops (virtual scrolling, data decimation)
- Log viewer must handle 100,000+ lines via virtual scrolling

### 29.2 Reproducibility

Each run must be reconstructable from:

- Config snapshot (full YAML blob stored in `config_versions`)
- Model reference (source + ID + revision)
- Dataset fingerprint (hash of dataset at load time)
- Run events (all stage transitions with timestamps)
- Artifacts (checkpoints, eval outputs)
- Random seed

### 29.3 Modularity

The following must be separable modules with clean interfaces:

- Model handling (`adapters/`)
- Training orchestration (`services/orchestrator.py`, `services/trainer.py`)
- Observability (`services/` + WebSocket handlers)
- AI recommendations (`services/ai_recommender.py`, `services/rule_engine.py`)
- Storage management (`services/storage_manager.py`)

### 29.4 Extensibility

New model families and new training methods plug into defined interfaces (`ModelAdapter`, `RecommendationEngine`), not require rewrites of core code.

### 29.5 Reliability

Run failures are captured with:

- Stage where failure occurred
- Stack trace / error message
- Last known metrics
- Partial artifacts (if available)
- Recovery options (resume from checkpoint or start fresh)

### 29.6 Safety

- Raw parameter editing is gated behind expert mode toggle
- All weight edits create automatic checkpoint backups
- All destructive actions (delete project, delete artifacts, apply weight edits) require explicit confirmation
- AI suggestions require explicit user approval before applying

### 29.7 Data Integrity

- All checkpoint writes are atomic (temp dir + rename)
- SQLite writes use WAL mode for concurrent read/write safety
- Config versions are append-only (no updates, no deletes)

---

## 30. Risks and Mitigations

### 30.1 Raw Weight Editing Risk

**Risk:** Feature becomes computationally heavy, hard to reason about, visually overwhelming, or unsafe without rollback.

**Mitigation:** Expert-only gating, bounded scope selection, mandatory checkpoint backup before edit, audit logging, dry-run validation, one-click revert.

### 30.2 Multi-Model Complexity

**Risk:** True full generality across all model families is expensive to implement and test.

**Mitigation:** Capability contract interface, one family well-supported first (causal LMs), growth through adapter implementations.

### 30.3 Local Hardware Limits

**Risk:** VRAM limits, memory pressure, activation capture cost, storage growth, slow runs.

**Mitigation:** Resource estimation before run, tiered activation storage, checkpoint retention policies, storage budget visibility, observability level controls, memory-aware operations.

### 30.4 Observability Overhead

**Risk:** Deep tracing and activation inspection degrade training performance.

**Mitigation:** Four configurable observability levels (minimal, standard, deep, expert). Default to "standard" which balances visibility with performance.

### 30.5 AI Suggestion Quality

**Risk:** AI suggestions become opaque or misleading.

**Mitigation:** All suggestions include evidence, rationale, expected effect, tradeoffs, confidence score, and risk level. Rule-based engine provides grounded fallback. No auto-apply -- user must explicitly accept.

### 30.6 Storage Growth

**Risk:** Checkpoints, logs, and activation data accumulate rapidly.

**Mitigation:** Configurable retention policies, storage dashboard with visibility, one-click cleanup, tiered activation storage (summaries only ~1KB/layer vs full tensors on demand).

### 30.7 Process Crashes

**Risk:** Training process dies, leaving run in inconsistent state.

**Mitigation:** Heartbeat monitoring via watchdog, crash recovery on startup, atomic checkpoints preventing corruption, resume flow creating new linked runs.

---

## 31. Phased Implementation Plan

### Phase 1: Foundation (Spec, Schema, Skeleton)

**Deliverables:**

- Finalized product spec (this document)
- SQLite schema with all tables (Alembic migrations)
- Pydantic config models with validation
- YAML config schema documentation
- FastAPI app skeleton with health endpoints
- React app skeleton with routing and layout shell
- Docker Compose configuration
- Monorepo structure with frontend/, backend/, shared/

**Key files:**

- `backend/app/main.py` -- FastAPI entry point
- `backend/app/core/database.py` -- SQLite setup with SQLAlchemy
- `backend/app/models/*.py` -- All ORM models
- `backend/app/schemas/*.py` -- Pydantic schemas
- `frontend/src/App.tsx` -- App shell with router
- `frontend/src/components/layout/` -- Sidebar, panels
- `docker-compose.yml`

### Phase 2: Core Application

**Deliverables:**

- Project CRUD (REST + UI)
- Config persistence (YAML read/write + SQLite versioning)
- Config validation via Pydantic
- Config diff computation and display
- Navigation and client-side state management (zustand)
- Settings screen (AI provider config, paths)
- Projects screen (create, browse, delete)
- Dashboard screen (project summary, resource snapshot)

**Key endpoints:** `/projects`, `/projects/{id}/configs`, `/settings`

### Phase 3: Model and Dataset Integration

**Deliverables:**

- Model resolution from HuggingFace Hub and local paths
- Model profiling (architecture extraction, param counts, resource estimates)
- ModelAdapter interface + CausalLMAdapter implementation
- Dataset resolution (HuggingFace, JSONL, CSV, custom formats)
- Dataset profiling (token stats, quality checks)
- Multi-turn format support (ShareGPT, OpenAI)
- Models screen (selection, profiling, architecture preview)
- Datasets screen (selection, profiling, sample preview)

**Key endpoints:** `/models/resolve`, `/models/profile`, `/models/architecture`, `/datasets/resolve`, `/datasets/profile`, `/datasets/samples`

### Phase 4: Training Orchestration

**Deliverables:**

- Run launcher (subprocess management)
- SFTTrainer integration with custom callbacks
- 14-stage run lifecycle implementation
- Stage transition recording
- Heartbeat file writing
- Watchdog process monitoring
- Atomic checkpoint writing
- Crash recovery on startup
- Resume from checkpoint flow
- Run CRUD endpoints
- Training screen (config form)
- Adapters and Optimization screen (config form)

**Key endpoints:** `/runs`, `/runs/{id}`, `/runs/{id}/cancel`, `/runs/{id}/pause`, `/runs/{id}/resume`

### Phase 5: Real-Time Observability

**Deliverables:**

- WebSocket server implementation
- Metric streaming (trainer callback -> SQLite -> WebSocket)
- Log streaming (structured + plain text)
- System resource monitoring (psutil)
- Stage transition events
- Runs screen (timeline, live metrics charts, log viewer, system resources)
- Bottom log panel (global log stream)
- Observability level controls

**Key WebSocket channels:** `run_state`, `metrics`, `logs`, `system`

### Phase 6: Comparison and Artifacts

**Deliverables:**

- Run comparison engine (config diff, metric overlay, artifact comparison)
- Artifact tracking (checkpoint, config snapshot, eval output, metric export)
- Checkpoint retention policy enforcement
- Storage tracking and cleanup
- Compare screen (diff viewer, metric overlay charts, artifact comparison)
- Artifacts screen (browser, filters, download, cleanup)
- Storage panel in Dashboard

**Key endpoints:** `/runs/compare`, `/artifacts`, `/storage`

### Phase 7: Model Explorer

**Deliverables:**

- Architecture tree view (collapsible, searchable)
- Layer metadata inspector
- Trainable/frozen parameter view
- Activation capture (Tier 1: statistical summaries)
- Activation capture (Tier 2: full tensors on demand)
- Cross-checkpoint activation comparison
- Weight delta computation and visualization
- Delta heatmap and ranked module list
- Weights and Architecture screen (all five modes)

**Key endpoints:** `/models/architecture`, `/models/layers/{name}`, `/models/activations`

### Phase 8: AI Recommendations

**Deliverables:**

- RecommendationEngine interface
- Rule-based engine implementation
- Cloud LLM integration (Anthropic SDK + OpenAI client)
- Suggestion generation pipeline
- Config diff rendering
- Approval workflow (accept/reject)
- Decision logging
- AI Suggestions screen (inbox, detail, approve/reject)
- AI summary in Compare screen
- Auto-analyze on run completion (optional)

**Key endpoints:** `/suggestions`, `/suggestions/generate`, `/suggestions/{id}/accept`, `/suggestions/{id}/reject`

### Phase 9: Expert Controls

**Deliverables:**

- Expert mode toggle with gating
- Bounded weight editing UI
- Automatic checkpoint backup before edit
- Dry-run validation
- Audit logging for all weight edits
- Revert to pre-edit checkpoint
- Expert Edit mode in Weights and Architecture screen

### Phase 10: Polish and Hardening

**Deliverables:**

- Error handling and user-facing error messages across all screens
- Loading states and skeleton screens
- Keyboard shortcuts and command palette
- Toast notifications for async operations
- Performance optimization (virtual scrolling, data decimation, memoization)
- Edge case handling (empty states, large datasets, network errors)
- Testing (backend: pytest, frontend: vitest + testing-library)

---

## 32. Resolved Design Decisions

These questions were previously open and have been resolved:

| Question | Decision |
|---|---|
| Desktop-wrapped or browser + local service? | Browser-based (React) + local Python backend (FastAPI) |
| Frontend framework? | React + shadcn/ui + Tailwind CSS |
| Backend framework? | Python FastAPI |
| Communication protocol? | WebSocket for streaming, REST for CRUD and health |
| Data store? | SQLite for all structured data |
| Config format? | YAML files validated via Pydantic |
| Config versioning? | SQLite-backed, append-only config_versions table |
| Deployment? | Docker Compose primary, native also supported |
| AI recommendation source? | External API only (Claude + OpenAI-compatible), rule-based fallback |
| GPU on macOS Docker? | MPS only accessible natively; Docker falls back to CPU |
| Dataset formats? | HuggingFace, JSONL, CSV, custom, ShareGPT, OpenAI format |
| Model sources? | HuggingFace Hub, local file paths |
| How should failed runs preserve partial state? | Atomic checkpoints, heartbeat watchdog, crash recovery on startup |
| How deep should activation capture go? | Tiered: statistical summaries always (~1KB/layer), full tensors on explicit request |
| MVP or full build? | Full product build, all features in scope |
| Repo structure? | Monorepo: frontend/, backend/, shared/ |

---

## 33. Open Design Questions

These do not block implementation but should be tracked:

- Which specific causal LM should be used as the reference model during development and testing? (e.g., a small model like GPT-2 for fast iteration)
- What is the exact boundary for "bounded" expert weight editing? (number of tensors, parameter count limit, specific module types)
- Should the architecture graph view (visual DAG) be implemented in the initial build or deferred as an enhancement to the tree view?
- How should large architecture graphs (100+ layer models) degrade gracefully in the tree view? (lazy loading, virtual scrolling, collapse-by-default thresholds)
- What is the maximum number of runs that can be compared simultaneously in the Compare screen?
- Should the command palette (cmdk) support launching runs and applying AI suggestions, or only navigation?
- What is the retention policy for decision logs and AI suggestions? (indefinite, configurable, tied to project lifecycle)

---

## Final Product Statement

This product is a local-first, single-user, config-driven fine-tuning workbench designed for expert visibility and future extensibility.

It combines:

- Execution (14-stage run lifecycle with failure recovery)
- Observability (real-time metrics, logs, and stage tracking)
- Introspection (architecture exploration with tiered activation inspection)
- Comparison (config diffs, metric overlays, artifact comparison)
- Explainable AI recommendations (cloud LLM + rule-based, with approval flow)
- Storage management (retention policies, budget visibility, tiered activation storage)

Its purpose is not merely to launch training runs, but to give the operator a complete, inspectable system for understanding and refining local model fine-tuning workflows.
