"""Unified benchmark runner — invokes the existing trainer headlessly.

Reuses `backend/app/services/trainer.py` as a subprocess (identical to
`training_dispatcher.py`), captures its stdout JSON event stream, and emits
two files in the caller-supplied output dir:

  * ``metrics.jsonl`` — every trainer event, one JSON object per line.
  * ``summary.json`` — the 8-field benchmark summary schema plus provenance.

This runner does not write to the webapp's database. A future ingestion step
can import ``summary.json`` rows into ``runs``.

Architecture notes:
  * The shell wrapper (`run_local.sh`) is a thin forwarder. Keeping the real
    logic in Python lets us validate config via the existing Pydantic models,
    parse the event stream line-by-line, and emit a typed summary.
  * Config patching is pure: load YAML, deep-copy, mutate ``quantization``
    and ``execution.device``, write to ``<output-dir>/patched-config.yaml``.
    A banner comment records the original SHA256 so archived patched files
    are self-documenting.
  * ``summary.json.config_hash`` is the SHA256 of the *original* config
    file bytes. The patched temp file is an implementation detail.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Literal, cast

import yaml

_STDERR_PREFIX = "[bench]"

DeviceLiteral = Literal["cuda", "mps", "cpu"]
_VALID_DEVICES: tuple[DeviceLiteral, ...] = ("cuda", "mps", "cpu")

_DEFERRED_HELDOUT_REASON = "deferred to post-train eval"
_DEFERRED_JUDGE_REASON = "deferred to judge-harness runner"
_NO_METRIC_EVENTS_REASON = "trainer emitted no metric events"
_NO_CHECKPOINT_REASON = "trainer emitted no checkpoint event"
_NO_MEMORY_KEY_REASON = (
    "trainer metric events did not include a memory key "
    "(looked for memory_mb, peak_memory_mb, memory_allocated_mb)"
)
_NO_TOKENS_REASON = "insufficient data to derive tokens_per_sec"
_TRAINER_CRASHED_REASON = "trainer exited non-zero before emitting complete event"
_CUDA_RATE_DEFAULT_WARNING = (
    "BENCH_CUDA_HOURLY_USD not set; cost_usd will be 0.0 (CI-safe default)."
)

_MEMORY_KEYS: tuple[str, ...] = ("memory_mb", "peak_memory_mb", "memory_allocated_mb")

_EVAL_SPLIT_RELATIVE_PATH = Path("configs") / "bench" / "eval_split.jsonl"
_EVAL_SPLIT_HASH_NULL_WARNING = (
    "bench.eval_split_hash is null; skipping eval-split integrity check. "
    "Populate the hash via scripts/bench/freeze_eval_split.py to enforce."
)


@dataclass
class RunnerArgs:
    device: DeviceLiteral
    config_path: Path
    output_dir: Path
    repo_root: Path
    run_judge_sanity: bool


@dataclass
class BenchSidecar:
    eval_split_hash: str | None


@dataclass
class TrainerEvents:
    """Aggregated view of the trainer's stdout event stream."""

    first_checkpoint_wall_seconds: float | None = None
    peak_memory_mb: float | None = None
    memory_key_seen: bool = False
    metric_event_count: int = 0
    last_train_loss: float | None = None
    complete_final_metrics: dict[str, float] | None = None
    complete_status: str | None = None
    total_steps_seen: int = 0
    max_step_seen: int = 0
    samples_per_second: float | None = None
    train_runtime_seconds: float | None = None
    saw_error_event: bool = False
    error_messages: list[str] = field(default_factory=list)


@dataclass
class SummaryMetrics:
    tokens_per_sec: float | None
    time_to_first_checkpoint_s: float | None
    wall_clock_s: float
    peak_memory_mb: float | None
    final_training_loss: float | None
    heldout_perplexity: float | None
    cost_usd: float
    judge_pass_rate: float | None


def _eprint(message: str) -> None:
    print(f"{_STDERR_PREFIX} {message}", file=sys.stderr, flush=True)


