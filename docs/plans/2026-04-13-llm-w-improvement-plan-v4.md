# LLM-W v4 Improvement Plan

**Owner:** Freddy Song
**Version:** v4 — architecturally closed. PoLL removed, MLX dropped, replay scope narrowed, quality metrics finalized, all acceptance criteria sharpened for verifiability.
**Supersedes:** v3.
**Purpose:** Raise LLM-W from a scaffolded fine-tuning workbench to an observability-first training + evaluation platform suitable for MLE interviews.
**Target:** 4–6 weeks part-time.
**North star:** *"A local-first LLM fine-tuning workbench with a research-backed observability and evaluation harness, benchmarked across edge (Apple Silicon) and cloud (CUDA) backends."*

---

## 1. Delta from v3

| Decision | v3 | v4 |
|---|---|---|
| Tier 3 multi-model panel (PoLL) | Removed | Confirmed removed |
| Apple Silicon training framework | MLX (fast, separate codepath) | **PyTorch MPS** (same codepath as CUDA) |
| MLX mentions | "May mention in BENCHMARKS.md" | **Dropped entirely**, not even as future work |
| Benchmark quality metric | Held-out perplexity primary, with caveats section | **Perplexity (headline) + judge harness pass rates (sanity check)** |
| "Reconstructible replay" language | Kept with softening | **Replaced** with narrow "eval-judgment replay" (Option A) |
| Rubric storage | Unspecified | **SQLite, mirroring `config_versions` pattern** |
| Stage 11 `evaluation` behavior | Ambiguous | **No-op placeholder; eval runs manually only** |
| Calibration held-out size | 50, with §6.12 honesty note | **50 confirmed**; bullets phrase without precise percentages |
| Three open design questions | Flagged | **Resolved** (see §7) |

**Net effect:** WS2 simplifies (~5 hrs), eval harness scope is tighter and more defensible, resume claims are cleaner.

---

## 2. Guiding Principles (unchanged)

1. Observability is the differentiator. Every training/eval feature emits structured, queryable telemetry.
2. Config-as-source-of-truth. Every run reproducible from a single versioned YAML + input hash.
3. Binary pass/fail over numeric scales for evaluation (Critique Shadowing — Hamel Husain).
4. Provider-abstracted I/O. Judges and compute backends swap via config.
5. Plumbing over PoC. Prefer fully-wired features over half-built novelty.
6. Do not rebuild what the ecosystem has. Our value is rubric design, calibration, and the feedback loop.
7. Cite the research. Every design choice traces back to a named paper, framework, or practitioner.

---

## 3. Research Foundation

| ID | Source | Used for |
|---|---|---|
| R1 | Liu et al. 2023 — G-Eval | Chain-of-thought scoring in Tier 2 judge (0.514 Spearman vs human) |
| R3 | Hamel Husain — Critique Shadowing | Binary pass/fail labeling; TPR/TNR calibration methodology |
| R4 | DataDog — ChainPoll | N-call majority vote on same judge model for hallucination detection |
| R5 | MultiChallenge benchmark (ACL 2025) | Validates binary rubric questions achieve 93% alignment with human eval |
| R6 | Anthropic — Constitutional AI principles | Safety rubric dimension design |
| R7 | OpenAI Structured Outputs / `instructor` library | Pydantic-validated judge outputs; reasoning-before-score ordering |
| R8 | Confident AI — DeepEval docs | Reference for 60+ metric patterns |
| R9 | Promptfoo docs | CI/CD patterns; `llm-rubric` assertion; PR gate workflow |
| R10 | Langfuse docs | Production trace → dataset → regression flywheel |
| R11 | Amazon Nova | Additive-binary rubric criteria improve evaluation 49% over holistic Likert |
| R12 | OpenAI Moderation API (`omni-moderation-latest`) | Tier-1 safety prescreen |
| R13 | PDF-1 reference architecture | Adapted to two-tier structure (Tier 3 panel dropped) |

**Removed from v2:** R2 (Verga et al. PoLL) — cross-family panel pattern dropped.

---

## 4. Workstreams

Each step numbered `W{n}.{step}` and carries:
- **Description** — what the step does
- **Acceptance Criteria (AC)** — binary pass/fail checks
- **Verification** — how to confirm AC without ambiguity

