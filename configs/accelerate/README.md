# Accelerate launch configs

These YAMLs are consumed by `accelerate launch --config_file configs/accelerate/<file>.yaml`.
The backend trainer wraps training with `accelerate.Accelerator(...)` and reads
`mixed_precision` / `gradient_accumulation_steps` from the per-run project YAML,
which override the launch config at runtime.

## Which config to use

- `single_gpu.yaml` — one CUDA or MPS GPU (local dev, unit tests, smoke runs).
- `fsdp_2gpu.yaml` — two-GPU FSDP full-shard (bench target: 2x L4). Pins
  `Qwen2DecoderLayer` as the transformer wrap class; change it to match your
  model family if you switch off Qwen2.
- `deepspeed_zero2_2gpu.yaml` — two-GPU DeepSpeed ZeRO-2, no CPU offload
  (fastest ZeRO tier for models that fit in aggregate GPU memory).

## Usage

```
accelerate launch --config_file configs/accelerate/fsdp_2gpu.yaml <entrypoint>.py ...
```

For a dry-run validation pass without starting training, add `--dry-run` if the
entrypoint supports it.

All three configs set `gradient_checkpointing: true` (SPEC §R-04) so
activation-memory pressure stays bounded by default.