def _compute_config_hash(*, config_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(config_path.read_bytes())
    return digest.hexdigest()


def _patch_config_for_device(
    *,
    raw_config: dict[str, object],
    device: DeviceLiteral,
) -> dict[str, object]:
    """Return a deep-copied config with device-appropriate quantization + execution."""
    patched = copy.deepcopy(raw_config)

    execution_raw = patched.get("execution")
    execution = execution_raw if isinstance(execution_raw, dict) else {}
    execution["device"] = device
    patched["execution"] = execution

    quant_raw = patched.get("quantization")
    quantization = quant_raw if isinstance(quant_raw, dict) else {}
    if device == "cuda":
        quantization.setdefault("enabled", True)
    else:
        quantization["enabled"] = False
    patched["quantization"] = quantization

    return patched


def _write_patched_config(
    *,
    patched_config: dict[str, object],
    destination: Path,
    original_sha256: str,
    original_path: Path,
    device: DeviceLiteral,
) -> None:
    banner = (
        "# Auto-generated by scripts/bench/run_local.py. Do not edit.\n"
        f"# Derived from: {original_path}\n"
        f"# Original SHA256: {original_sha256}\n"
        f"# Device override: {device}\n"
        f"# Generated at: {datetime.now(UTC).isoformat()}\n"
    )
    body = yaml.safe_dump(patched_config, sort_keys=False)
    destination.write_text(banner + body)


def _extract_bench_sidecar(*, raw_config: dict[str, object]) -> BenchSidecar:
    bench_raw = raw_config.get("bench")
    if not isinstance(bench_raw, dict):
        return BenchSidecar(eval_split_hash=None)
    hash_value = bench_raw.get("eval_split_hash")
    eval_split_hash = hash_value if isinstance(hash_value, str) and hash_value else None
    return BenchSidecar(eval_split_hash=eval_split_hash)


def _compute_eval_split_hash(*, eval_split_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(eval_split_path.read_bytes())
    return digest.hexdigest()


def _validate_eval_split_hash(
    *,
    bench_sidecar: BenchSidecar,
    repo_root: Path,
) -> str | None:
    """Enforce that the YAML-declared eval-split hash matches the on-disk file.

    Returns an error message suitable for ``_eprint`` on mismatch / missing
    file. Returns ``None`` when the hash matches (or when the sidecar declared
    no hash, which intentionally falls back to a soft warning).
    """
    declared_hash = bench_sidecar.eval_split_hash
    eval_split_path = repo_root / _EVAL_SPLIT_RELATIVE_PATH

    if declared_hash is None:
        _eprint(f"warning: {_EVAL_SPLIT_HASH_NULL_WARNING}")
        return None

    if not eval_split_path.exists():
        return (
            f"eval_split.jsonl missing but bench.eval_split_hash is set "
            f"(expected at {eval_split_path})"
        )

    actual_hash = _compute_eval_split_hash(eval_split_path=eval_split_path)
    if actual_hash != declared_hash:
        return f"eval_split_hash mismatch: YAML={declared_hash} disk={actual_hash}"
    return None


def _validate_device_available(*, device: DeviceLiteral) -> None:
    """Confirm the requested device is actually usable on this host.

    Import torch lazily so --help works even without torch installed. The cpu
    path skips the torch check entirely — useful for smoke tests and CI where
    torch isn't installed and no accelerator is required.
    """
    if device == "cpu":
        return

    try:
        import torch  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "torch is not importable; install the backend 'training' extras "
            "(pip install -e 'backend[training]') before running the bench."
        ) from exc

    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA requested but torch.cuda.is_available() returned False."
            )
    elif device == "mps":
        if not torch.backends.mps.is_available():
            raise RuntimeError(
                "MPS requested but torch.backends.mps.is_available() returned False."
            )


def _validate_config_schema(*, raw_config: dict[str, object], repo_root: Path) -> None:
    """Best-effort Pydantic validation of the YAML before trainer launch.

    Import WorkbenchConfig lazily by first adding backend/ to sys.path. If the
    backend package isn't importable (e.g. torch missing), skip validation with
    a warning — the trainer subprocess will perform its own config validation
    stage either way.
    """
    backend_path = repo_root / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    try:
        from app.schemas.workbench_config import WorkbenchConfig  # noqa: PLC0415
    except ImportError as exc:
        _eprint(
            f"warning: skipping pre-flight config validation (backend import failed: {exc})"
        )
        return

    try:
        WorkbenchConfig.model_validate(raw_config)
    except Exception as exc:
        raise RuntimeError(f"Config schema validation failed: {exc}") from exc


def _synthesize_run_id(*, device: DeviceLiteral) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"bench-{device}-{timestamp}"