### WS1 — Repo hygiene & demo surface

**Goal:** cold GitHub visitor answers "what does this do?" in ≤10s and sees a running demo in ≤20s.

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W1.1 | Write `README.md` | Present sections: (a) one-sentence pitch; (b) Mermaid architecture diagram; (c) tech stack table; (d) quickstart (`docker-compose up`); (e) feature matrix; (f) benchmark-results placeholder table; (g) demo GIF embedded; (h) links to `SPEC.md`, `BENCHMARKS.md`, `EVAL.md`; (i) research-citations footer listing R-IDs | Section headings present; all internal links resolve; Mermaid renders on GitHub |
| W1.2 | Quickstart verification | `docker-compose up` on a fresh clone produces a running UI at `localhost:5173` within 20 min on first run (image build + startup). Subsequent runs ≤2 min. | CI job on a fresh runner posts green check on every README PR (or, fallback: manual test on a clean VM with screenshots in PR) |
| W1.3 | Record demo GIF | Duration 45–60s. Shows: start QLoRA run → metric streaming updating ≥1×/sec → checkpoint event → run-comparison view. File ≤8 MB. Committed at `docs/assets/demo.gif`. | File exists; GitHub preview plays; size check in CI |
| W1.4 | Populate stubs | `BENCHMARKS.md`, `EVAL.md` committed with all planned section headings (even if content-empty) | Files exist at repo root; `grep "##"` shows ≥5 headings each |
| W1.5 | Clean hidden dotfolders | Each of `.beads/ .canopy/ .mulch/ .overstory/ .seeds/` either has a `README.md` explaining purpose *or* is in `.gitignore`. No unexplained dotfolder. | `ls -la` shows every `.*` directory either tracked with README or gitignored |
| W1.6 | LICENSE | MIT license at repo root | `LICENSE` file exists, header line matches MIT template |
| W1.7 | CITATION.cff | Valid CFF 1.2.0 | `cffconvert --validate` exits 0 |

**DoD:** Recruiter visiting repo cold can identify the project and launch the demo unaided.

---

### WS2 — Multi-hardware benchmarking study

**Goal:** Defensible cross-hardware benchmark of LoRA fine-tuning on three backends.

**Setup (locked):**
- **Model:** `Qwen/Qwen2.5-1.5B-Instruct`
- **Dataset:** `HuggingFaceH4/ultrachat_200k`, 2,000-example subset, seed=42
- **Config:** LoRA r=16 α=32, 1 epoch, seq_len=512, batch=4, lr=2e-4
- **Backends (all PyTorch):**
  - **A.** M1 Pro MBP, device=`mps`
  - **B.** M4 Pro MBP, device=`mps`
  - **C.** RunPod A10 24GB, device=`cuda` with bitsandbytes QLoRA
- **Cloud spend cap:** $20

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W2.1 | Freeze bench config | `configs/bench/qwen15b-lora.yaml` committed. SHA256 of file logged with every run. | `sha256sum` of config matches hash recorded in `runs.config_hash` for all 3 runs |
| W2.2 | Unified runner script | `scripts/bench/run_local.sh` takes `--device {mps,cuda}` and `--output-dir`. Emits identical metric JSON schema regardless of device. | Run on M4 Pro and on A10 produce JSON files with identical top-level keys |
| W2.3 | Metric capture per run | DB records: `tokens_per_sec`, `time_to_first_checkpoint_s`, `wall_clock_s`, `peak_memory_mb`, `final_training_loss`, `heldout_perplexity`, `cost_usd`, `judge_pass_rate`. Missing metrics recorded as NULL with a `metric_unavailable_reason` column populated. | 8/8 columns present per run; NULLs have reason strings; no silent drops |
| W2.4 | Frozen eval split | 200-example held-out validation set, seed=42, SHA256 hash of the split committed to repo at `configs/bench/eval_split.hash`. Hash recorded with every run. | `runs.eval_split_hash` matches committed hash across all 3 runs |
| W2.5 | Judge harness sanity check | After each training run, 50-prompt generation set is scored by WS3 Tier-2 judge on `faithfulness` and `instruction_following` rubrics. Pass rate recorded in `runs.judge_pass_rate`. Prompt set is disjoint from calibration set and eval split. | 50 generations per backend exist in `artifacts/`; `judge_pass_rate` populated |
| W2.6 | Populate BENCHMARKS.md | Results table: 3 backends × 8 metrics. Throughput-vs-memory PNG chart. $/1M-token column. 200-word analysis with ≥1 surprising finding. "Cost governance" appendix with actual cloud spend. | Document renders in GitHub; all cells filled; chart PNG committed |
| W2.7 | Cost governance | Cloud run on spot instance. `max_wall_clock_hours` kill-switch in trainer. Total spend ≤$20, recorded in BENCHMARKS.md. | Spend documented; spot pricing confirmed in RunPod dashboard screenshot |

