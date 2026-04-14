"""Tests for scripts/bench/run_local.py.

All tests use a fake trainer (``fake_trainer.py``) wired via the
``BENCH_TRAINER_CMD`` environment variable, so no GPU / torch / HF download
is required.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_SCRIPTS_BENCH_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SCRIPTS_BENCH_DIR.parent.parent
_FAKE_TRAINER = Path(__file__).resolve().parent / "fake_trainer.py"
_CONFIG_PATH = _REPO_ROOT / "configs" / "bench" / "qwen15b-lora.yaml"

sys.path.insert(0, str(_SCRIPTS_BENCH_DIR))

from run_local import (  # noqa: E402
    _build_unavailable_reasons,
    _compute_config_hash,
    _derive_cost_usd,
    _derive_summary_metrics,
    _derive_tokens_per_sec,
    _extract_bench_sidecar,
    _patch_config_for_device,
    _update_events_from_event,
    TrainerEvents,
)


def _load_bench_config() -> dict[str, object]:
    return yaml.safe_load(_CONFIG_PATH.read_text())


def test_patch_config_disables_quantization_for_mps() -> None:
    raw_config = _load_bench_config()
    patched = _patch_config_for_device(raw_config=raw_config, device="mps")
    assert patched["quantization"]["enabled"] is False  # type: ignore[index]
    assert patched["execution"]["device"] == "mps"  # type: ignore[index]


def test_patch_config_enables_quantization_for_cuda() -> None:
    raw_config = _load_bench_config()
    patched = _patch_config_for_device(raw_config=raw_config, device="cuda")
    assert patched["quantization"]["enabled"] is True  # type: ignore[index]
    assert patched["execution"]["device"] == "cuda"  # type: ignore[index]


def test_patch_config_disables_quantization_for_cpu() -> None:
    raw_config = _load_bench_config()
    patched = _patch_config_for_device(raw_config=raw_config, device="cpu")
    assert patched["quantization"]["enabled"] is False  # type: ignore[index]
    assert patched["execution"]["device"] == "cpu"  # type: ignore[index]


def test_patch_config_does_not_mutate_input() -> None:
    raw_config = _load_bench_config()
    original_quant_enabled = raw_config["quantization"]["enabled"]  # type: ignore[index]
    _patch_config_for_device(raw_config=raw_config, device="mps")
    assert raw_config["quantization"]["enabled"] == original_quant_enabled  # type: ignore[index]


def test_compute_config_hash_is_stable() -> None:
    hash_a = _compute_config_hash(config_path=_CONFIG_PATH)
    hash_b = _compute_config_hash(config_path=_CONFIG_PATH)
    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_extract_bench_sidecar_reads_eval_split_hash() -> None:
    sidecar = _extract_bench_sidecar(raw_config=_load_bench_config())
    assert sidecar.eval_split_hash is None


def test_update_events_tracks_peak_memory_and_loss() -> None:
    events = TrainerEvents()
    _update_events_from_event(
        events=events,
        event={
            "type": "metric",
            "step": 10,
            "metrics": {"loss": 1.5, "memory_mb": 800.0},
        },
        wall_clock_seconds=1.0,
    )
    _update_events_from_event(
        events=events,
        event={
            "type": "metric",
            "step": 20,
            "metrics": {"loss": 1.2, "memory_mb": 900.0},
        },
        wall_clock_seconds=2.0,
    )
    assert events.peak_memory_mb == 900.0
    assert events.last_train_loss == 1.2
    assert events.metric_event_count == 2


def test_update_events_captures_first_checkpoint_time() -> None:
    events = TrainerEvents()
    _update_events_from_event(
        events=events,
        event={"type": "checkpoint", "step": 10, "path": "x", "size_bytes": 1},
        wall_clock_seconds=5.5,
    )
    _update_events_from_event(
        events=events,
        event={"type": "checkpoint", "step": 20, "path": "y", "size_bytes": 2},
        wall_clock_seconds=9.9,
    )
    assert events.first_checkpoint_wall_seconds == 5.5


def test_derive_tokens_per_sec_prefers_samples_per_second() -> None:
    events = TrainerEvents(samples_per_second=8.0)
    raw_config: dict[str, object] = {"preprocessing": {"max_seq_length": 512}}
    assert _derive_tokens_per_sec(events=events, raw_config=raw_config) == 8.0 * 512


def test_derive_tokens_per_sec_returns_none_without_data() -> None:
    events = TrainerEvents()
    assert _derive_tokens_per_sec(events=events, raw_config={}) is None


def test_derive_cost_usd_zero_for_mps() -> None:
    assert _derive_cost_usd(device="mps", wall_clock_s=3600.0) == 0.0


def test_derive_cost_usd_cuda_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BENCH_CUDA_HOURLY_USD", "2.0")
    assert _derive_cost_usd(device="cuda", wall_clock_s=1800.0) == 1.0


def test_derive_cost_usd_cuda_defaults_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BENCH_CUDA_HOURLY_USD", raising=False)
    assert _derive_cost_usd(device="cuda", wall_clock_s=3600.0) == 0.0


def test_build_unavailable_reasons_marks_deferred_metrics() -> None:
    events = TrainerEvents()
    summary_metrics = _derive_summary_metrics(
        events=events,
        raw_config={},
        device="mps",
        wall_clock_s=10.0,
    )
    reasons = _build_unavailable_reasons(
        events=events, metrics=summary_metrics, trainer_exit_code=0
    )
    assert reasons["heldout_perplexity"] == "deferred to post-train eval"
    assert reasons["judge_pass_rate"] == "deferred to judge-harness runner"


def _run_bash_help() -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "BENCH_PYTHON": sys.executable}
    return subprocess.run(
        ["bash", str(_SCRIPTS_BENCH_DIR / "run_local.sh"), "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_bash_wrapper_help_exits_zero() -> None:
    result = _run_bash_help()
    assert result.returncode == 0
    assert "unified benchmark runner" in result.stdout.lower()


@pytest.mark.skipif(
    os.environ.get("BENCH_SKIP_INTEGRATION") == "1",
    reason="explicitly skipped via BENCH_SKIP_INTEGRATION",
)
def test_end_to_end_with_fake_trainer(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    env = {
        **os.environ,
        "BENCH_TRAINER_CMD": f"{sys.executable} {_FAKE_TRAINER}",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS_BENCH_DIR / "run_local.py"),
            "--device",
            "cpu",
            "--config",
            str(_CONFIG_PATH),
            "--output-dir",
            str(output_dir),
            "--repo-root",
            str(_REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    metrics_path = output_dir / "metrics.jsonl"
    summary_path = output_dir / "summary.json"
    patched_path = output_dir / "patched-config.yaml"
    assert metrics_path.exists()
    assert summary_path.exists()
    assert patched_path.exists()

    lines = [line for line in metrics_path.read_text().splitlines() if line.strip()]
    assert len(lines) >= 5
    parsed_events: list[dict[str, Any]] = [json.loads(line) for line in lines]
    event_types = {event["type"] for event in parsed_events}
    assert {
        "stage_enter",
        "metric",
        "progress",
        "checkpoint",
        "complete",
    } <= event_types

    summary = json.loads(summary_path.read_text())
    required_keys = {
        "tokens_per_sec",
        "time_to_first_checkpoint_s",
        "wall_clock_s",
        "peak_memory_mb",
        "final_training_loss",
        "heldout_perplexity",
        "cost_usd",
        "judge_pass_rate",
        "run_id",
        "device",
        "config_hash",
        "eval_split_hash",
        "started_at",
        "completed_at",
        "metric_unavailable_reasons",
    }
    assert required_keys <= set(summary.keys())
    assert summary["device"] == "cpu"
    assert summary["run_id"].startswith("bench-cpu-")
    assert summary["peak_memory_mb"] == 1030.0
    assert summary["time_to_first_checkpoint_s"] is not None
    assert summary["time_to_first_checkpoint_s"] > 0
    assert summary["final_training_loss"] is not None
    assert summary["tokens_per_sec"] is not None and summary["tokens_per_sec"] > 0
    assert summary["heldout_perplexity"] is None
    assert summary["judge_pass_rate"] is None
    assert summary["cost_usd"] == 0.0
    assert summary["metric_unavailable_reasons"]["heldout_perplexity"]
    assert summary["metric_unavailable_reasons"]["judge_pass_rate"]

    patched_text = patched_path.read_text()
    assert "Original SHA256:" in patched_text
    patched_yaml = yaml.safe_load(
        "\n".join(
            line for line in patched_text.splitlines() if not line.startswith("#")
        )
    )
    assert patched_yaml["quantization"]["enabled"] is False
    assert patched_yaml["execution"]["device"] == "cpu"
