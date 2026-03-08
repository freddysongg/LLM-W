# Claude Code Guidelines

This document defines **non-negotiable rules** for AI-generated code in the LLM Fine-Tuning Workbench. Violations mean the output is not acceptable.

---

## Project Overview

Monorepo with two services:

- `frontend/` -- React + TypeScript + shadcn/ui (browser-based)
- `backend/` -- Python FastAPI + SQLite + PyTorch/HuggingFace

Communication: REST (config CRUD, health) + WebSocket (streaming logs, metrics, run state).

Canonical spec: `spec.md` in the project root.

---

## Code Style Rules (TypeScript -- frontend/)

* All code must pass `prettier` formatting
* Never create temporary variables that are not used
* Never create redundant variables -- return or use values directly
* Never create unused constants
* Remove variables immediately when unused
* Do not create inline type definitions -- define interfaces/types separately
* **Always use object destructuring** when accessing object properties:

  ```ts
  // CORRECT
  const { modelId, family } = modelProfile;

  // WRONG
  const modelId = modelProfile.modelId;
  const family = modelProfile.family;
  ```
* Destructure function parameters when accessing multiple properties
* Destructure in assignments, not just declarations
* When imports can be shortened, always shorten them
* Combine multiple imports from the same source
* Use `import type` for type-only imports
* Always use ES2020+ JavaScript style
* Prefer arrow functions
* Do not rely on the `this` keyword
* Functions must have well-defined, descriptive names
* **Use Parameter Object Pattern** for functions with more than one argument:

  ```ts
  // CORRECT
  function createRun({ projectId, configVersionId }: CreateRunParams): Run {}

  // WRONG
  function createRun(projectId: string, configVersionId: string): Run {}
  ```
* Positional parameters allowed only for trivial cases (e.g., `clamp(value, min, max)`)
* Use default values in destructured parameters: `({ limit = 10, offset = 0 }: QueryParams = {})`

---

## Code Style Rules (Python -- backend/)

* All code must pass `ruff` formatting and linting
* Never create unused variables, imports, or constants
* Remove dead code immediately
* **Always use keyword arguments** for functions with more than two parameters:

  ```python
  # CORRECT
  def create_run(*, project_id: str, config_version_id: str) -> Run: ...

  # WRONG
  def create_run(project_id: str, config_version_id: str) -> Run: ...
  ```
* Use dataclasses or Pydantic models for structured data, never raw dicts for domain objects
* Prefer f-strings over `.format()` or `%` formatting
* Use `pathlib.Path` over `os.path` for all filesystem operations
* Type hints required on all function signatures (parameters and return types)
* Use `from __future__ import annotations` for modern type syntax
* Never use mutable default arguments (`def foo(items=[])`), use `None` sentinel pattern
* Prefer list/dict/set comprehensions over manual loops for transformations
* Use context managers (`with`) for all resource management (files, DB sessions, locks)

---

## TypeScript Rules

* Never use `any`
* All variables, parameters, and return values must be explicitly typed
* Use `unknown` instead of `any`, then narrow with type guards
* Never add `eslint-disable` comments -- fix the issue instead
* All functions must have explicit return types
* Use proper interfaces or types for complex objects
* Ensure types match actual runtime data
* When working with JSON or external data, define explicit interfaces
* Never assume values are present -- explicit null/undefined checks required
* Avoid non-null assertions (`!`) unless accompanied by a comment explaining why it is safe
* Prefer discriminated unions over flags or enums
* No status objects without a discriminant field
* All `switch` statements must be exhaustive
* Use `never` checks to enforce exhaustiveness
* No magic strings -- use string literal unions, constants, or `const enum`
* Always do a type check after modifications

---

## Python Typing Rules

* Never use `Any` -- use `object` or `Unknown` patterns with type narrowing
* All function parameters and return types must have type annotations
* Use `TypedDict` for dictionary shapes that cross API boundaries
* Use `Literal` types instead of magic strings
* Use `Protocol` for structural typing where interfaces are needed
* Pydantic models define all API request/response shapes -- never return raw dicts from routes
* SQLAlchemy models must have typed column definitions