**DoD:** BENCHMARKS.md populated with real numbers; 3 runs queryable in SQLite with identical config hashes; reviewer can reproduce any run via `scripts/bench/run_local.sh`.

---

### WS3 — LLM-as-Judge evaluation harness

**Goal:** Calibrated binary-pass/fail eval harness with reproducible audit trail.

**Architecture (two-tier, adapted from R13):**

```
┌─────────────────────────────────────────────────────────┐
│  EvaluationRun (orchestrator)                           │
│    └── EvaluationCase[]                                 │
│                                                         │
│  TIER 1 — Deterministic  (target: ~80% of checks, $0)   │
│    • JSON schema / regex / format / length validators   │
│    • OpenAI Moderation API  [R12]                       │
│                                                         │
│  TIER 2 — Single LLM Judge  (target: ~20% of checks)    │
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

#### W3.1 — Schema layer

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W3.1.1 | New SQLAlchemy models + Alembic migration | Tables: `rubrics` (name, description, research_basis, created_at), `rubric_versions` (rubric_id, version_number, yaml_blob, content_hash, diff_from_prev, created_at), `eval_runs` (run_id optional FK to training run, rubric_version_ids[], started_at, completed_at, pass_rate, total_cost_usd), `eval_cases` (eval_run_id, case_input, expected_output, metadata), `eval_calls` (eval_run_id, case_id, rubric_version_id, judge_model, tier, verdict, reasoning, response_hash, cost_usd, latency_ms, created_at). Mirrors existing `config_versions` pattern. | Migration applies cleanly on fresh DB; schema diff matches design doc |
| W3.1.2 | Append-only enforcement on `eval_calls` | SQLite trigger rejects UPDATE and DELETE on `eval_calls`. | Integration test: attempt UPDATE raises `OperationalError`; attempt DELETE raises `OperationalError` |
| W3.1.3 | Pydantic contracts | `EvaluationCase` (prompt, output, optional reference, optional retrieved_context, optional conversation_history, metadata), `Score` (verdict: Literal['pass','fail'], reasoning: str non-empty, per_criterion: dict[str, bool], cost_usd, latency_ms, judge_model, rubric_version, response_hash). Reasoning field ordered before verdict in schema [R7]. | 100 random-input round-trip test passes; `instructor`-parsed schema matches |
| W3.1.4 | `Rubric` Pydantic model | Required fields: `id`, `version`, `description`, `scale: Literal['binary']`, `criteria: list[Criterion]` (each atomic binary + points), `few_shot_examples: list[Example]` with ≥5 containing **both pass and fail instances**, `judge_model_pin: str` (no `-latest` aliases), `research_basis: list[str]` (R-IDs), optional `chainpoll: {n: int, model: str, temperature: float}`. | Invalid rubric (e.g., only pass examples, or `-latest` model) raises on load; lint rule rejects `-latest` in YAML |

#### W3.2 — Judge provider

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W3.2.1 | `JudgeProvider` ABC | Abstract class with `evaluate(case, rubric) -> Score`. Mirrors `RecommendationEngine` pattern in `backend/app/services/ai_recommender.py`. Lives in `backend/app/services/eval/judge.py`. | Abstract methods enforced; cannot instantiate base class |
| W3.2.2 | `OpenAIJudge` concrete impl | Supports `gpt-4o` and `gpt-4o-mini`. Uses `instructor>=1.0,<2.0` for schema-validated returns. Pulls API key from existing `settings_service`. | Mock API test: 10 synthetic responses all schema-valid |
| W3.2.3 | Tier-1 deterministic registry | Decorator-registered validators: `json_schema`, `regex_match`, `max_length`, `contains_keywords`, `moderation_openai`. | p95 latency <50ms on 200-case batch in unit test |
| W3.2.4 | Tier-2 G-Eval implementation | Auto-generates eval steps from criteria per R1 methodology; includes steps in prompt; scores output. | Validated on 200 WS2 outputs; all outputs produce valid `Score` object |
| W3.2.5 | ChainPoll variant | When rubric has `chainpoll` config, judge called N=3 times at temperature=0.3; majority-vote verdict; all N reasonings stored in `eval_calls`. Used for Hallucination rubric only. | Integration test: N=3 run with deliberate 2–1 split has dissenting reasoning queryable from DB |

#### W3.3 — Rubric set v1

Four rubrics, all additive-binary [R11], stored as YAML in `rubrics/` and mirrored into `rubric_versions` table:

| Rubric | Research basis | Criteria | Tier |
|---|---|---|---|
| **Faithfulness** | R1, R3 | Claims supported by reference; no fabricated entities; no contradictions | Tier 2 |
| **Instruction-following** | R3, R5, R11 | Addresses question; follows format; stays in scope; no hallucinated entities | Tier 2 |
| **Safety** | R6, R12 | Tier 1 Moderation prescreen + Tier 2 CAI-inspired (helpful, honest, harmless) as 3 binary criteria | Tier 1 + Tier 2 |
| **Hallucination (ChainPoll)** | R4 | 3 judge calls at temp=0.3, majority verdict | Tier 2 + ChainPoll (N=3) |

#### W3.4 — Calibration workflow

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W3.4.1 | Source calibration outputs | 200 outputs stratified across ≥10 domain buckets. SHA256 hash of source file committed. Saved to `eval/calibration/v1_raw.jsonl`. | File exists; stratification documented in header comment |
| W3.4.2 | Hand-label 100 | Pass/fail + one-line critique per R3. **Stratify target: roughly 50/50 pass/fail split** to avoid class imbalance. Saved to `eval/calibration/v1_labels.jsonl`. | 100 labels committed; label class distribution 40–60/40–60 split |
| W3.4.3 | Split 50/50 few-shot vs held-out | Split by committed hash rule (deterministic). 50 examples used in rubric few-shots; 50 held out for measurement. | Split script produces identical output across runs |
| W3.4.4 | Calibration script | `scripts/eval/calibrate.py` takes labeled set + rubric YAML. Reports per-rubric `{TPR, TNR, precision, recall, F1}` on held-out 50. Writes metrics to `rubric_versions.calibration_metrics` JSON column. | Script exit 0; metrics populated in DB |
| W3.4.5 | Calibration gate | Rubric status: **calibrated** iff TPR ≥ 0.90 AND TNR ≥ 0.90; **provisional** iff both ≥ 0.80; **uncalibrated** otherwise. Release bar: ≥2 rubrics `calibrated`, **zero rubrics** `uncalibrated`. | DB query at release shows all 4 rubrics ≥ provisional, ≥2 calibrated |
| W3.4.6 | Honesty in docs | EVAL.md states: held-out n=50; 95% CI on TPR at 0.90 is roughly [0.78, 0.97]; provisional rubrics explicitly listed. | EVAL.md contains CI language; resume bullets do not cite precise percentages |

#### W3.5 — Eval-judgment replay (narrow)

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W3.5.1 | Response hashing | Every row in `eval_calls` has `response_hash = SHA256(raw_judge_response_text)`. | New row without hash raises `IntegrityError` (NOT NULL constraint) |
| W3.5.2 | Replay CLI | `llmw eval replay <eval_call_id>` re-runs the same `(case_input, rubric_version, judge_model)` combination. Reports hash match/divergence. Does **not** overwrite the original row — writes a new `eval_calls` row linked via `replayed_from_id`. | Replay on an existing row produces a new row; divergence detection tested by mocking changed API response |
| W3.5.3 | Rubric-version pinning | Rubric version used for a judgment is immutable via content hash; replay uses exact same version, never "current." | Unit test: replay of old judgment does not pick up newer rubric edits |

#### W3.6 — Surfaces (UI + CLI)

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W3.6.1 | Eval UI tab | New page `frontend/src/pages/eval-page.tsx`. Flow: pick run → pick rubric version → trigger eval → per-case verdicts with CoT expandable → export JSON. Streams via existing WebSocket infra. | Playwright E2E click-through passes |
| W3.6.2 | CLI / CI mode | `llmw eval --config eval.yaml` command. Exits 0 iff every calibrated rubric's pass rate is ≥ per-rubric threshold in `eval.yaml` AND no rubric falls >5pp below prior run's rate. Default threshold 0.80. | `.github/workflows/eval-gate.yml` validates on PR; induced regression correctly blocks merge |
| W3.6.3 | Cost ceiling | `eval.yaml` supports `max_cost_usd`. Exceeding cap aborts cleanly with partial-results flush. | Integration test: cap at $0.01 triggers early termination, `eval_runs.status = 'aborted_cost_cap'` |
| W3.6.4 | Stage 11 integration | Training lifecycle stage 11 (`evaluation` in `orchestrator.py`) remains a no-op placeholder. Eval is launched manually only — via UI button or CLI. Document this explicitly in EVAL.md. | Training run completes with stage 11 marked "skipped"; no auto-eval fires |

**DoD for WS3:** Pipeline run on 200 WS2 outputs shows per-rubric pass rates; ≥2 rubrics calibrated, none uncalibrated; results exportable; one GitHub Actions run demonstrates CI quality gate; replay command verified against synthetic drift.

---

### WS4 — Distributed training plumbing (FSDP)

**Goal:** Validate FSDP path with rank-aware observability on cloud hardware.
**Cloud cap:** $10.

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W4.1 | Refactor trainer to `accelerate` | Training entry point uses `accelerate.Accelerator`. Existing stdout-JSON event contract for `orchestrator.py` preserved — only rank 0 emits to stdout. Single-GPU run: loss curve matches pre-refactor within 1e-3. | Diff loss curves pre/post refactor; side-by-side stored in `docs/assets/fsdp-loss-match.png` |
| W4.2 | Accelerate configs | Committed: `configs/accelerate/single_gpu.yaml`, `fsdp_2gpu.yaml`, `deepspeed_zero2_2gpu.yaml`. All enable `gradient_checkpointing: true` by default. | Files exist; `accelerate launch --config_file <file> train.py --dry-run` validates each |
| W4.3 | Rank-aware observability | Metric emission gated to `accelerator.is_main_process`. Per-rank GPU memory emitted on separate side channel. | 2-rank mock test: 1 main metric stream, 2 memory streams visible |
| W4.4 | Atomic rank-aware checkpointing | Rank 0 writes; ranks synchronize on barrier before resume. Kill-rank-1-mid-save test: resume produces model state dict whose byte hash matches pre-save hash within fp tolerance. | Integration test: kill signal to rank 1 during save, then resume; `torch.allclose(pre, post, atol=1e-5)` passes |
| W4.5 | Cloud validation | One 2×L4 RunPod run of same Qwen config. Records FSDP throughput, per-rank peak memory, wall clock. Documented in BENCHMARKS.md "Distributed scaling" section. Spend ≤$10. | RunPod invoice ≤$10; BENCHMARKS.md shows real FSDP throughput number |
| W4.6 | Scope lock | SPEC.md updated with explicit out-of-scope list: multi-node, tensor-parallel, pipeline-parallel. | SPEC.md section `## Out of Scope` contains these three items verbatim |

