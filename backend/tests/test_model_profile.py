from __future__ import annotations

import json
from unittest.mock import patch

import pytest

pytest.importorskip("transformers")
pytest.importorskip("torch")

import torch.nn as nn  # noqa: E402

from app.services import trainer  # noqa: E402


def test_emit_model_profile_walks_named_parameters(
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = nn.Sequential(
        nn.Linear(10, 20),
        nn.Linear(20, 5),
    )

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_model_profile(model=model)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    profile = next(e for e in events if e["type"] == "model_profile")
    assert profile["total_params"] > 0
    assert profile["trainable_params"] > 0
    assert len(profile["layers"]) >= 2
    first_layer = profile["layers"][0]
    assert "name" in first_layer
    assert "shape" in first_layer
    assert "param_count" in first_layer
    assert first_layer["trainable"] in (True, False)
    assert first_layer["dtype"]


def test_emit_model_profile_captures_frozen_layers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = nn.Linear(10, 5)
    for p in model.parameters():
        p.requires_grad = False

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_model_profile(model=model)

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    profile = next(e for e in events if e["type"] == "model_profile")
    assert profile["trainable_params"] == 0
    assert all(layer["trainable"] is False for layer in profile["layers"])
