"""Trainer script — runs in a subprocess spawned by orchestrator.py.

Communicates via JSON lines on stdout. All events are flushed immediately.
The orchestrator reads stdout and updates SQLite + event bus.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import shutil
import signal
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from transformers import TrainerCallback

logger = logging.getLogger(__name__)

# Stage definitions matching spec section 19.1
RUN_STAGES: list[tuple[int, str]] = [
    (1, "config_validation"),
    (2, "environment_validation"),
    (3, "model_resolution"),
    (4, "dataset_resolution"),
    (5, "dataset_profiling"),
    (6, "tokenization_preprocessing"),
    (7, "training_preparation"),
    (8, "adapter_attachment"),
    (9, "training_start"),
    (10, "training_progress"),
    (11, "evaluation"),
    (12, "checkpoint_save"),
    (13, "artifact_finalization"),
    (14, "completion"),
]

_CANCEL_REQUESTED = threading.Event()
_PAUSE_REQUESTED = threading.Event()

# Candidate field names tried in order when the configured name is missing
_INPUT_FIELD_CANDIDATES: list[str] = [
    "text",
    "prompt",
    "instruction",
    "input",
    "query",
    "question",
    "content",
    "context",
]
_TARGET_FIELD_CANDIDATES: list[str] = [
    "response",
    "output",
    "answer",
    "target",
    "completion",
    "label",
]


def _resolve_dataset_field(
    *,
    configured: str,
    candidates: list[str],
    available: list[str],
    field_label: str,
    stage_name: str,
) -> str:
    """Return configured field if present, otherwise auto-detect from candidates."""
    if configured in available:
        return configured
    for candidate in candidates:
        if candidate in available:
            _emit_log(
                severity="warning",
                message=(
                    f"{field_label} '{configured}' not found in columns {available}; "
                    f"auto-detected '{candidate}'"
                ),
                stage=stage_name,
            )
            return candidate
    return configured


def _emit(event: dict[str, Any]) -> None:
    event.setdefault("timestamp", datetime.now(UTC).isoformat())
    print(json.dumps(event), flush=True)


def _emit_log(*, severity: str, message: str, stage: str) -> None:
    _emit({"type": "log", "severity": severity, "message": message, "stage": stage})


def _emit_stage_enter(*, stage_name: str, stage_order: int) -> None:
    _emit({"type": "stage_enter", "stage_name": stage_name, "stage_order": stage_order})


def _emit_stage_complete(*, stage_name: str, duration_ms: int, output_summary: str) -> None:
    _emit(
        {
            "type": "stage_complete",
            "stage_name": stage_name,
            "duration_ms": duration_ms,
            "output_summary": output_summary,
        }
    )


def _emit_stage_fail(*, stage_name: str, error: str) -> None:
    _emit({"type": "stage_fail", "stage_name": stage_name, "error": error})


def _emit_progress(
    *, current_step: int, total_steps: int, progress_pct: float, epoch: float
) -> None:
    _emit(
        {
            "type": "progress",
            "current_step": current_step,
            "total_steps": total_steps,
            "progress_pct": progress_pct,
            "epoch": epoch,
        }
    )


def _emit_metric(*, step: int, epoch: float, metrics: dict[str, float]) -> None:
    _emit({"type": "metric", "step": step, "epoch": epoch, "metrics": metrics})


def _emit_checkpoint(*, step: int, path: str, size_bytes: int) -> None:
    _emit({"type": "checkpoint", "step": step, "path": path, "size_bytes": size_bytes})


def _emit_complete(*, status: str, final_metrics: dict[str, float]) -> None:
    _emit({"type": "complete", "status": status, "final_metrics": final_metrics})


def _emit_error(*, stage: str, message: str) -> None:
    _emit({"type": "error", "stage": stage, "message": message})


def _write_heartbeat(
    *,
    heartbeat_path: Path,
    run_id: str,
    current_step: int,
    total_steps: int,
    stage: str,
    metrics: dict[str, float],
) -> None:
    payload = {
        "run_id": run_id,
        "pid": os.getpid(),
        "current_step": current_step,
        "total_steps": total_steps,
        "timestamp": datetime.now(UTC).isoformat(),
        "stage": stage,
        "metrics": metrics,
    }
    tmp = heartbeat_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.rename(heartbeat_path)


def _start_heartbeat_thread(
    *,
    heartbeat_path: Path,
    run_id: str,
    interval_seconds: int,
    state: dict[str, Any],
) -> threading.Thread:
    def _loop() -> None:
        while not state.get("done"):
            with contextlib.suppress(OSError):
                _write_heartbeat(
                    heartbeat_path=heartbeat_path,
                    run_id=run_id,
                    current_step=state.get("current_step", 0),
                    total_steps=state.get("total_steps", 0),
                    stage=state.get("stage", ""),
                    metrics=state.get("metrics", {}),
                )
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread


def _atomic_checkpoint_write(*, trainer: Any, step: int, project_dir: Path) -> str:
    """Write checkpoint atomically: tmp dir → rename."""
    import sys

    checkpoints_dir = project_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    tmp_dir = checkpoints_dir / f".tmp-checkpoint-{step}"
    final_dir = checkpoints_dir / f"checkpoint-{step}"

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

    trainer.save_model(str(tmp_dir))

    if sys.platform == "win32":
        # Path.rename raises FileExistsError on Windows if target exists
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.move(str(tmp_dir), str(final_dir))
    else:
        tmp_dir.rename(final_dir)
    return str(final_dir)


def _get_dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _run_checkpoints_dir(*, project_dir: Path, run_id: str) -> Path:
    # Per-run isolation so concurrent/prior runs never clobber each other's artifacts
    return project_dir / "runs" / run_id / "checkpoints"


def _sample_gpu_memory_mb() -> float | None:
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        return None
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024 * 1024)
        if torch.backends.mps.is_available():
            return torch.mps.current_allocated_memory() / (1024 * 1024)
    except Exception:
        return None
    return None


class WorkbenchCallback(TrainerCallback):
    """HuggingFace TrainerCallback that emits structured events to stdout."""

    def __init__(
        self,
        *,
        run_id: str,
        project_dir: Path,
        heartbeat_state: dict[str, Any],
    ) -> None:
        self._run_id = run_id
        self._project_dir = project_dir
        self._heartbeat_state = heartbeat_state
        self._last_metrics: dict[str, float] = {}
        self._last_log_time: float | None = None
        self._last_num_tokens: float | None = None

    def on_train_begin(self, args: Any, state: Any, control: Any, **kwargs: Any) -> None:
        _emit_stage_complete(
            stage_name="training_start",
            duration_ms=0,
            output_summary="trainer initialized",
        )
        _emit_stage_enter(stage_name="training_progress", stage_order=10)
        total_steps = state.max_steps if state.max_steps > 0 else 0
        self._heartbeat_state["stage"] = "training_progress"
        self._heartbeat_state["total_steps"] = total_steps
        _emit_progress(
            current_step=0,
            total_steps=total_steps,
            progress_pct=0.0,
            epoch=0.0,
        )

    def on_step_end(self, args: Any, state: Any, control: Any, **kwargs: Any) -> None:
        step = state.global_step
        total_steps = state.max_steps if state.max_steps > 0 else 1
        epoch = float(state.epoch or 0.0)
        progress_pct = min(100.0, step / total_steps * 100)
        _emit_progress(
            current_step=step,
            total_steps=total_steps,
            progress_pct=progress_pct,
            epoch=epoch,
        )
        self._heartbeat_state["current_step"] = step
        self._heartbeat_state["total_steps"] = total_steps

    def on_log(
        self, args: Any, state: Any, control: Any, logs: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        if not logs:
            return
        step = state.global_step
        epoch = float(state.epoch or 0.0)
        metrics: dict[str, float] = {}
        for key, value in logs.items():
            if isinstance(value, (int, float)):
                metrics[key] = float(value)

        # Normalize HF's "loss" to the domain name "train_loss" so downstream
        # consumers (rule engine, charts) have a single canonical key.
        if "loss" in metrics:
            metrics["train_loss"] = metrics.pop("loss")

        now = time.monotonic()
        num_tokens = metrics.get("num_tokens")
        if (
            num_tokens is not None
            and self._last_log_time is not None
            and self._last_num_tokens is not None
        ):
            elapsed = now - self._last_log_time
            delta_tokens = num_tokens - self._last_num_tokens
            if elapsed > 0 and delta_tokens >= 0:
                metrics["tokens_per_second"] = delta_tokens / elapsed
        if num_tokens is not None:
            self._last_num_tokens = num_tokens
        self._last_log_time = now

        gpu_memory_mb = _sample_gpu_memory_mb()
        if gpu_memory_mb is not None:
            metrics["gpu_memory_used_mb"] = gpu_memory_mb

        total_steps = state.max_steps if state.max_steps > 0 else 1

        progress_pct = min(100.0, step / total_steps * 100)
        if metrics:
            _emit_metric(step=step, epoch=epoch, metrics=metrics)
            self._last_metrics = metrics
            self._heartbeat_state["current_step"] = step
            self._heartbeat_state["total_steps"] = total_steps
            self._heartbeat_state["metrics"] = metrics
            loss = metrics.get("train_loss")
            lr = metrics.get("learning_rate")
            stats_parts = []
            if loss is not None:
                stats_parts.append(f"loss: {loss:.4f}")
            if lr is not None:
                stats_parts.append(f"lr: {lr:.2e}")
            stats = ", ".join(stats_parts) if stats_parts else ""
            log_msg = f"Step {step}/{total_steps} ({progress_pct:.1f}%)"
            if stats:
                log_msg = f"{log_msg} — {stats}"
            _emit_log(severity="info", message=log_msg, stage="training_progress")
        _emit_progress(
            current_step=step,
            total_steps=total_steps,
            progress_pct=progress_pct,
            epoch=epoch,
        )

    def on_evaluate(
        self,
        args: Any,
        state: Any,
        control: Any,
        metrics: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        _emit_stage_enter(stage_name="evaluation", stage_order=11)
        if metrics:
            step = state.global_step
            epoch = float(state.epoch or 0.0)
            eval_metrics = {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}
            _emit_metric(step=step, epoch=epoch, metrics=eval_metrics)
        _emit_stage_complete(
            stage_name="evaluation",
            duration_ms=0,
            output_summary=f"eval at step {state.global_step}",
        )

    def on_save(self, args: Any, state: Any, control: Any, **kwargs: Any) -> None:
        step = state.global_step
        checkpoint_dir = (
            _run_checkpoints_dir(project_dir=self._project_dir, run_id=self._run_id)
            / f"checkpoint-{step}"
        )
        if checkpoint_dir.exists():
            size = _get_dir_size(checkpoint_dir)
            _emit_checkpoint(step=step, path=str(checkpoint_dir), size_bytes=size)

    def on_train_end(self, args: Any, state: Any, control: Any, **kwargs: Any) -> None:
        self._heartbeat_state["stage"] = "artifact_finalization"


def _camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _normalize_config_keys(obj: Any) -> Any:
    """Recursively convert camelCase dict keys to snake_case.

    The frontend TypeScript types use camelCase (modelId, batchSize) but the
    backend WorkbenchConfig Pydantic models and the trainer both expect
    snake_case. This normalizes any YAML saved with camelCase keys.
    """
    if isinstance(obj, dict):
        return {_camel_to_snake(k): _normalize_config_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_config_keys(item) for item in obj]
    return obj


def _stage_config_validation(*, config_path: Path) -> dict[str, Any]:
    import yaml

    stage_name = "config_validation"
    _emit_stage_enter(stage_name=stage_name, stage_order=1)
    t0 = time.monotonic()

    try:
        raw = yaml.safe_load(config_path.read_text())
    except Exception as exc:
        _emit_stage_fail(stage_name=stage_name, error=f"YAML parse error: {exc}")
        raise

    raw = _normalize_config_keys(raw)

    try:
        # import inline to avoid mandatory top-level dep when running standalone
        from app.schemas.workbench_config import WorkbenchConfig  # noqa: PLC0415

        WorkbenchConfig.model_validate(raw)
    except Exception as exc:
        _emit_stage_fail(stage_name=stage_name, error=f"Config validation failed: {exc}")
        raise

    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary="Config valid",
    )
    return raw


def _stage_environment_validation(*, raw_config: dict[str, Any]) -> str:
    import platform

    stage_name = "environment_validation"
    _emit_stage_enter(stage_name=stage_name, stage_order=2)
    t0 = time.monotonic()

    try:
        import torch  # noqa: PLC0415

        device_str = raw_config.get("execution", {}).get("device", "auto")
        if device_str == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        else:
            device = device_str

        _emit_log(
            severity="info",
            message=(
                f"Device: {device}, Python: {platform.python_version()}, Torch: {torch.__version__}"
            ),
            stage=stage_name,
        )
    except ImportError:
        device = "cpu"
        _emit_log(severity="warning", message="torch not installed, using cpu", stage=stage_name)

    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary=f"device={device}",
    )
    return device


def _is_bitsandbytes_available() -> bool:
    try:
        import bitsandbytes  # noqa: PLC0415, F401

        return True
    except ImportError:
        return False


def _stage_model_resolution(*, raw_config: dict[str, Any], device: str) -> Any:
    stage_name = "model_resolution"
    _emit_stage_enter(stage_name=stage_name, stage_order=3)
    t0 = time.monotonic()

    model_cfg = raw_config.get("model", {})
    model_id = model_cfg.get("model_id", "")
    torch_dtype_str = model_cfg.get("torch_dtype", "auto")
    trust_remote_code = bool(model_cfg.get("trust_remote_code", False))

    quant_cfg = raw_config.get("quantization", {})
    is_quantization_enabled = bool(quant_cfg.get("enabled", False))

    adapters_cfg = raw_config.get("adapters", {})
    is_qlora = adapters_cfg.get("enabled", True) and adapters_cfg.get("type", "lora") == "qlora"

    needs_bitsandbytes = is_quantization_enabled or is_qlora
    if needs_bitsandbytes and not _is_bitsandbytes_available():
        error_msg = (
            "bitsandbytes is required for QLoRA/quantization but is not installed. "
            "Install it with: pip install bitsandbytes>=0.43.0 "
            "(note: bitsandbytes has limited Windows support — use LoRA instead on Windows)"
        )
        _emit_stage_fail(stage_name=stage_name, error=error_msg)
        raise RuntimeError(error_msg)

    _emit_log(severity="info", message=f"Loading model: {model_id}", stage=stage_name)

    try:
        import torch  # noqa: PLC0415
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        torch_dtype = dtype_map.get(torch_dtype_str, "auto")

        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=trust_remote_code)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        load_kwargs: dict[str, Any] = {
            "trust_remote_code": trust_remote_code,
            "torch_dtype": torch_dtype,
        }

        if needs_bitsandbytes:
            from transformers import BitsAndBytesConfig  # noqa: PLC0415

            quant_mode = quant_cfg.get("mode", "4bit")
            compute_dtype_str = quant_cfg.get("compute_dtype", "bfloat16")
            compute_dtype = dtype_map.get(compute_dtype_str, torch.bfloat16)

            if quant_mode == "4bit":
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=compute_dtype,
                    bnb_4bit_quant_type=quant_cfg.get("quant_type", "nf4"),
                    bnb_4bit_use_double_quant=bool(quant_cfg.get("double_quant", True)),
                )
            else:
                load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)

            _emit_log(
                severity="info",
                message=f"Applying {quant_mode} quantization via bitsandbytes",
                stage=stage_name,
            )

        model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs)
        if not needs_bitsandbytes:
            model.to(device)
    except Exception as exc:
        _emit_stage_fail(stage_name=stage_name, error=str(exc))
        raise

    param_count = sum(p.numel() for p in model.parameters())
    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary=f"params={param_count:,}",
    )
    return model, tokenizer


def _stage_dataset_resolution(*, raw_config: dict[str, Any], tokenizer: Any) -> Any:
    stage_name = "dataset_resolution"
    _emit_stage_enter(stage_name=stage_name, stage_order=4)
    t0 = time.monotonic()

    dataset_cfg = raw_config.get("dataset", {})
    source = dataset_cfg.get("source", "huggingface")
    dataset_id = dataset_cfg.get("dataset_id", "")
    train_split = dataset_cfg.get("train_split", "train")
    max_samples = dataset_cfg.get("max_samples")

    if not dataset_id or not dataset_id.strip():
        error_msg = (
            "dataset_id is empty — configure a dataset on the Datasets page before starting a run"
        )
        _emit_stage_fail(stage_name=stage_name, error=error_msg)
        raise ValueError(error_msg)

    try:
        from datasets import load_dataset  # noqa: PLC0415

        _emit_log(severity="info", message=f"Loading dataset: {dataset_id}", stage=stage_name)
        if source == "huggingface":
            subset = dataset_cfg.get("subset")
            raw_ds = load_dataset(dataset_id, subset, trust_remote_code=False)
        elif source in ("local_jsonl", "local_csv"):
            fmt = "json" if source == "local_jsonl" else "csv"
            raw_ds = load_dataset(fmt, data_files={"train": dataset_id})
        else:
            raw_ds = load_dataset("json", data_files={"train": dataset_id})

        train_dataset = raw_ds[train_split]
        if max_samples is not None:
            train_dataset = train_dataset.select(range(min(max_samples, len(train_dataset))))

        eval_dataset = None
        eval_split = dataset_cfg.get("eval_split")
        if eval_split and eval_split in raw_ds:
            eval_dataset = raw_ds[eval_split]
            if max_samples is not None:
                eval_dataset = eval_dataset.select(
                    range(min(max_samples // 10 or 1, len(eval_dataset)))
                )

        _emit_log(
            severity="info",
            message=f"Dataset loaded: {len(train_dataset)} train rows",
            stage=stage_name,
        )
    except Exception as exc:
        _emit_stage_fail(stage_name=stage_name, error=str(exc))
        raise

    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary=f"train_rows={len(train_dataset)}",
    )
    return train_dataset, eval_dataset


def _stage_dataset_profiling(*, train_dataset: Any, raw_config: dict[str, Any]) -> None:
    stage_name = "dataset_profiling"
    _emit_stage_enter(stage_name=stage_name, stage_order=5)
    t0 = time.monotonic()

    row_count = len(train_dataset)
    input_field = raw_config.get("dataset", {}).get("input_field", "prompt")

    sample_count = min(100, row_count)
    lengths = []
    for i in range(sample_count):
        row = train_dataset[i]
        text = str(row.get(input_field, ""))
        lengths.append(len(text.split()))

    avg_len = sum(lengths) / len(lengths) if lengths else 0
    _emit_log(
        severity="info",
        message=f"Dataset: {row_count} rows, avg token est: {avg_len:.0f}",
        stage=stage_name,
    )

    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary=f"rows={row_count}, avg_word_len={avg_len:.0f}",
    )


def _stage_tokenization_preprocessing(
    *,
    train_dataset: Any,
    eval_dataset: Any | None,
    tokenizer: Any,
    raw_config: dict[str, Any],
) -> tuple[Any, Any | None]:
    stage_name = "tokenization_preprocessing"
    _emit_stage_enter(stage_name=stage_name, stage_order=6)
    t0 = time.monotonic()

    preprocessing_cfg = raw_config.get("preprocessing", {})
    max_seq_length = preprocessing_cfg.get("max_seq_length", 512)
    dataset_cfg = raw_config.get("dataset", {})
    input_field = dataset_cfg.get("input_field", "prompt")
    target_field = dataset_cfg.get("target_field", "response")

    available_columns: list[str] = list(train_dataset.column_names)
    input_field = _resolve_dataset_field(
        configured=input_field,
        candidates=_INPUT_FIELD_CANDIDATES,
        available=available_columns,
        field_label="input_field",
        stage_name=stage_name,
    )
    target_field = _resolve_dataset_field(
        configured=target_field,
        candidates=_TARGET_FIELD_CANDIDATES,
        available=available_columns,
        field_label="target_field",
        stage_name=stage_name,
    )

    if input_field not in available_columns:
        error_msg = (
            f"input_field not found in dataset columns {available_columns}. "
            f"Update the Datasets page to set the correct input field name."
        )
        _emit_stage_fail(stage_name=stage_name, error=error_msg)
        raise ValueError(error_msg)

    _emit_log(
        severity="info",
        message=f"Tokenizing dataset ({len(train_dataset)} rows, max_seq_length={max_seq_length})",
        stage=stage_name,
    )

    def _tokenize(batch: dict[str, list[Any]]) -> dict[str, list[Any]]:
        inputs = batch.get(input_field, [])
        targets = batch.get(target_field, inputs)
        texts = [f"{inp}{tgt}" for inp, tgt in zip(inputs, targets, strict=False)]
        return tokenizer(
            texts,
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )

    train_tokenized = train_dataset.map(_tokenize, batched=True)
    eval_tokenized = eval_dataset.map(_tokenize, batched=True) if eval_dataset else None

    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary=f"max_seq_length={max_seq_length}",
    )
    return train_tokenized, eval_tokenized


def _stage_training_preparation(
    *,
    model: Any,
    tokenizer: Any,
    train_dataset: Any,
    eval_dataset: Any | None,
    raw_config: dict[str, Any],
    project_dir: Path,
    resume_from_checkpoint: str | None,
    run_id: str,
    heartbeat_state: dict[str, Any],
    device: str,
) -> Any:
    stage_name = "training_preparation"
    _emit_stage_enter(stage_name=stage_name, stage_order=7)
    t0 = time.monotonic()

    training_cfg = raw_config.get("training", {})
    optimization_cfg = raw_config.get("optimization", {})

    checkpoints_dir = _run_checkpoints_dir(project_dir=project_dir, run_id=run_id)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    mixed_precision: str = optimization_cfg.get("mixed_precision", "no")
    if mixed_precision == "bf16" and device == "mps":
        # bf16 has unreliable hardware support on MPS; fp16 is the correct fallback
        _emit_log(
            severity="info",
            message="bf16 not supported on MPS, using fp16",
            stage=stage_name,
        )
        mixed_precision = "fp16"
    elif mixed_precision in ("bf16", "fp16") and device == "cpu":
        _emit_log(
            severity="warning",
            message=(
                f"{mixed_precision} requested but no GPU available"
                f" (device={device}), falling back to no mixed precision"
            ),
            stage=stage_name,
        )
        mixed_precision = "no"

    is_cpu = device == "cpu"

    epochs: int = training_cfg.get("epochs", 2)
    batch_size: int = training_cfg.get("batch_size", 4)
    grad_accum: int = training_cfg.get("gradient_accumulation_steps", 4)
    configured_warmup_steps: int = optimization_cfg.get("warmup_steps", 0)
    warmup_ratio: float = optimization_cfg.get("warmup_ratio", 0.03)
    steps_per_epoch = max(1, len(train_dataset) // (batch_size * grad_accum))
    total_steps = steps_per_epoch * epochs
    dynamic_interval = max(1, total_steps // 10)
    if configured_warmup_steps > 0:
        warmup_steps = configured_warmup_steps
    else:
        # Compute warmup_steps from ratio since TRL ≥5.2 deprecated warmup_ratio
        warmup_steps = round(total_steps * warmup_ratio)

    configured_eval_steps: int | None = training_cfg.get("eval_steps")
    configured_save_steps: int | None = training_cfg.get("save_steps")
    configured_logging_steps: int | None = training_cfg.get("logging_steps")
    eval_steps = configured_eval_steps if configured_eval_steps is not None else dynamic_interval
    logging_steps = (
        configured_logging_steps if configured_logging_steps is not None else dynamic_interval
    )
    if configured_save_steps is None:
        save_steps = dynamic_interval
    elif total_steps > 0 and configured_save_steps > total_steps:
        # Prevent silently disabling mid-training saves when the configured
        # cadence is larger than the run's entire length (common on small runs)
        save_steps = dynamic_interval
        _emit_log(
            severity="warning",
            message=(
                f"save_steps={configured_save_steps} exceeds total_steps={total_steps}; "
                f"clamped to {save_steps} so intermediate checkpoints are saved"
            ),
            stage=stage_name,
        )
    else:
        save_steps = configured_save_steps

    try:
        from trl import SFTConfig, SFTTrainer  # noqa: PLC0415

        _emit_log(severity="info", message="Preparing SFTConfig...", stage=stage_name)
        sft_config = SFTConfig(
            output_dir=str(checkpoints_dir),
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=grad_accum,
            learning_rate=training_cfg.get("learning_rate", 2e-4),
            weight_decay=training_cfg.get("weight_decay", 0.01),
            max_grad_norm=training_cfg.get("max_grad_norm", 1.0),
            eval_steps=eval_steps,
            save_steps=save_steps,
            logging_steps=logging_steps,
            seed=training_cfg.get("seed", 42),
            warmup_steps=warmup_steps,
            lr_scheduler_type=optimization_cfg.get("scheduler", "cosine"),
            gradient_checkpointing=optimization_cfg.get("gradient_checkpointing", True),
            fp16=mixed_precision == "fp16",
            bf16=mixed_precision == "bf16",
            use_cpu=is_cpu,
            report_to="none",
            resume_from_checkpoint=resume_from_checkpoint,
            max_length=raw_config.get("preprocessing", {}).get("max_seq_length", 512),
        )

        callback = WorkbenchCallback(
            run_id=run_id,
            project_dir=project_dir,
            heartbeat_state=heartbeat_state,
        )

        _emit_log(severity="info", message="Initializing SFTTrainer...", stage=stage_name)
        trainer = SFTTrainer(
            model=model,
            args=sft_config,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            processing_class=tokenizer,
            callbacks=[callback],
        )
    except Exception as exc:
        _emit_stage_fail(stage_name=stage_name, error=str(exc))
        raise

    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary="SFTTrainer configured",
    )
    return trainer


def _stage_adapter_attachment(*, model: Any, raw_config: dict[str, Any]) -> Any:
    stage_name = "adapter_attachment"
    _emit_stage_enter(stage_name=stage_name, stage_order=8)
    t0 = time.monotonic()

    adapters_cfg = raw_config.get("adapters", {})
    if not adapters_cfg.get("enabled", True):
        _emit_log(
            severity="info", message="Adapters disabled, training full model", stage=stage_name
        )
        _emit_stage_complete(
            stage_name=stage_name, duration_ms=0, output_summary="adapters disabled"
        )
        return model

    adapter_type = adapters_cfg.get("type", "lora")

    try:
        from peft import LoraConfig, TaskType, get_peft_model  # noqa: PLC0415

        if adapter_type == "qlora":
            from peft import prepare_model_for_kbit_training  # noqa: PLC0415

            model = prepare_model_for_kbit_training(model)
            _emit_log(
                severity="info",
                message="Model prepared for k-bit (QLoRA) training",
                stage=stage_name,
            )

        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=adapters_cfg.get("rank", 8),
            lora_alpha=adapters_cfg.get("alpha", 16),
            lora_dropout=adapters_cfg.get("dropout", 0.05),
            target_modules=adapters_cfg.get("target_modules", ["q_proj", "v_proj"]),
        )
        model = get_peft_model(model, lora_config)
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
        adapter_label = "QLoRA" if adapter_type == "qlora" else "LoRA"
        _emit_log(
            severity="info",
            message=(
                f"{adapter_label} attached: {trainable:,}/{total:,} trainable params "
                f"({100 * trainable / total:.2f}%)"
            ),
            stage=stage_name,
        )
    except ImportError:
        _emit_log(
            severity="warning",
            message="peft not installed, skipping adapter attachment",
            stage=stage_name,
        )
    except Exception as exc:
        _emit_stage_fail(stage_name=stage_name, error=str(exc))
        raise

    duration_ms = int((time.monotonic() - t0) * 1000)
    adapter_label = "QLoRA" if adapter_type == "qlora" else "LoRA"
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary=f"{adapter_label} adapters attached",
    )
    return model


def _stage_artifact_finalization(*, trainer: Any, project_dir: Path) -> None:
    stage_name = "artifact_finalization"
    _emit_stage_enter(stage_name=stage_name, stage_order=13)
    t0 = time.monotonic()

    artifacts_dir = project_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    try:
        final_model_dir = artifacts_dir / "final_model"
        trainer.save_model(str(final_model_dir))
        size = _get_dir_size(final_model_dir)
        _emit(
            {
                "type": "artifact",
                "artifact_type": "final_model",
                "path": str(final_model_dir),
                "size_bytes": size,
            }
        )
    except Exception as exc:
        _emit_log(
            severity="warning",
            message=f"Could not save final model: {exc}",
            stage=stage_name,
        )

    duration_ms = int((time.monotonic() - t0) * 1000)
    _emit_stage_complete(
        stage_name=stage_name,
        duration_ms=duration_ms,
        output_summary="artifacts saved",
    )


_IS_UNIX = sys.platform != "win32"


def _handle_sigterm(signum: int, frame: Any) -> None:
    _CANCEL_REQUESTED.set()


def _poll_cancel_flag(cancel_flag_path: Path, stop_event: threading.Event) -> None:
    """Poll a flag file and set _CANCEL_REQUESTED when it appears (Windows only)."""
    while not stop_event.is_set():
        if cancel_flag_path.exists():
            _CANCEL_REQUESTED.set()
            return
        stop_event.wait(timeout=1.0)


def main() -> int:
    if _IS_UNIX:
        signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    parser = argparse.ArgumentParser(description="Workbench trainer subprocess")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config-path", required=True, type=Path)
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--resume-from-checkpoint", default=None)
    parser.add_argument("--heartbeat-interval", type=int, default=10)
    parser.add_argument("--cancel-flag-path", type=Path, default=None)
    args = parser.parse_args()

    run_id: str = args.run_id
    config_path: Path = args.config_path
    project_dir: Path = args.project_dir
    resume_from_checkpoint: str | None = args.resume_from_checkpoint
    heartbeat_interval: int = args.heartbeat_interval
    cancel_flag_path: Path | None = args.cancel_flag_path

    cancel_poll_stop = threading.Event()
    if not _IS_UNIX and cancel_flag_path is not None:
        cancel_poll_thread = threading.Thread(
            target=_poll_cancel_flag,
            args=(cancel_flag_path, cancel_poll_stop),
            daemon=True,
        )
        cancel_poll_thread.start()

    heartbeat_path = project_dir / ".heartbeat"
    heartbeat_state: dict[str, Any] = {
        "current_step": 0,
        "total_steps": 0,
        "stage": "config_validation",
        "metrics": {},
        "done": False,
    }

    heartbeat_thread = _start_heartbeat_thread(
        heartbeat_path=heartbeat_path,
        run_id=run_id,
        interval_seconds=heartbeat_interval,
        state=heartbeat_state,
    )

    final_metrics: dict[str, float] = {}

    try:
        raw_config = _stage_config_validation(config_path=config_path)
        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        heartbeat_state["stage"] = "environment_validation"
        device = _stage_environment_validation(raw_config=raw_config)
        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        heartbeat_state["stage"] = "model_resolution"
        model, tokenizer = _stage_model_resolution(raw_config=raw_config, device=device)
        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        heartbeat_state["stage"] = "adapter_attachment"
        model = _stage_adapter_attachment(model=model, raw_config=raw_config)
        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        heartbeat_state["stage"] = "dataset_resolution"
        train_dataset, eval_dataset = _stage_dataset_resolution(
            raw_config=raw_config, tokenizer=tokenizer
        )
        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        heartbeat_state["stage"] = "dataset_profiling"
        _stage_dataset_profiling(train_dataset=train_dataset, raw_config=raw_config)
        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        heartbeat_state["stage"] = "tokenization_preprocessing"
        train_dataset, eval_dataset = _stage_tokenization_preprocessing(
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=tokenizer,
            raw_config=raw_config,
        )
        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        heartbeat_state["stage"] = "training_preparation"
        trainer = _stage_training_preparation(
            model=model,
            tokenizer=tokenizer,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            raw_config=raw_config,
            project_dir=project_dir,
            resume_from_checkpoint=resume_from_checkpoint,
            run_id=run_id,
            heartbeat_state=heartbeat_state,
            device=device,
        )
        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        _emit_stage_enter(stage_name="training_start", stage_order=9)
        heartbeat_state["stage"] = "training_start"

        trainer.train(resume_from_checkpoint=resume_from_checkpoint)

        if _CANCEL_REQUESTED.is_set():
            _emit_complete(status="cancelled", final_metrics=final_metrics)
            return 0

        if trainer.state.log_history:
            last_log = trainer.state.log_history[-1]
            final_metrics = {
                k: float(v) for k, v in last_log.items() if isinstance(v, (int, float))
            }

        # Stage 11 is a reserved no-op placeholder in v4: eval runs manually
        # via the UI button or `llmw eval` CLI, never inline at training
        # completion. The emission keeps the 14-stage timeline contract honest.
        _emit_stage_enter(stage_name="evaluation", stage_order=11)
        _emit_stage_complete(
            stage_name="evaluation",
            duration_ms=0,
            output_summary="reserved no-op; v4 eval runs manually via UI or CLI",
        )

        heartbeat_state["stage"] = "artifact_finalization"
        _stage_artifact_finalization(trainer=trainer, project_dir=project_dir)

        _emit_stage_enter(stage_name="completion", stage_order=14)
        _emit_stage_complete(
            stage_name="completion",
            duration_ms=0,
            output_summary="training complete",
        )
        _emit_complete(status="completed", final_metrics=final_metrics)
        return 0

    except Exception as exc:
        current_stage = heartbeat_state.get("stage", "unknown")
        error_msg = f"{exc}\n{traceback.format_exc()}"
        _emit_error(stage=current_stage, message=error_msg)
        _emit_complete(status="failed", final_metrics=final_metrics)
        return 1

    finally:
        heartbeat_state["done"] = True
        cancel_poll_stop.set()
        heartbeat_thread.join(timeout=2.0)


if __name__ == "__main__":
    sys.exit(main())