def _build_trainer_command(
    *,
    run_id: str,
    patched_config_path: Path,
    project_dir: Path,
    heartbeat_interval: int,
) -> list[str]:
    return [
        sys.executable,
        "-u",
        "-m",
        "app.services.trainer",
        "--run-id",
        run_id,
        "--config-path",
        str(patched_config_path),
        "--project-dir",
        str(project_dir),
        "--heartbeat-interval",
        str(heartbeat_interval),
    ]


def _update_events_from_event(
    *,
    events: TrainerEvents,
    event: dict[str, object],
    wall_clock_seconds: float,
) -> None:
    event_type = event.get("type")
    if event_type == "checkpoint":
        if events.first_checkpoint_wall_seconds is None:
            events.first_checkpoint_wall_seconds = wall_clock_seconds
    elif event_type == "metric":
        events.metric_event_count += 1
        metrics_raw = event.get("metrics")
        if isinstance(metrics_raw, dict):
            for memory_key in _MEMORY_KEYS:
                memory_value = metrics_raw.get(memory_key)
                if isinstance(memory_value, (int, float)):
                    events.memory_key_seen = True
                    current_peak = events.peak_memory_mb
                    if current_peak is None or memory_value > current_peak:
                        events.peak_memory_mb = float(memory_value)
            loss = metrics_raw.get("loss")
            if isinstance(loss, (int, float)):
                events.last_train_loss = float(loss)
            else:
                train_loss = metrics_raw.get("train_loss")
                if isinstance(train_loss, (int, float)):
                    events.last_train_loss = float(train_loss)
            sps = metrics_raw.get("train_samples_per_second")
            if isinstance(sps, (int, float)):
                events.samples_per_second = float(sps)
            runtime = metrics_raw.get("train_runtime")
            if isinstance(runtime, (int, float)):
                events.train_runtime_seconds = float(runtime)
    elif event_type == "progress":
        current_step = event.get("current_step")
        total_steps = event.get("total_steps")
        if isinstance(current_step, int) and current_step > events.max_step_seen:
            events.max_step_seen = current_step
        if isinstance(total_steps, int) and total_steps > events.total_steps_seen:
            events.total_steps_seen = total_steps
    elif event_type == "complete":
        status = event.get("status")
        if isinstance(status, str):
            events.complete_status = status
        final_metrics_raw = event.get("final_metrics")
        if isinstance(final_metrics_raw, dict):
            coerced: dict[str, float] = {}
            for key, value in final_metrics_raw.items():
                if isinstance(value, (int, float)):
                    coerced[key] = float(value)
            events.complete_final_metrics = coerced
            train_loss = coerced.get("train_loss")
            if train_loss is not None and events.last_train_loss is None:
                events.last_train_loss = train_loss
            sps = coerced.get("train_samples_per_second")
            if sps is not None and events.samples_per_second is None:
                events.samples_per_second = sps
            runtime = coerced.get("train_runtime")
            if runtime is not None and events.train_runtime_seconds is None:
                events.train_runtime_seconds = runtime
    elif event_type == "error":
        events.saw_error_event = True
        message = event.get("message")
        if isinstance(message, str):
            events.error_messages.append(message)


def _capture_trainer_stream(
    *,
    stdout: IO[str],
    metrics_file: IO[str],
    start_monotonic: float,
) -> TrainerEvents:
    events = TrainerEvents()
    for line in stdout:
        stripped = line.strip()
        if not stripped:
            continue
        metrics_file.write(line if line.endswith("\n") else line + "\n")
        metrics_file.flush()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        wall_clock = time.monotonic() - start_monotonic
        _update_events_from_event(
            events=events, event=parsed, wall_clock_seconds=wall_clock
        )
    return events


