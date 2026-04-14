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
- `tests/test_run_local.py` — unit + integration tests (mock trainer).

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
entry explaining why. `heldout_perplexity` and `judge_pass_rate` are always
null in this runner; they are populated later by the eval (#9) and judge
(#10) paths.

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

Every non-zero exit also writes a stderr line prefixed `[bench]`.

## Running the tests

```bash
python3 -m pytest scripts/bench/tests/ -v
```

The tests use a mock trainer (`tests/fake_trainer.py`) that emits a fixed
JSON event sequence — no GPU or model download required.