**DoD:** `accelerate launch --config_file configs/accelerate/fsdp_2gpu.yaml train.py ...` succeeds on cloud; 2-rank run visible in observability UI; BENCHMARKS.md shows a real FSDP throughput number.

---

### WS5 — Polish & resume artifact production

**Goal:** Repo is recruiter-ready; reader grasps novelty in ≤10 min.

| Step | Description | Acceptance Criteria | Verification |
|---|---|---|---|
| W5.1 | Case study writeup | `docs/case-study.md`, 700–900 words, uses WS2 numbers, ≥3 embedded charts, cites R1/R3/R4 and PDFs. Linked from README. | Word count in range; charts render; R-IDs cross-referenced in `docs/references.md` |
| W5.2 | Architecture diagram | Mermaid in README: Observability core → Training runner (single / FSDP) → Eval harness (Tier 1/2 + ChainPoll) → Feedback loop. | Mermaid renders on GitHub; all four boxes present |
| W5.3 | Second demo GIF | Eval flow: load rubric YAML → trigger eval → drill into failing case with CoT. ≤8 MB. | File exists at `docs/assets/eval-demo.gif`; plays on GitHub |
| W5.4 | Resume bullets | 3 final bullets with real numbers. Phrased to survive n=50 CI honesty (no precise TPR/TNR percentages; instead "calibrated TPR/TNR ≥ 0.90 on 50 held-out human labels"). Draft in `docs/resume-bullets.md`. | Each bullet ≤2 lines at 10pt; numbers sourced from DB/BENCHMARKS.md |
| W5.5 | Repo triage | `.beads/` issues closed or migrated to GitHub Issues. Zero TODO comments in WS1–WS4 paths without `TODO(context): reason — remove when [condition]` format. | `grep -rE "TODO(?!\()" backend/app frontend/src` returns empty |
| W5.6 | Bibliography | `docs/references.md` lists all R-IDs with full citations, URLs, and which WS/component references each. | Every R-ID in §3 table present with URL and back-references |
| W5.7 | Reading notes | `docs/reading-notes/geval.md`, `chainpoll.md`, `constitutional-ai.md`. Each answers: main contribution, method, key limitation, why it applies to LLM-W. | Three files exist, each answers four questions in ≥100 words per question |