def _derive_tokens_per_sec(
    *,
    events: TrainerEvents,
    raw_config: dict[str, object],
) -> float | None:
    """Prefer trainer-reported samples_per_second (× seq_len). Fall back to a
    steps×batch×seq_len / runtime estimate.
    """
    preprocessing_raw = raw_config.get("preprocessing")
    preprocessing = preprocessing_raw if isinstance(preprocessing_raw, dict) else {}
    max_seq_length_raw = preprocessing.get("max_seq_length", 512)
    max_seq_length = (
        int(max_seq_length_raw) if isinstance(max_seq_length_raw, (int, float)) else 512
    )

    if events.samples_per_second is not None and events.samples_per_second > 0:
        return events.samples_per_second * max_seq_length

    if events.train_runtime_seconds is None or events.train_runtime_seconds <= 0:
        return None

    training_raw = raw_config.get("training")
    training = training_raw if isinstance(training_raw, dict) else {}
    batch_raw = training.get("batch_size", 1)
    batch_size = int(batch_raw) if isinstance(batch_raw, (int, float)) else 1
    grad_accum_raw = training.get("gradient_accumulation_steps", 1)
    grad_accum = int(grad_accum_raw) if isinstance(grad_accum_raw, (int, float)) else 1

    total_steps = events.max_step_seen or events.total_steps_seen
    if total_steps <= 0:
        return None

    tokens_processed = total_steps * batch_size * grad_accum * max_seq_length
    return tokens_processed / events.train_runtime_seconds


def _derive_cost_usd(*, device: DeviceLiteral, wall_clock_s: float) -> float:
    if device != "cuda":
        return 0.0
    hourly_rate_str = os.environ.get("BENCH_CUDA_HOURLY_USD")
    if not hourly_rate_str:
        _eprint(_CUDA_RATE_DEFAULT_WARNING)
        return 0.0
    try:
        hourly_rate = float(hourly_rate_str)
    except ValueError:
        _eprint(
            f"warning: BENCH_CUDA_HOURLY_USD={hourly_rate_str!r} is not a float; "
            "using 0.0"
        )
        return 0.0
    return wall_clock_s / 3600.0 * hourly_rate


def _derive_summary_metrics(
    *,
    events: TrainerEvents,
    raw_config: dict[str, object],
    device: DeviceLiteral,
    wall_clock_s: float,
) -> SummaryMetrics:
    tokens_per_sec = _derive_tokens_per_sec(events=events, raw_config=raw_config)
    final_loss = events.last_train_loss
    if final_loss is None and events.complete_final_metrics is not None:
        final_loss = events.complete_final_metrics.get(
            "train_loss", events.complete_final_metrics.get("loss")
        )
    return SummaryMetrics(
        tokens_per_sec=tokens_per_sec,
        time_to_first_checkpoint_s=events.first_checkpoint_wall_seconds,
        wall_clock_s=wall_clock_s,
        peak_memory_mb=events.peak_memory_mb,
        final_training_loss=final_loss,
        heldout_perplexity=None,
        cost_usd=_derive_cost_usd(device=device, wall_clock_s=wall_clock_s),
        judge_pass_rate=None,
    )


def _build_unavailable_reasons(
    *,
    events: TrainerEvents,
    metrics: SummaryMetrics,
    trainer_exit_code: int,
) -> dict[str, str]:
    reasons: dict[str, str] = {
        "heldout_perplexity": _DEFERRED_HELDOUT_REASON,
        "judge_pass_rate": _DEFERRED_JUDGE_REASON,
    }
    if metrics.tokens_per_sec is None:
        reasons["tokens_per_sec"] = (
            _TRAINER_CRASHED_REASON if trainer_exit_code != 0 else _NO_TOKENS_REASON
        )
    if metrics.time_to_first_checkpoint_s is None:
        reasons["time_to_first_checkpoint_s"] = (
            _TRAINER_CRASHED_REASON if trainer_exit_code != 0 else _NO_CHECKPOINT_REASON
        )
    if metrics.peak_memory_mb is None:
        reasons["peak_memory_mb"] = (
            _TRAINER_CRASHED_REASON
            if trainer_exit_code != 0 and events.metric_event_count == 0
            else _NO_MEMORY_KEY_REASON
        )
    if metrics.final_training_loss is None:
        reasons["final_training_loss"] = (
            _TRAINER_CRASHED_REASON
            if trainer_exit_code != 0
            else _NO_METRIC_EVENTS_REASON
        )
    return reasons