---

## Architecture Rules

### Frontend (frontend/)

```
pages/        -> hooks/ -> api/ -> (backend REST/WS)
              -> stores/
components/   -> (pure rendering, no direct API calls)
hooks/        -> api/, ws/, stores/
api/          -> (REST client functions only)
ws/           -> (WebSocket client only)
stores/       -> (Zustand stores, no side effects)
types/        -> (shared TypeScript types)
lib/          -> (pure utility functions)
```

* Page components orchestrate layout and data fetching via hooks
* Components must be pure renderers -- no direct API calls, no business logic
* Custom hooks encapsulate all data fetching and state management
* API client functions (`api/`) are thin wrappers around fetch/TanStack Query
* Stores hold only client-side UI state (selected items, panel visibility), not server state
* Server state is managed exclusively through TanStack Query

### Backend (backend/)

```
api/routes/   -> services/ -> adapters/, models/, workers/
api/websocket/ -> services/
services/     -> adapters/, models/, core/
adapters/     -> (model-specific implementations)
models/       -> (SQLAlchemy ORM only, no logic)
schemas/      -> (Pydantic request/response shapes)
core/         -> (database, config, events)
workers/      -> (background tasks)
```

* Routes must not contain business logic -- delegate to services
* Services must not import route modules or Pydantic request schemas
* Pydantic schemas must not contain behavior (no methods beyond validators)
* ORM models must not contain business logic
* Higher layers depend on lower layers only -- no circular imports
* Adapters implement the `ModelAdapter` interface for each model family

---

## Side Effects and I/O Rules

### TypeScript

* Side-effecting functions must be in `api/`, `ws/`, or custom hooks -- never in `lib/` or `components/`
* Pure utility functions in `lib/` must not import fetch, WebSocket, or browser APIs
* Every subscription (WebSocket, event listener, timer) must have a cleanup function in `useEffect` return

### Python

* Side-effecting functions must be clearly named (`fetch_*`, `write_*`, `send_*`, `stream_*`)
* Side-effecting code lives in `services/`, `adapters/`, `workers/`, or `api/`
* Pure functions must not import FastAPI, SQLAlchemy, httpx, or environment variables
* Every opened resource must use a context manager or explicit cleanup

---

## Error Handling Rules

### TypeScript

* Never throw generic errors (`new Error("something went wrong")`)
* API errors must include: HTTP status, error code, and actionable message
* `catch` blocks must rethrow, return a typed error, or document why the error is safe to ignore
* Never swallow errors silently
* Never return `null` to indicate failure -- use discriminated unions or Result patterns

### Python

* Never raise bare `Exception` -- use typed exceptions with context
* All route handlers must catch service exceptions and map them to proper HTTP responses
* Never use bare `except:` -- always catch specific exception types
* Failed training operations must capture: stage, error message, stack trace, last known metrics
* Database operations must use transactions with proper rollback on failure
* Never return `None` to indicate failure -- raise or return a Result type

---

## Naming Rules

* No vague names: `data`, `info`, `value`, `item`, `handler`, `result`, `response` (unless literally an HTTP response object)
* Names must encode intent and domain meaning
* Boolean variables must start with: `is`, `has`, `can`, `should`
* Python functions: `snake_case`, classes: `PascalCase`, constants: `UPPER_SNAKE_CASE`
* TypeScript functions: `camelCase`, types/interfaces: `PascalCase`, constants: `UPPER_SNAKE_CASE`
* React components: `PascalCase`
* File names: `kebab-case` (frontend), `snake_case` (backend)

---

## Performance and Safety Rules

* Nested loops must include a comment explaining time complexity
* Using `.find()` / `next()` inside loops is forbidden unless the dataset is provably tiny
* Avoid accidental O(n^2) behavior
* Validate all external input at system boundaries (API routes, WebSocket messages, file uploads)
* Never trust external API responses -- validate shape before use
* Do not use unsafe regex patterns that may cause ReDoS
* Avoid nested quantifiers in regex
* All database queries must use parameterized statements -- never string interpolation
* WebSocket messages must be validated against expected schemas before processing
* File paths from user input must be sanitized -- no path traversal