**DoD:** Recruiter-ready; reader grasps novelty in ≤10 min.

---

## 5. Resume Bullets (drafts — populate numbers post-WS)

Phrased to survive n=50 calibration CI width:

1. Built a local-first LLM fine-tuning workbench for QLoRA/LoRA PEFT workflows with a 14-stage instrumented run lifecycle, atomic checkpointing, and WebSocket metric streaming; benchmarked Qwen2.5-1.5B training across M1 Pro, M4 Pro, and cloud A10 backends (PyTorch MPS/CUDA), measuring **[X]** tokens/sec and **[Y]** GB peak memory at **$[Z]** per 1M training tokens.
2. Designed a two-tier LLM-as-Judge evaluation harness (deterministic checks + G-Eval CoT single judge [Liu 2023]) with Critique-Shadowing calibration [Husain] and a ChainPoll [DataDog] variant for hallucination detection, achieving calibrated TPR/TNR **≥ 0.90 on 50 held-out human labels** across faithfulness and instruction-following rubrics.
3. Engineered a production-failure-to-regression-test feedback loop [Langfuse pattern]: failing eval cases auto-captured into a persistent dataset with content-hashed rubric versions and SHA256 judge-response hashing, enabling detection of judge-model drift across historical evaluations.
4. Plumbed FSDP training via HuggingFace `accelerate` with rank-aware observability and atomic checkpoint synchronization, achieving **[X]×** throughput on 2×L4 vs single-GPU baseline.

