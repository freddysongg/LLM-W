from __future__ import annotations

import json
from unittest.mock import patch

import pytest

pytest.importorskip("transformers")
pytest.importorskip("torch")

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402

from app.services import trainer  # noqa: E402


def test_emit_weight_stats_computes_per_layer_stats(
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = nn.Linear(10, 5)

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_weight_stats(model=model, step=100)

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    event = next(e for e in events if e["type"] == "weight_stats")
    assert event["step"] == 100
    assert len(event["stats"]) >= 1
    first_layer_name = next(iter(event["stats"]))
    stats = event["stats"][first_layer_name]
    for key in ("mean", "std", "norm", "min", "max"):
        assert key in stats
        assert isinstance(stats[key], (int, float))


class _SingleParamModule(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.scale = nn.Parameter(torch.tensor([3.14]))


def test_emit_weight_stats_handles_single_element_layer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = _SingleParamModule()

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_weight_stats(model=model, step=1)

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    event = next(e for e in events if e["type"] == "weight_stats")
    stats = event["stats"]["scale"]
    assert stats["std"] == 0.0
