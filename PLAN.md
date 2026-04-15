# W3.6.1: Eval UI Tab — Plan

## Context

- Backend has ORM models (`eval_runs`, `eval_cases`, `eval_calls`), eval services (judges, replay), and Pydantic schemas (`EvaluationCase`, `Score`, `Rubric`), but **does NOT yet expose REST routes or a WebSocket channel for eval**. This task scope is frontend only per issue #26 title ("Eval UI tab (frontend page)").
- The frontend will be written against the REST/WebSocket shapes mandated by issue #26 (POST/GET `/api/v1/eval/runs`, GET `/api/v1/eval/runs/{id}/calls`, WebSocket channel `eval`). Until the backend routes land, the UI will compile + typecheck but runtime calls will 404. That is flagged for architect review.

## Types (`frontend/src/types/eval.ts`)

- `EvalRunStatus` = `"pending" | "running" | "completed" | "failed" | "cancelled"`
- `JudgeVerdict` = `"pass" | "fail"`
- `JudgeTier` = `"tier1" | "llm"` (mirrors `eval_calls.tier`)
- `EvalRun` (id, trainingRunId, status, startedAt, completedAt, passRate, totalCostUsd, maxCostUsd)
- `EvalCase` (id, evalRunId, caseInput: `EvaluationCasePayload`, inputHash)
- `EvalCall` (id, evalRunId, caseId, rubricVersionId, judgeModel, tier, verdict, reasoning, perCriterion, responseHash, costUsd, latencyMs, replayedFromId, createdAt)
- `EvaluationCasePayload` (prompt, output, reference, retrievedContext, conversationHistory, metadata)
- `EvalRunCreateRequest` (trainingRunId, rubricVersionIds, maxCostUsd)
- `EvalRunDetail` (run + cases[] + calls[])
- `RubricCalibrationStatus` = `"uncalibrated" | "calibrated" | "failed"`
- `RubricVersion` (id, rubricId, versionNumber, contentHash, calibrationStatus, judgeModelPin, createdAt)
- `Rubric` (id, name, description, researchBasis, versions[])
- WebSocket eval envelope events: `eval.case_completed`, `eval.run_completed`, `eval.cost_warning` — typed payloads `EvalCaseCompletedPayload`, `EvalRunCompletedPayload`, `EvalCostWarningPayload`.

## API (`frontend/src/api/eval.ts`)

- `fetchEvalRuns({ trainingRunId? })` → list (for the history panel). GET `/eval/runs?training_run_id=...`.
- `fetchEvalRun({ evalRunId })` → detail. GET `/eval/runs/{id}`.
- `fetchEvalRunCalls({ evalRunId, limit?, offset? })` → paginated calls.
- `createEvalRun({ trainingRunId, rubricVersionIds, maxCostUsd })` → POST `/eval/runs`.
- `fetchRubrics()` / `fetchRubricVersions({ rubricId })` → listing for the picker. GET `/rubrics` and `/rubrics/{id}/versions`.
- Normalization functions convert snake_case backend rows to camelCase TS types.

## Hooks (`frontend/src/hooks/useEval.ts`)

- `useEvalRuns({ trainingRunId? })`
- `useEvalRun({ evalRunId })`
- `useEvalRunCalls({ evalRunId })`
- `useRubrics()` + `useRubricVersions({ rubricId })`
- `useCreateEvalRun()` mutation
- Existing `useRuns` is reused for the training-run dropdown.

## WebSocket (`frontend/src/ws/eval-stream.ts` + `frontend/src/hooks/useEvalStream.ts`)

- Extend `WebSocketChannel` union in `types/websocket.ts` to include `"eval"`.
- `useEvalStream({ projectId, evalRunId })` subscribes to the existing shared `wsClient`, listens for envelopes on channel `"eval"`, dispatches to three callbacks via the envelope event name (discriminated union of eval payloads). Cleanup removes the listener in useEffect return. Does NOT touch the socket lifecycle (matches `useRunStream` convention).

## Components (`frontend/src/components/eval/`)

- `eval-run-list.tsx` — list of past eval runs, selectable
- `eval-run-header.tsx` — shows status / pass rate / cost / started/completed timestamps
- `rubric-selector.tsx` — multi-select rubric versions (filter to calibrated-only latest by default), with a "show all" toggle
- `training-run-selector.tsx` — dropdown of the active project's training runs + a "Standalone eval" option
- `eval-trigger-panel.tsx` — orchestrates training-run + rubric selection + max cost input + "Run evaluation" button
- `eval-case-table.tsx` — one row per case, shows prompt preview, output preview, per-rubric verdict chips, cost sum
- `eval-case-detail-drawer.tsx` — opens on row click, shows the full EvaluationCase payload, model output vs reference side-by-side (diff-like column layout), and a list of per-rubric `EvalCall` cards with verdict, critique/reasoning, per-criterion checklist, judge model, response hash, latency, cost
- `judge-verdict-badge.tsx` — typed pass/fail badge
- `cot-expansion.tsx` — collapsible panel showing reasoning text
- `cost-warning-banner.tsx` — rendered on cost warning event
- `eval-export-button.tsx` — client-side JSON export of the detail payload.

## Page (`frontend/src/pages/eval-page.tsx`)

- Root orchestrator matching `runs-page.tsx` shape. Uses hooks for data, `useEvalStream` for live case events.
- Left column: run list + trigger panel.
- Right column when a run is selected: header, cost-warning banner if applicable, case table, drawer for the selected case.
- Export button in top bar dumps `{ run, cases, calls }` as JSON.

## Routing & sidebar

- Add `<Route path="/eval" element={<EvalPage />} />` to `App.tsx`.
- Add an "Evaluation" nav item (icon `ClipboardCheck` or `ShieldCheck`) inside the "Execution" nav group in `sidebar.tsx`.

## Verification

- `npm run lint` (prettier check)
- `npm run typecheck` (tsc --noEmit)
- `npm run build` (full tsc + vite build)
- Manually audit every `useEffect` subscription for a cleanup function, every function for an explicit return type, zero `any`, zero inline type definitions, zero magic strings.

## Out of scope / punted

- Backend REST routes + `eval` WS channel implementation (issue scope is the frontend page; the spec lists the endpoints but the architect will need a separate issue to land them).
- Playwright E2E — the acceptance criteria call for it, but a live test requires a running backend + OpenAI API key; punted to architect.
- The diff view between model output and reference uses a plain two-column scrollable display rather than a syntax-highlighted diff, to avoid adding a dependency.