---

## 6. Out of Scope (v4)

- DPO / ORPO / RLHF training
- Multi-model panel judges (PoLL)
- Multi-node / tensor-parallel / pipeline-parallel training
- Agent trajectory evaluation
- Voice / multimodal fine-tuning
- Hosted SaaS; auth; multi-tenancy
- Custom CUDA kernels
- MLX (dropped entirely; not documented as future work)

---

## 7. Resolved Design Questions

Questions raised during v3 review, now closed:

| Question | Resolution |
|---|---|
| Does eval run inline during training or post-hoc? | **Post-hoc only.** Stage 11 of training lifecycle is a no-op placeholder. Eval triggered manually via UI or CLI. |
| Where are rubrics stored? | **SQLite**, mirroring `config_versions`: `rubrics` table + `rubric_versions` table (full YAML blob, content hash, diff from prev). YAML files in `rubrics/` are the input format; DB is the source of truth for eval calls. |
| What does "replay" mean? | **Eval-judgment replay only** (narrow). Re-run a single `(case, rubric_version, judge_model)` triple and check SHA256 hash of the judge response against the stored hash. Detects OpenAI model drift. Full training-run replay is out of scope for v4. |
| MLX on Macs? | **Dropped.** Use PyTorch MPS. Same codepath as CUDA. Not mentioned in BENCHMARKS.md even as future work. |
| Calibration held-out set size? | **n=50 confirmed.** Bullets phrased with "≥ 0.90 on 50 held-out" rather than precise percentages to avoid false precision. |
| Why perplexity + judge harness? | Perplexity is headline (cheap, standard). Judge pass rates are sanity check — shows all three backends produce equivalent-quality outputs. Combined, the story is "quality equivalent across backends; choose by throughput/cost." |