---

## Project Structure Rules

### Frontend (frontend/src/)

* `components/ui/` -- shadcn/ui components only (generated, do not modify directly)
* `components/layout/` -- app shell, sidebar, panel layouts
* `components/charts/` -- metric visualization components (recharts wrappers)
* `components/config/` -- config editor components
* `components/model/` -- architecture explorer, layer inspector
* `components/runs/` -- run timeline, stage display, log viewer
* `hooks/` -- custom React hooks (data fetching, subscriptions, state)
* `stores/` -- Zustand stores for client-side UI state
* `api/` -- REST client functions (one file per resource)
* `ws/` -- WebSocket client and connection management
* `types/` -- TypeScript type definitions (one file per domain)
* `pages/` -- route-level page components (one per screen)
* `lib/` -- pure utility functions

### Backend (backend/app/)

* `api/routes/` -- FastAPI route modules (one per resource)
* `api/websocket/` -- WebSocket endpoint handlers
* `core/` -- database connection, app config, event bus
* `models/` -- SQLAlchemy ORM model definitions
* `schemas/` -- Pydantic request/response schemas
* `services/` -- business logic (orchestrator, trainer, introspection, AI recommender, watchdog, storage manager)
* `adapters/` -- model adapter implementations (base interface + per-family adapters)
* `workers/` -- background task runners

### Shared (shared/)

* `config_schema/` -- canonical YAML config schema documentation
* `types/` -- shared type definitions used as reference across frontend and backend

### Adding a New Feature

1. Define Pydantic schemas in `backend/app/schemas/`
2. Create or update service in `backend/app/services/`
3. Add route in `backend/app/api/routes/`
4. Define TypeScript types in `frontend/src/types/`
5. Create API client function in `frontend/src/api/`
6. Create custom hook in `frontend/src/hooks/`
7. Build components in `frontend/src/components/`
8. Wire into page in `frontend/src/pages/`

---

## Config and Schema Rules

* All config is YAML -- validated against Pydantic models in the backend
* Config changes in the UI must write back to YAML and create a new version in SQLite
* Config versions are immutable once created -- no in-place mutation
* Pydantic models are the single source of truth for config validation
* Config diffs are computed and stored alongside each version
* YAML files must be human-readable -- no generated comments or metadata injected into user-facing files

---

## Database Rules

* SQLite is the only database -- no Postgres, no Redis
* All schema changes go through Alembic migrations -- never modify tables manually
* Database sessions must use async context managers
* Checkpoint writes must be atomic (write to temp dir, then rename)
* Never store large binary data in SQLite -- store filesystem paths instead
* Metric points should be batch-inserted for performance during training

---

## Testing Rules

* Frontend tests live in `frontend/src/__tests__/` or colocated as `*.test.ts(x)` -- follow whichever pattern is established first
* Backend tests live in `backend/tests/`
* Never mock what you can construct -- prefer real objects with test data
* API tests must test against actual route handlers, not service internals
* Training-related tests may use small synthetic models and datasets

---

## Docker Rules

* `docker-compose.yml` lives at the project root
* `Dockerfile.frontend` and `Dockerfile.backend` live at the project root
* Containers must not require GPU -- GPU access is native-only (MPS on macOS, CUDA on Linux)
* Volume mounts must be used for persistent data (`data/`, `projects/`)
* Environment variables must have sensible defaults -- the app must start without a `.env` file
* Health checks must be defined for both services

---

## WebSocket Rules

* All WebSocket messages must follow a typed envelope format: `{ type: string, payload: object }`
* The backend must handle client disconnections gracefully -- no crashes on broken pipes
* WebSocket connections must include reconnection logic on the frontend
* Log and metric streams must support backpressure -- do not flood the client

---

## Git Rules

