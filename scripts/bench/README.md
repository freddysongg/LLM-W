# Bench Runner

Unified cross-hardware benchmark for the LLM fine-tuning workbench. Wraps the
existing trainer subprocess headlessly and emits a standardized summary that
downstream tooling (ingestion, leaderboards, #8/#9/#10) can consume.

## Files

- `run_local.sh` — thin bash wrapper, delegates to the Python implementation.
  Kept so the ticket's "script at `scripts/bench/run_local.sh`, executable
  bit set" AC is satisfied.
- `run_local.py` — the real implementation: argparse, YAML patching,
  trainer subprocess launch, stdout JSON stream capture, summary emission.
- `freeze_eval_split.py` — one-shot script that materializes the frozen
  200-example held-out eval split (see "Frozen eval split" below).
- `judge_sanity.py` — post-training step: loads the saved LoRA adapter,
  generates completions on 50 disjoint prompts, scores them with the v1
  rubrics via the Tier-2 G-Eval judge, and mutates `summary.json` to
  populate `judge_pass_rate` (see "Judge sanity" below).
- `tests/test_run_local.py` — unit + integration tests (mock trainer).
- `tests/test_freeze_eval_split.py` — determinism + disjointness tests for
  the freeze script, using a stubbed `datasets.load_dataset`.
- `tests/test_judge_sanity.py` — unit tests for the judge-sanity runner
  (disjointness, idempotency, stub-driven scoring, failure resilience).

## Usage

From the repo root:

```bash
# macOS with Apple Silicon
./scripts/bench/run_local.sh \
  --device mps \
  --config configs/bench/qwen15b-lora.yaml \
  --output-dir runs/bench-mps-$(date -u +%Y%m%dT%H%M%SZ)

# RunPod / Linux + CUDA
BENCH_CUDA_HOURLY_USD=1.19 ./scripts/bench/run_local.sh \
  --device cuda \
  --config configs/bench/qwen15b-lora.yaml \
  --output-dir /workspace/runs/bench-cuda-$(date -u +%Y%m%dT%H%M%SZ)
```

`--config` defaults to `configs/bench/qwen15b-lora.yaml`. `--output-dir` and
`--device` are required.

### Device validation

The runner imports `torch` at startup and checks:

- `--device cuda` requires `torch.cuda.is_available() == True`
- `--device mps`  requires `torch.backends.mps.is_available() == True`
- `--device cpu`  always passes the availability check

Mismatched devices exit non-zero with a `[bench]` stderr message before any
subprocess is spawned.

### Quantization auto-patching

`configs/bench/qwen15b-lora.yaml` ships with `quantization.enabled: true`.
On `--device mps` or `--device cpu` the runner writes a patched copy to
`<output-dir>/patched-config.yaml` with `quantization.enabled: false` and
`execution.device` set to match the requested device. The patched file
includes a banner with the SHA256 of the original so archived runs are
self-documenting.

The `summary.json.config_hash` field is always the SHA256 of the *original*
config bytes — never the patched copy.

## Frozen eval split

`configs/bench/eval_split.jsonl` is a deterministic 200-example held-out eval
slice of `HuggingFaceH4/ultrachat_200k` pinned to dataset revision
`8049631c405ae6576f93f445c6b8166f76f5505a`. Both the JSONL file and its
SHA256 hash (`configs/bench/eval_split.hash`) are committed to the repo.

The slice is carved out of the same shuffled `train_sft` split used for
training (`shuffle(seed=42)`), at indices `[2000, 2200)` — provably disjoint
from the `[0, 2000)` training subset declared in
`configs/bench/qwen15b-lora.yaml`.

### Regenerating the split

Only required if the pinned dataset revision in `freeze_eval_split.py`
changes. The script is idempotent — running it again with the same revision
produces byte-identical outputs.

```bash
pip install "datasets>=2.0.0"
python3 scripts/bench/freeze_eval_split.py
```

The script writes to `configs/bench/eval_split.jsonl` and
`configs/bench/eval_split.hash`. After regenerating, copy the new SHA into
`configs/bench/qwen15b-lora.yaml` under `bench.eval_split_hash:`. The runner
exits with code 11 at startup if the YAML hash and on-disk file disagree.

Pass `--output-dir <path>` to write outside the repo (used by the
determinism tests). Pass `--force` to overwrite drifted on-disk outputs;
without `--force` the script exits non-zero.

### Runner integrity check

`run_local.py` reads `bench.eval_split_hash` from the YAML at startup:

- **Hash matches on-disk file** → proceed normally.
- **Hash mismatches on-disk file** → exit 11 with
  `[bench] eval_split_hash mismatch: YAML=<a> disk=<b>`.
- **Hash declared but file missing** → exit 11 with
  `[bench] eval_split.jsonl missing but bench.eval_split_hash is set`.
- **Hash is `null`** → log a `[bench] warning:` and proceed (escape hatch
  used during the WS2.x bring-up; unreachable now that the hash is
  populated).

## Judge sanity

After a successful training run the runner can optionally invoke
`judge_sanity.py`, which:

1. Loads the 50-prompt disjoint set from `configs/bench/judge_sanity_prompts.jsonl`,
   verifies its SHA256 against `bench.judge_sanity_prompts_hash`, and asserts
   no prompt overlaps the 200-example frozen eval split (and the calibration
   set, if `eval/calibration/v1_raw.hash` exists — otherwise logs a warning).
2. Locates the latest `checkpoint-<step>` under `<output-dir>/project/checkpoints/`
   (or uses `--adapter-path` when passed explicitly), loads the base model
   via `transformers.AutoModelForCausalLM` + applies the adapter via
   `peft.PeftModel.from_pretrained`, and generates at `temperature=0.0`,
   `max_new_tokens=256`.
3. Writes `<output-dir>/judge_sanity_generations.jsonl`. If that file
   already has 50 entries, generation is skipped entirely (idempotent re-run).
4. Scores each `(prompt, output)` against both `rubrics/faithfulness.yaml`
   and `rubrics/instruction_following.yaml` via `GEvalJudge(OpenAIJudge())`.
   `EvaluationCase.reference` is left as `None`: the goal is equivalent-
   quality cross-backend sanity, not perfect rubric semantics, and the
   rubric's few-shot examples still carry references.
5. Mutates `summary.json` atomically: sets `judge_pass_rate` to the mean of
   the per-rubric pass rates, adds a `judge_breakdown` sub-field
   `{faithfulness: <rate>, instruction_following: <rate>}`, and removes the
   deferred-reason entry from `metric_unavailable_reasons`.

Any failure in generation or scoring is caught and recorded in
`metric_unavailable_reasons.judge_pass_rate`; `judge_pass_rate` stays `null`
and the script exits 0. The training run is not considered failed.

### Running from the bench wrapper

Gated behind `--judge-sanity` (default off) so bench CI remains free:

```bash
./scripts/bench/run_local.sh \
  --device mps \
  --config configs/bench/qwen15b-lora.yaml \
  --output-dir runs/bench-mps-$(date -u +%Y%m%dT%H%M%SZ) \
  --judge-sanity
```

### Running standalone against an existing run

```bash
python3 scripts/bench/judge_sanity.py \
  --summary runs/bench-mps-.../summary.json \
  --config  configs/bench/qwen15b-lora.yaml \
  --device  mps
```

Pass `--adapter-path <path>` to override the default (latest checkpoint
under `<output-dir>/project/checkpoints/`).

### Prompt source

The initial `configs/bench/judge_sanity_prompts.jsonl` is a hand-authored
synthetic placeholder (`judge_sanity_prompts_source: synthetic-placeholder-v1`)
covering instruction-following, explanation, and creative styles. Replace
with a sampled slice of a pinned public dataset (e.g. `databricks/dolly-15k`)
before the first real bench run is logged — update the JSONL, the `.hash`
file, the `bench.judge_sanity_prompts_hash`, and the
`bench.judge_sanity_prompts_source` fields together.

## Environment variables

| Variable                 | Required? | Purpose                                                                 |
|--------------------------|-----------|-------------------------------------------------------------------------|
| `BENCH_CUDA_HOURLY_USD`  | Optional  | Hourly USD rate used to compute `cost_usd` on `--device cuda`. Defaults to `0.0` with a stderr warning (keeps CI green). |
| `BENCH_TRAINER_CMD`      | Optional  | Override the trainer command — used by the mock-trainer tests. Comma/space-separated tokens prepended ahead of the standard trainer args. Do not set in production. |

## Output layout

```
<output-dir>/
├── patched-config.yaml     # device-adjusted config passed to trainer
├── metrics.jsonl           # raw trainer stdout events, one JSON object per line
├── summary.json            # standardized 8-metric summary + provenance
├── trainer.stderr.log      # only written if trainer printed to stderr
└── project/                # trainer's project dir (checkpoints, artifacts, heartbeat)
```

### `summary.json` schema

```json
{
  "tokens_per_sec": 0.0,
  "time_to_first_checkpoint_s": 0.0,
  "wall_clock_s": 0.0,
  "peak_memory_mb": null,
  "final_training_loss": 0.0,
  "heldout_perplexity": null,
  "cost_usd": 0.0,
  "judge_pass_rate": null,
  "run_id": "bench-mps-20260413T120000Z",
  "device": "mps",
  "config_hash": "sha256-of-original-yaml",
  "eval_split_hash": null,
  "started_at": "2026-04-13T12:00:00+00:00",
  "completed_at": "2026-04-13T12:30:00+00:00",
  "metric_unavailable_reasons": {
    "heldout_perplexity": "deferred to post-train eval",
    "judge_pass_rate": "deferred to judge-harness runner"
  }
}
```

`null` metric values always come paired with a `metric_unavailable_reasons`
entry explaining why. `heldout_perplexity` is populated later by the eval
(#9) path. `judge_pass_rate` is populated in-place by the post-training
judge-sanity step (see "Judge sanity" below) when `--judge-sanity` is passed;
in that case a `judge_breakdown` sub-field is added with per-rubric pass
rates.

### Peak-memory derivation

The runner scans every `{"type":"metric"}` event's `metrics` dict for the
first key matching `memory_mb`, `peak_memory_mb`, or `memory_allocated_mb`
and tracks the maximum value seen. The current trainer (as of this commit)
does not actively emit any of these keys — it forwards whatever HuggingFace
Trainer's log dict contains, which is typically `loss`, `learning_rate`,
`train_runtime`, `train_samples_per_second`, `grad_norm`. Until the trainer
is extended to emit memory (a separate ticket), `peak_memory_mb` will be
`null` with reason `"trainer metric events did not include a memory key"`.

### `tokens_per_sec` derivation

Preferred: `train_samples_per_second × preprocessing.max_seq_length` from
the final metric event. Fallback: `steps × batch × grad_accum × seq_len /
train_runtime`. If neither is available, `tokens_per_sec` is `null`.

## Exit codes

| Code | Meaning                                                          |
|------|------------------------------------------------------------------|
| 0    | Trainer completed successfully, summary fully written.           |
| 2    | Config missing or unparseable.                                   |
| 3    | Requested device unavailable (or torch not importable).          |
| 4    | Config failed pre-flight Pydantic validation.                    |
| 5    | `backend/` directory not found relative to repo root.            |
| 6    | Could not spawn trainer subprocess.                              |
| 7    | Trainer subprocess had no stdout pipe (should be impossible).    |
| 8    | Failed to write `summary.json`.                                  |
| 9    | Trainer exited non-zero; partial summary written.                |
| 10   | Trainer never emitted a terminal `complete` event.               |
| 11   | `bench.eval_split_hash` mismatched on-disk `eval_split.jsonl`.   |

Every non-zero exit also writes a stderr line prefixed `[bench]`.

## Running the tests

```bash
python3 -m pytest scripts/bench/tests/ -v
```

The tests use a mock trainer (`tests/fake_trainer.py`) that emits a fixed
JSON event sequence — no GPU or model download required.