---

## 8. Final Risk Re-Validation

Systematic review; every risk from v3 plus anything new surfaced during this iteration.

| ID | Risk | Severity | Status | Mitigation |
|---|---|---|---|---|
| R-01 | Calibration bar ≥0.90 on n=50 is statistically noisy | MED | **Accepted, documented** | W3.4.6 forces honesty language in EVAL.md and bullet phrasing; tri-state (calibrated/provisional/uncalibrated) softens the gate |
| R-02 | "Reconstructible replay" overclaim | MED | **Resolved** | Language replaced with "eval-judgment replay" throughout; narrow scope defined in W3.5 |
| R-03 | Cross-framework benchmark validity (MLX vs bitsandbytes) | HIGH (v3) | **Eliminated by design** | MLX dropped; PyTorch MPS + CUDA is one framework; "same code, three devices" is unambiguous |
| R-04 | Gradient checkpointing default on 2×L4 | LOW | **Resolved** | W4.2 pins `gradient_checkpointing: true` in default config |
| R-05 | 10-min quickstart claim | LOW | **Softened** | W1.2 AC: ≤20 min first run, ≤2 min subsequent; documented in README |
| R-06 | Agent trajectory / Inspect AI / Ragas absent | LOW | **Deferred** | Explicit v5 roadmap in README; not v4 scope |
| R-07 | Resume defense requires primary-source familiarity | LOW | **Addressed** | W5.7 reading notes produce summaries of G-Eval, ChainPoll, CAI |
| R-08 | `instructor` API drift | LOW | **Addressed** | Pinned `instructor>=1.0,<2.0` in `pyproject.toml` |
| R-09 | ChainPoll variance at temp=0 too low | LOW | **Addressed** | W3.2.5 pins temp=0.3 for ChainPoll only; default temp elsewhere unchanged |
| R-10 | Append-only `eval_calls` bypassable at app level | LOW | **Addressed** | W3.1.2 requires SQLite trigger enforcement with test |
| R-11 | Judge pass rates too close across backends to be informative | LOW | **Accepted** | Expected outcome; narrative pivots to "quality equivalent → choose by throughput/cost." Documented in BENCHMARKS.md analysis |
| R-12 | Docker on Mac blocks GPU training | N/A | **Designed around** | Workbench ships in Docker; training subprocess runs natively via `scripts/bench/run_local.sh` |
| R-13 | Trainer refactor to `accelerate` breaks stdout-JSON event contract | MED | **Addressed** | W4.1 AC explicitly requires stdout emission gated to `is_main_process`; loss-curve regression test |
| R-14 | Training dispatcher currently rejects Modal env; may block cloud FSDP path | LOW | **Accepted** | WS4 uses RunPod direct (SSH + docker), not Modal. Modal remains stubbed. |
| R-15 | Stage 11 "evaluation" placeholder is misleading in 14-stage claim | LOW | **Addressed** | EVAL.md documents stage 11 as "reserved; manual-eval-only in v4"; resume bullet 1's "14-stage instrumented" remains honest because stage 11 does emit state transitions even as a no-op |
| R-16 | Hand-labeling 100 examples is emotionally taxing; may quality-degrade late | LOW | **Accepted** | W3.4.2: label in two sessions across two days; include 5 previously-labeled examples in session 2 to detect drift |
| R-17 | Rubric YAML drift between disk and DB | MED | **Addressed** | W3.1.1: DB is source of truth; disk YAML is write-only input format. Loader writes new version on every change; no "sync" step. |
| R-18 | Calibration class imbalance skews TPR/TNR | MED | **Addressed** | W3.4.2: 40–60/40–60 split enforced in labels |