def _write_summary(
    *,
    summary_path: Path,
    run_id: str,
    device: DeviceLiteral,
    config_hash: str,
    bench_sidecar: BenchSidecar,
    started_at: str,
    completed_at: str,
    metrics: SummaryMetrics,
    unavailable_reasons: dict[str, str],
) -> None:
    payload: dict[str, object] = {
        "tokens_per_sec": metrics.tokens_per_sec,
        "time_to_first_checkpoint_s": metrics.time_to_first_checkpoint_s,
        "wall_clock_s": metrics.wall_clock_s,
        "peak_memory_mb": metrics.peak_memory_mb,
        "final_training_loss": metrics.final_training_loss,
        "heldout_perplexity": metrics.heldout_perplexity,
        "cost_usd": metrics.cost_usd,
        "judge_pass_rate": metrics.judge_pass_rate,
        "run_id": run_id,
        "device": device,
        "config_hash": config_hash,
        "eval_split_hash": bench_sidecar.eval_split_hash,
        "started_at": started_at,
        "completed_at": completed_at,
        "metric_unavailable_reasons": unavailable_reasons,
    }
    tmp_path = summary_path.with_suffix(summary_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n")
    tmp_path.rename(summary_path)


def _invoke_judge_sanity(
    *,
    summary_path: Path,
    config_path: Path,
    repo_root: Path,
    device: DeviceLiteral,
    output_dir: Path,
) -> int:
    """Invoke scripts/bench/judge_sanity.py as a subprocess.

    Runs in its own process so the judge step's ML imports (transformers,
    peft) don't pollute the runner's import graph, and so a crash in the
    best-effort scoring step cannot fail the trainer's summary write.
    """
    script_path = Path(__file__).resolve().parent / "judge_sanity.py"
    command = [
        sys.executable,
        "-u",
        str(script_path),
        "--summary",
        str(summary_path),
        "--config",
        str(config_path),
        "--repo-root",
        str(repo_root),
        "--device",
        device,
        "--output-dir",
        str(output_dir),
    ]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    completed = subprocess.run(command, env=env, check=False)
    return completed.returncode


def _spawn_trainer(
    *,
    command: list[str],
    cwd: Path,
) -> subprocess.Popen[str]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        env=env,
        text=True,
        bufsize=1,
    )


def _parse_args(*, argv: list[str]) -> RunnerArgs:
    parser = argparse.ArgumentParser(
        prog="run_local.py",
        description=(
            "Unified benchmark runner: reuses the backend trainer subprocess "
            "to collect standardized metrics across MPS/CUDA hosts."
        ),
    )
    parser.add_argument(
        "--device",
        required=True,
        choices=list(_VALID_DEVICES),
        help="Execution device. Must be available on the host.",
    )
    parser.add_argument(
        "--config",
        default="configs/bench/qwen15b-lora.yaml",
        help="Path to the bench YAML config (default: configs/bench/qwen15b-lora.yaml).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write metrics.jsonl and summary.json.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repo root (injected by run_local.sh; defaults to cwd).",
    )
    parser.add_argument(
        "--judge-sanity",
        action="store_true",
        help=(
            "After a successful training run, invoke scripts/bench/judge_sanity.py "
            "to generate 50 completions with the saved adapter and score them via "
            "the Tier-2 G-Eval judge. Requires an OpenAI API key; costs a few cents "
            "per invocation. Disabled by default so CI runs stay free."
        ),
    )
    parsed = parser.parse_args(argv)

    repo_root = Path(parsed.repo_root).resolve() if parsed.repo_root else Path.cwd()
    config_arg = Path(parsed.config)
    config_path = (
        config_arg if config_arg.is_absolute() else (repo_root / config_arg).resolve()
    )
    output_dir = Path(parsed.output_dir).resolve()
    device = cast(DeviceLiteral, parsed.device)
    return RunnerArgs(
        device=device,
        config_path=config_path,
        output_dir=output_dir,
        repo_root=repo_root,
        run_judge_sanity=bool(parsed.judge_sanity),
    )


