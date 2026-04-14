# Hardware Benchmarks

Cross-hardware LoRA fine-tuning benchmark of a fixed model + dataset + config across Apple Silicon (MPS) and cloud (CUDA) backends. Numbers populate as WS2 runs complete.

## Setup

Locked configuration for all three runs. Model: `Qwen/Qwen2.5-1.5B-Instruct`. Dataset: `HuggingFaceH4/ultrachat_200k`, 2,000-example subset, seed=42. LoRA config: `r=16`, `α=32`, 1 epoch, `seq_len=512`, `batch=4`, `lr=2e-4`. SHA256 of `configs/bench/qwen15b-lora.yaml` is logged in `runs.config_hash` for every run so the same bits produce the same numbers.

## Backends

Three PyTorch backends, same codepath, three devices. **A.** M1 Pro MacBook Pro, `device=mps`. **B.** M4 Pro MacBook Pro, `device=mps`. **C.** RunPod A10 24GB, `device=cuda` with bitsandbytes QLoRA. Cloud spend capped at $20 total across backend C and WS4 FSDP validation.

## System Metrics

| Metric | M1 Pro (MPS) | M4 Pro (MPS) | A10 (CUDA QLoRA) |
|---|---|---|---|
| `tokens_per_sec` | _TBD_ | _TBD_ | _TBD_ |
| `time_to_first_checkpoint_s` | _TBD_ | _TBD_ | _TBD_ |
| `wall_clock_s` | _TBD_ | _TBD_ | _TBD_ |
| `peak_memory_mb` | _TBD_ | _TBD_ | _TBD_ |
| `final_training_loss` | _TBD_ | _TBD_ | _TBD_ |
| `cost_usd` | $0 | $0 | _TBD_ |
| `$/1M_training_tokens` | $0 | $0 | _TBD_ |

Missing metrics are logged as `NULL` with a populated `metric_unavailable_reason` so no value is silently dropped.

## Quality Metrics

Held-out perplexity is the headline number (cheap, standard, apples-to-apples across devices). Judge harness pass rate on a 50-prompt generation set is the sanity check — disjoint from both the calibration labels and the eval split, scored by the WS3 Tier-2 judge on `faithfulness` and `instruction_following` rubrics. Expected outcome is near-equivalent quality across the three backends, which pivots the story to throughput and cost rather than quality.

| Metric | M1 Pro (MPS) | M4 Pro (MPS) | A10 (CUDA QLoRA) |
|---|---|---|---|
| `heldout_perplexity` | _TBD_ | _TBD_ | _TBD_ |
| `judge_pass_rate` (faithfulness) | _TBD_ | _TBD_ | _TBD_ |
| `judge_pass_rate` (instruction-following) | _TBD_ | _TBD_ | _TBD_ |

## Analysis

_Populated after runs complete (target: 200 words). Will identify at least one surprising finding — e.g., throughput ratio vs price ratio, memory ceiling hit on a backend, or a quality gap narrower than expected given cost asymmetry. If quality is statistically indistinguishable across backends, the narrative becomes "choose by throughput and cost" rather than a quality tradeoff._

## Cost Governance

Cloud runs use spot instances with a `max_wall_clock_hours` kill-switch in the trainer. Total cloud spend is tracked and documented here at the end of each run. Spot pricing is confirmed via a RunPod dashboard screenshot committed alongside the final numbers. Hard cap: $20 for WS2 + $10 for WS4 FSDP validation = $30 ceiling across the entire benchmarking + distributed work; run is killed if this would be exceeded.

| Backend | Plan | Actual | Spot verified |
|---|---|---|---|
| A10 (WS2) | ≤ $20 | _TBD_ | _TBD_ |
| 2×L4 (WS4 FSDP) | ≤ $10 | _TBD_ | _TBD_ |

## Distributed Scaling (FSDP)

2×L4 FSDP run on the same locked config, covered by WS4. Populates with FSDP throughput, per-rank peak memory, and wall-clock — compared against the single-GPU A10 baseline to show scaling efficiency. Multi-node, tensor-parallel, and pipeline-parallel are explicitly out of scope for v4 (see `SPEC.md`).

| Metric | A10 (single) | 2×L4 (FSDP) | Scaling factor |
|---|---|---|---|
| `tokens_per_sec` | _TBD_ | _TBD_ | _TBD_ |
| `peak_memory_mb` (per rank) | _TBD_ | _TBD_ | — |
| `wall_clock_s` | _TBD_ | _TBD_ | _TBD_ |