**Severity rollup:**
- **High:** 0 (R-03 eliminated)
- **Medium:** 4 — all with explicit mitigations in ACs
- **Low:** 13 — 11 addressed, 2 accepted with documented rationale

**Design bulletproofness check:** Every medium risk has a named AC as its mitigation. Every low risk is either closed or has explicit acceptance rationale. No known unaddressed risk.

---

## 9. Weekly Cadence

| Week | Focus | Output |
|---|---|---|
| 1 | WS1 + start WS2 Mac runs | README + GIF + 2 Mac benchmark runs |
| 2 | WS3 schema + `JudgeProvider` + calibration labels (batch 1) | DB migration applied; 50 labels done |
| 3 | WS3 Tier 1/2 + calibration complete + WS2 cloud run + WS2 judge sanity | ≥2 rubrics calibrated; 3-backend table populated |
| 4 | WS3 ChainPoll + WS3 UI tab + WS4 accelerate refactor | Hallucination rubric calibrated; eval page works; single-GPU parity verified |
| 5 | WS4 FSDP cloud run + WS3 CI gate + WS5 writeup + reading notes | FSDP throughput documented; `.github/workflows/eval-gate.yml` green; case study draft |
| 6 | Polish, final README, resume bullets locked | Repo recruiter-ready |

---

## 10. Kill Criteria

Stop and reassess if:
- Week 2 ends with no complete WS2 benchmark table
- Week 4 ends with zero calibrated rubrics
- Cloud spend passes $50 total
- `accelerate` refactor breaks single-GPU loss parity and can't be resolved in 4 hrs

**Cut order if slipping:** WS4 → ChainPoll variant → second demo GIF → case-study writeup.
**Never cut:** WS2 benchmarking, Tier-1+Tier-2 eval, calibration of faithfulness + instruction-following rubrics.

---

## 11. Codebase Dependencies (what's greenfield vs. reusable)

From gap analysis — hooks and integration points:

| Work | Status in current codebase | Action |
|---|---|---|
| 14-stage run lifecycle | **Implemented** (`orchestrator.py:42-74`) | Stage 11 wire-through deferred; stays placeholder |
| Model adapter pattern | **Implemented** (`backend/app/adapters/base.py`) | No changes needed for WS2/WS3/WS4 |
| WebSocket infra | **Implemented** (`backend/app/api/websocket/`) | Reused by WS3 eval page; no changes |
| Event bus | **Implemented** (`backend/app/core/events.py`) | Reused |
| Training subprocess | **Implemented** (`trainer.py` + `training_dispatcher.py`) | WS4 refactors to `accelerate`; stdout-JSON contract preserved |
| Settings / API keys | **Implemented** (`settings_service.py`) | `OpenAIJudge` consumes existing OpenAI client config |
| Provider abstraction | **Partial** (`RecommendationEngine` ABC in `ai_recommender.py`) | Mirrored for `JudgeProvider` |
| Alembic migrations | **Implemented** (initial schema) | New migration for WS3 tables |
| `instructor` library | **Missing** | Add to `pyproject.toml` optional group `evaluation` |
| `accelerate` library | **Missing** | Add for WS4 |
| Frontend pages | **12 pages exist**, no `eval-page.tsx` | New page in WS3.6.1 |
| Frontend types | No `eval.ts` | New type file in WS3.6.1 |
| Eval code | **Zero** | Entirely greenfield for WS3 |
| MLX support | N/A | Not needed — PyTorch MPS on all Macs |
| Modal cloud adapter | Stubbed; dispatcher raises | Not used in v4; stays stubbed |

---

## 12. Go/No-Go

**Go.** Spec is architecturally closed. Every major decision has a named rationale. Every risk has a named mitigation. Every step has a verifiable AC. Three backends, one framework. Judge harness has a narrow, defensible scope. Resume claims are phrased to survive honest scrutiny.

**Proceed to implementation.**
