# LLM-as-Judge Evaluation Harness

Calibrated, binary pass/fail evaluation with a reproducible audit trail. Every judgment is schema-validated, content-hashed, and replayable. Rubrics are stored in SQLite mirroring the `config_versions` pattern; runs and judge calls live in append-only tables so history cannot be silently mutated.

## Architecture

Two-tier design — deterministic checks first, single LLM judge second, ChainPoll majority-vote as a variant. No multi-model panel. No inline eval during training.

```
┌─────────────────────────────────────────────────────────┐
│  EvaluationRun (orchestrator)                           │
│    └── EvaluationCase[]                                 │
│                                                         │
│  TIER 1 — Deterministic  (target ~80% of checks, $0)    │
│    • JSON schema / regex / format / length validators   │
│    • OpenAI Moderation API  [R12]                       │
│                                                         │
│  TIER 2 — Single LLM Judge  (target ~20% of checks)     │
│    • Binary pass/fail with G-Eval CoT rubric  [R1]      │
│    • instructor + Pydantic, reasoning-before-score [R7] │
│    • OpenAI-only: gpt-4o-mini default, gpt-4o opt-in    │
│    • ChainPoll variant [R4]: N=3 calls at temp=0.3,     │
│      majority vote, Hallucination rubric only           │
│                                                         │
│  PROVENANCE LAYER (cross-cutting)                       │
│    • SHA256: prompt, output, rubric_version, response   │
│    • Append-only `eval_calls` table (SQLite trigger)    │
└─────────────────────────────────────────────────────────┘
          │
          ▼
  FEEDBACK LOOP  [R10]
  failing case → dataset → regression suite
```

## Rubrics

Four rubrics ship in v1. All additive-binary (atomic pass/fail criteria with points) per R11 — no Likert scales, no holistic ratings.

| Rubric | Tier | Research basis | Criteria |
|---|---|---|---|
| **Faithfulness** | Tier 2 | R1, R3 | Claims supported by reference; no fabricated entities; no contradictions |
| **Instruction-following** | Tier 2 | R3, R5, R11 | Addresses question; follows format; stays in scope; no hallucinated entities |
| **Safety** | Tier 1 + Tier 2 | R6, R12 | Moderation prescreen (Tier 1) + Constitutional AI dimensions (Tier 2): helpful, honest, harmless |
| **Hallucination (ChainPoll)** | Tier 2 + ChainPoll | R4 | 3 judge calls at temp=0.3, majority verdict, all reasonings stored |

Each rubric has a pinned judge model (no `-latest` aliases), ≥5 few-shot examples covering both pass and fail, and a `research_basis` listing the R-IDs that justify its design.

## Calibration Methodology

Calibration follows Critique Shadowing (R3). 200 outputs are sourced and stratified across ≥10 domain buckets; 100 are hand-labeled pass/fail with one-line critiques, targeting a roughly 50/50 class split to prevent TPR/TNR from reflecting imbalance. Labels are split deterministically by hash into 50 few-shot examples and 50 held-out.

A rubric is **calibrated** iff TPR ≥ 0.90 AND TNR ≥ 0.90 on the held-out 50; **provisional** iff both are ≥ 0.80; **uncalibrated** otherwise. Release bar: at least two rubrics calibrated, zero uncalibrated.

**Honesty note on n=50.** The 95% Clopper–Pearson confidence interval on a TPR of 0.90 measured on 50 samples is roughly [0.78, 0.97]. Every downstream claim — including resume phrasing — avoids quoting precise TPR/TNR percentages and uses the phrase "calibrated TPR/TNR ≥ 0.90 on 50 held-out human labels." Provisional rubrics are always listed explicitly.

## Research Basis

Every design choice in this harness traces back to a named paper, framework, or practitioner. The full bibliography lives in `docs/references.md`; the table below anchors the decisions.

| ID | Source | Applied to |
|---|---|---|
| R1 | Liu et al. 2023 — G-Eval | Chain-of-thought scoring in Tier 2 judge (0.514 Spearman vs human) |
| R3 | Hamel Husain — Critique Shadowing | Binary pass/fail labeling; TPR/TNR calibration methodology |
| R4 | DataDog — ChainPoll | N-call majority vote for hallucination detection |
| R5 | MultiChallenge (ACL 2025) | Validates binary rubrics reach 93% human alignment |
| R6 | Anthropic — Constitutional AI | Safety rubric dimension design |
| R7 | OpenAI Structured Outputs / `instructor` | Pydantic-validated judge outputs, reasoning-before-score ordering |
| R11 | Amazon Nova | Additive-binary rubrics outperform holistic Likert by ~49% |
| R12 | OpenAI Moderation (`omni-moderation-latest`) | Tier-1 safety prescreen |

Full citations with URLs and per-R-ID usage notes: [`docs/references.md`](docs/references.md).

## Replay Mechanism

Narrow scope: **eval-judgment replay only**. Every row in `eval_calls` stores `response_hash = SHA256(raw_judge_response_text)`. The `llmw eval replay <eval_call_id>` command re-runs the exact same `(case_input, rubric_version, judge_model)` triple — rubric versions are immutable by content hash, so a replay of an old judgment never picks up newer rubric edits. The replay writes a new linked row via `replayed_from_id`; the original is never overwritten. Mismatched hashes detect OpenAI model drift across time.

Full training-run replay is explicitly out of scope for v4.

## CI Integration

`llmw eval --config eval.yaml` is the CI entry point. GitHub Actions workflow at `.github/workflows/eval-gate.yml` runs on every PR that touches training or rubric files. Gate passes iff every **calibrated** rubric meets its per-rubric threshold in `eval.yaml` (default 0.80) AND no rubric regresses by more than 5pp versus the prior run. Cost is capped per-run via `max_cost_usd` in the config; cap exceeded aborts cleanly with a partial-results flush and `eval_runs.status = 'aborted_cost_cap'`.

## Training Lifecycle Integration

**Stage 11 of the 14-stage training lifecycle is the `evaluation` stage. In v4 it is a reserved no-op placeholder — training emits `stage_enter` and `stage_complete` events for stage 11 but performs no work. Evaluation is triggered manually via the UI button or `llmw eval` CLI, never automatically at training completion.**

This is deliberate reservation, not a missing feature. The v4 improvement plan addresses risk R-15 ("Stage 11 'evaluation' placeholder is misleading in 14-stage claim") by requiring explicit state-transition emission even in the no-op path. The "14-stage instrumented" claim remains honest because stage 11 does emit lifecycle events — the stage appears in every run's timeline with `output_summary = "reserved no-op; v4 eval runs manually via UI or CLI"` and `duration_ms = 0`.

The unconditional emission lives in `backend/app/services/trainer.py` in the main run sequence, placed between `training_start` (stage 9 / 10) and `artifact_finalization` (stage 13). Orchestrator-side stage ordering is defined in `backend/app/services/orchestrator.py` (`_STAGE_ORDER`). No code path in the trainer or orchestrator auto-triggers the eval harness at run completion; the separation keeps training deterministic and eval cost visible to the operator.
