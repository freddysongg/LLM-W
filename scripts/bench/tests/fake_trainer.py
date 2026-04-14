"""Fake trainer used by run_local.py tests.

Emits a fixed sequence of JSON events on stdout matching the real trainer's
schema (see backend/app/services/trainer.py _emit_* helpers). No torch, no
HuggingFace — it just writes JSON and exits.

Invoked via ``BENCH_TRAINER_CMD="python3 <abs-path-to-this-file>"``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from typing import Any


def _emit(event: dict[str, Any]) -> None:
    event.setdefault("timestamp", datetime.now(UTC).isoformat())
    print(json.dumps(event), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--heartbeat-interval", type=int, default=10)
    parser.add_argument("--resume-from-checkpoint", default=None)
    parser.add_argument("--cancel-flag-path", default=None)
    args = parser.parse_args()

    _emit(
        {
            "type": "stage_enter",
            "stage_name": "training_progress",
            "stage_order": 10,
        }
    )
    for step in (10, 20, 30):
        _emit(
            {
                "type": "metric",
                "step": step,
                "epoch": step / 30.0,
                "metrics": {
                    "loss": 2.0 - step / 30.0,
                    "learning_rate": 2e-4,
                    "memory_mb": 1000.0 + step,
                },
            }
        )
        _emit(
            {
                "type": "progress",
                "current_step": step,
                "total_steps": 30,
                "progress_pct": step / 30.0 * 100,
                "epoch": step / 30.0,
            }
        )
        time.sleep(0.01)

    _emit(
        {
            "type": "checkpoint",
            "step": 30,
            "path": f"{args.project_dir}/checkpoints/checkpoint-30",
            "size_bytes": 1234,
        }
    )
    _emit(
        {
            "type": "complete",
            "status": "completed",
            "final_metrics": {
                "train_loss": 1.0,
                "train_runtime": 12.5,
                "train_samples_per_second": 8.0,
            },
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