* Never push to git -- only stage and commit, user pushes manually
* Never mention AI, Claude, or automation in commit messages
* Never commit, stage, or `git add` any CLAUDE.md file
* Never commit `.env` files, API keys, or credentials
* Prefer specific `git add <file>` over `git add .` or `git add -A`

---

## Documentation and Comments

* Do not comment on what the code does
* Comments may only explain: why something exists, why it is safe, why a trade-off was chosen
* Function length limits:
  * Pure functions (both languages): max 30 lines
  * Service functions: max 50 lines
  * Route handlers: max 20 lines (delegate to services)
* If a function name contains "And", it likely violates single-responsibility

---

## TODO Discipline

* All TODOs must include a reason and a condition for removal
* Anonymous TODOs are forbidden
* Format: `TODO(context): reason -- remove when [condition]`

---

## AI-Specific Guardrails

* Never invent APIs, schemas, fields, or behavior -- read the code first
* Never guess database schemas or response shapes
* Never refactor beyond the explicitly requested scope
* Never introduce abstractions for hypothetical future use
* If requirements are unclear, stop and ask instead of guessing
* Always read `spec.md` for architectural decisions before proposing structural changes
* Never modify `spec.md` without explicit user approval

---

## Final Rule

If any rule conflicts with speed, convenience, or brevity -- **the rule wins**.

<!-- mulch:start -->
## Project Expertise (Mulch)
<!-- mulch-onboard-v:1 -->

This project uses [Mulch](https://github.com/jayminwest/mulch) for structured expertise management.

**At the start of every session**, run:
```bash
mulch prime
```

This injects project-specific conventions, patterns, decisions, and other learnings into your context.
Use `mulch prime --files src/foo.ts` to load only records relevant to specific files.

**Before completing your task**, review your work for insights worth preserving — conventions discovered,
patterns applied, failures encountered, or decisions made — and record them:
```bash
mulch record <domain> --type <convention|pattern|failure|decision|reference|guide> --description "..."
```

Link evidence when available: `--evidence-commit <sha>`, `--evidence-bead <id>`

Run `mulch status` to check domain health and entry counts.
Run `mulch --help` for full usage.
Mulch write commands use file locking and atomic writes — multiple agents can safely record to the same domain concurrently.

### Before You Finish

1. Discover what to record:
   ```bash
   mulch learn
   ```
2. Store insights from this work session:
   ```bash
   mulch record <domain> --type <convention|pattern|failure|decision|reference|guide> --description "..."
   ```
3. Validate and commit:
   ```bash
   mulch sync
   ```
<!-- mulch:end -->

<!-- seeds:start -->
## Issue Tracking (Seeds)
<!-- seeds-onboard-v:1 -->

This project uses [Seeds](https://github.com/jayminwest/seeds) for git-native issue tracking.

**At the start of every session**, run:
```
sd prime
```

This injects session context: rules, command reference, and workflows.

**Quick reference:**
- `sd ready` — Find unblocked work
- `sd create --title "..." --type task --priority 2` — Create issue
- `sd update <id> --status in_progress` — Claim work
- `sd close <id>` — Complete work
- `sd dep add <id> <depends-on>` — Add dependency between issues
- `sd sync` — Sync with git (run before pushing)

### Before You Finish
1. Close completed issues: `sd close <id>`
2. File issues for remaining work: `sd create --title "..."`
3. Sync and push: `sd sync && git push`
<!-- seeds:end -->

<!-- canopy:start -->
## Prompt Management (Canopy)
<!-- canopy-onboard-v:1 -->

This project uses [Canopy](https://github.com/jayminwest/canopy) for git-native prompt management.

**At the start of every session**, run:
```
cn prime
```

This injects prompt workflow context: commands, conventions, and common workflows.

**Quick reference:**
- `cn list` — List all prompts
- `cn render <name>` — View rendered prompt (resolves inheritance)
- `cn emit --all` — Render prompts to files
- `cn update <name>` — Update a prompt (creates new version)
- `cn sync` — Stage and commit .canopy/ changes

**Do not manually edit emitted files.** Use `cn update` to modify prompts, then `cn emit` to regenerate.
<!-- canopy:end -->