def run(*, argv: list[str]) -> int:
    try:
        args = _parse_args(argv=argv)
    except SystemExit as exit_exc:
        return int(exit_exc.code or 0)

    if not args.config_path.exists():
        _eprint(f"config not found: {args.config_path}")
        return 2

    try:
        raw_config_loaded = yaml.safe_load(args.config_path.read_text())
    except yaml.YAMLError as exc:
        _eprint(f"failed to parse YAML: {exc}")
        return 2
    if not isinstance(raw_config_loaded, dict):
        _eprint("config YAML must be a mapping at the top level")
        return 2
    raw_config: dict[str, object] = raw_config_loaded

    try:
        _validate_device_available(device=args.device)
    except RuntimeError as exc:
        _eprint(str(exc))
        return 3

    try:
        _validate_config_schema(raw_config=raw_config, repo_root=args.repo_root)
    except RuntimeError as exc:
        _eprint(str(exc))
        return 4

    bench_sidecar = _extract_bench_sidecar(raw_config=raw_config)
    eval_split_error = _validate_eval_split_hash(
        bench_sidecar=bench_sidecar, repo_root=args.repo_root
    )
    if eval_split_error is not None:
        _eprint(eval_split_error)
        return 11

    args.output_dir.mkdir(parents=True, exist_ok=True)
    project_dir = args.output_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)

    config_hash = _compute_config_hash(config_path=args.config_path)
    patched_config = _patch_config_for_device(raw_config=raw_config, device=args.device)
    patched_config_path = args.output_dir / "patched-config.yaml"
    _write_patched_config(
        patched_config=patched_config,
        destination=patched_config_path,
        original_sha256=config_hash,
        original_path=args.config_path,
        device=args.device,
    )

    run_id = _synthesize_run_id(device=args.device)
    backend_cwd = args.repo_root / "backend"
    if not backend_cwd.exists():
        _eprint(f"expected backend directory not found: {backend_cwd}")
        return 5

    trainer_cmd_override = os.environ.get("BENCH_TRAINER_CMD")
    if trainer_cmd_override:
        command = [
            *trainer_cmd_override.split(),
            "--run-id",
            run_id,
            "--config-path",
            str(patched_config_path),
            "--project-dir",
            str(project_dir),
            "--heartbeat-interval",
            "10",
        ]
    else:
        command = _build_trainer_command(
            run_id=run_id,
            patched_config_path=patched_config_path,
            project_dir=project_dir,
            heartbeat_interval=10,
        )

    metrics_path = args.output_dir / "metrics.jsonl"
    summary_path = args.output_dir / "summary.json"

    started_at = datetime.now(UTC).isoformat()
    start_monotonic = time.monotonic()

    try:
        proc = _spawn_trainer(command=command, cwd=backend_cwd)
    except OSError as exc:
        _eprint(f"failed to spawn trainer: {exc}")
        return 6

    if proc.stdout is None:
        _eprint("trainer subprocess has no stdout pipe")
        proc.kill()
        proc.wait()
        return 7

    with metrics_path.open("w", encoding="utf-8") as metrics_file:
        events = _capture_trainer_stream(
            stdout=proc.stdout,
            metrics_file=metrics_file,
            start_monotonic=start_monotonic,
        )

    trainer_exit_code = proc.wait()
    wall_clock_s = time.monotonic() - start_monotonic
    completed_at = datetime.now(UTC).isoformat()

    if proc.stderr is not None:
        try:
            stderr_tail = proc.stderr.read()
        except OSError:
            stderr_tail = ""
        if stderr_tail:
            trainer_stderr_path = args.output_dir / "trainer.stderr.log"
            trainer_stderr_path.write_text(stderr_tail)

    summary_metrics = _derive_summary_metrics(
        events=events,
        raw_config=raw_config,
        device=args.device,
        wall_clock_s=wall_clock_s,
    )
    unavailable_reasons = _build_unavailable_reasons(
        events=events,
        metrics=summary_metrics,
        trainer_exit_code=trainer_exit_code,
    )

    try:
        _write_summary(
            summary_path=summary_path,
            run_id=run_id,
            device=args.device,
            config_hash=config_hash,
            bench_sidecar=bench_sidecar,
            started_at=started_at,
            completed_at=completed_at,
            metrics=summary_metrics,
            unavailable_reasons=unavailable_reasons,
        )
    except OSError as exc:
        _eprint(f"failed to write summary.json: {exc}")
        return 8

    if trainer_exit_code != 0:
        _eprint(
            f"trainer exited with code {trainer_exit_code}; "
            f"partial summary written to {summary_path}"
        )
        return 9 if trainer_exit_code > 0 else abs(trainer_exit_code)

    if events.complete_status not in {"completed", "cancelled"}:
        _eprint(
            "trainer did not emit a terminal 'complete' event; "
            "summary written but may be incomplete"
        )
        return 10

    if args.run_judge_sanity:
        judge_exit = _invoke_judge_sanity(
            summary_path=summary_path,
            config_path=args.config_path,
            repo_root=args.repo_root,
            device=args.device,
            output_dir=args.output_dir,
        )
        if judge_exit != 0:
            _eprint(
                f"judge_sanity.py exited with code {judge_exit}; "
                "summary.json may retain judge_pass_rate=null"
            )

    return 0


def main() -> int:
    return run(argv=sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
