from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from safetensors.numpy import load_file, save_file

from app.services.cloud.mlx_adapter_conversion import (
    UnsupportedPeftAdapterError,
    _convert_key,
    convert_peft_adapter_to_mlx,
    is_peft_adapter_directory,
)


def _write_peft_adapter(
    *,
    directory: Path,
    config_overrides: dict[str, Any] | None = None,
    tensors: dict[str, np.ndarray] | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    base_config: dict[str, Any] = {
        "peft_type": "LORA",
        "task_type": "CAUSAL_LM",
        "r": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "target_modules": ["q_proj", "v_proj"],
        "bias": "none",
        "base_model_name_or_path": "Qwen/Qwen2.5-1.5B",
    }
    if config_overrides:
        base_config.update(config_overrides)
    (directory / "adapter_config.json").write_text(
        json.dumps(base_config, sort_keys=True), encoding="utf-8"
    )
    weights = tensors or {
        "base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight": np.zeros(
            (8, 4), dtype=np.float32
        ),
        "base_model.model.model.layers.0.self_attn.q_proj.lora_B.weight": np.zeros(
            (4, 8), dtype=np.float32
        ),
        "base_model.model.model.layers.0.self_attn.v_proj.lora_A.weight": np.zeros(
            (8, 4), dtype=np.float32
        ),
        "base_model.model.model.layers.0.self_attn.v_proj.lora_B.weight": np.zeros(
            (4, 8), dtype=np.float32
        ),
    }
    save_file(weights, str(directory / "adapter_model.safetensors"))
    return directory


def test_is_peft_adapter_directory_true_when_both_files_present(tmp_path: Path) -> None:
    source = _write_peft_adapter(directory=tmp_path / "adapter")

    assert is_peft_adapter_directory(source) is True


def test_is_peft_adapter_directory_false_when_missing_safetensors(tmp_path: Path) -> None:
    directory = tmp_path / "adapter"
    directory.mkdir()
    (directory / "adapter_config.json").write_text("{}", encoding="utf-8")

    assert is_peft_adapter_directory(directory) is False


def test_is_peft_adapter_directory_false_when_path_is_file(tmp_path: Path) -> None:
    file_path = tmp_path / "lone-file.safetensors"
    file_path.write_bytes(b"")

    assert is_peft_adapter_directory(file_path) is False


def test_convert_writes_mlx_layout_with_renamed_keys(tmp_path: Path) -> None:
    source = _write_peft_adapter(directory=tmp_path / "checkpoint-final")
    destination = tmp_path / "mlx-adapters" / "checkpoint-final"

    result = convert_peft_adapter_to_mlx(source=source, destination=destination)

    assert result == destination
    assert (destination / "adapter_config.json").is_file()
    assert (destination / "adapters.safetensors").is_file()

    config = json.loads((destination / "adapter_config.json").read_text())
    assert config["fine_tune_type"] == "lora"
    assert config["lora_parameters"]["rank"] == 8
    assert config["lora_parameters"]["alpha"] == 16.0
    assert config["lora_parameters"]["scale"] == 16.0 / 8.0
    assert config["target_modules"] == ["q_proj", "v_proj"]

    converted = load_file(str(destination / "adapters.safetensors"))
    assert set(converted.keys()) == {
        "model.layers.0.self_attn.q_proj.lora_a.weight",
        "model.layers.0.self_attn.q_proj.lora_b.weight",
        "model.layers.0.self_attn.v_proj.lora_a.weight",
        "model.layers.0.self_attn.v_proj.lora_b.weight",
    }


def test_convert_preserves_tensor_values(tmp_path: Path) -> None:
    rng = np.random.default_rng(seed=42)
    lora_a = rng.standard_normal(size=(8, 4)).astype(np.float32)
    lora_b = rng.standard_normal(size=(4, 8)).astype(np.float32)
    source = _write_peft_adapter(
        directory=tmp_path / "src",
        tensors={
            "base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight": lora_a,
            "base_model.model.model.layers.0.self_attn.q_proj.lora_B.weight": lora_b,
        },
    )
    destination = tmp_path / "dst"

    convert_peft_adapter_to_mlx(source=source, destination=destination)

    converted = load_file(str(destination / "adapters.safetensors"))
    np.testing.assert_array_equal(
        converted["model.layers.0.self_attn.q_proj.lora_a.weight"], lora_a
    )
    np.testing.assert_array_equal(
        converted["model.layers.0.self_attn.q_proj.lora_b.weight"], lora_b
    )


def test_convert_rejects_qlora_with_quantization_config(tmp_path: Path) -> None:
    source = _write_peft_adapter(
        directory=tmp_path / "qlora",
        config_overrides={"quantization_config": {"bnb_4bit_quant_type": "nf4"}},
    )

    with pytest.raises(UnsupportedPeftAdapterError, match="QLoRA"):
        convert_peft_adapter_to_mlx(source=source, destination=tmp_path / "dst")


def test_convert_rejects_non_lora_peft_type(tmp_path: Path) -> None:
    source = _write_peft_adapter(
        directory=tmp_path / "prefix",
        config_overrides={"peft_type": "PROMPT_TUNING"},
    )

    with pytest.raises(UnsupportedPeftAdapterError, match="LORA"):
        convert_peft_adapter_to_mlx(source=source, destination=tmp_path / "dst")


def test_convert_rejects_non_none_bias(tmp_path: Path) -> None:
    source = _write_peft_adapter(
        directory=tmp_path / "biased",
        config_overrides={"bias": "all"},
    )

    with pytest.raises(UnsupportedPeftAdapterError, match="bias"):
        convert_peft_adapter_to_mlx(source=source, destination=tmp_path / "dst")


def test_convert_rejects_unknown_safetensor_keys(tmp_path: Path) -> None:
    source = _write_peft_adapter(
        directory=tmp_path / "bad-keys",
        tensors={
            "wholly_unexpected_key": np.zeros((4, 4), dtype=np.float32),
        },
    )

    with pytest.raises(UnsupportedPeftAdapterError, match="do not match"):
        convert_peft_adapter_to_mlx(source=source, destination=tmp_path / "dst")


def test_convert_missing_config_raises(tmp_path: Path) -> None:
    source = tmp_path / "no-config"
    source.mkdir()
    save_file({"k": np.zeros((1,), dtype=np.float32)}, str(source / "adapter_model.safetensors"))

    with pytest.raises(UnsupportedPeftAdapterError, match="adapter_config"):
        convert_peft_adapter_to_mlx(source=source, destination=tmp_path / "dst")


def test_convert_missing_safetensors_raises(tmp_path: Path) -> None:
    source = tmp_path / "no-safetensors"
    source.mkdir()
    (source / "adapter_config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(UnsupportedPeftAdapterError, match="adapter_model"):
        convert_peft_adapter_to_mlx(source=source, destination=tmp_path / "dst")


def test_convert_idempotent_overwrites_existing_destination(tmp_path: Path) -> None:
    source = _write_peft_adapter(directory=tmp_path / "src")
    destination = tmp_path / "dst"
    destination.mkdir()
    (destination / "stale.txt").write_text("stale", encoding="utf-8")

    convert_peft_adapter_to_mlx(source=source, destination=destination)

    assert not (destination / "stale.txt").exists()
    assert (destination / "adapters.safetensors").is_file()


def test_convert_failure_leaves_destination_untouched(tmp_path: Path) -> None:
    source = _write_peft_adapter(
        directory=tmp_path / "bad",
        tensors={"not_a_lora_key": np.zeros((1,), dtype=np.float32)},
    )
    destination = tmp_path / "dst"
    destination.mkdir()
    sentinel = destination / "previous-good-adapter.txt"
    sentinel.write_text("prior", encoding="utf-8")

    with pytest.raises(UnsupportedPeftAdapterError):
        convert_peft_adapter_to_mlx(source=source, destination=destination)

    assert sentinel.read_text() == "prior"
    staging_dirs = [
        child
        for child in destination.parent.iterdir()
        if child.is_dir() and child.name.startswith(".dst.staging-")
    ]
    assert staging_dirs == []


def test_convert_handles_string_target_modules(tmp_path: Path) -> None:
    """peft sometimes stores target_modules as a string regex rather than a list."""
    source = _write_peft_adapter(
        directory=tmp_path / "str-target",
        config_overrides={"target_modules": "q_proj"},
    )

    convert_peft_adapter_to_mlx(source=source, destination=tmp_path / "dst")

    config = json.loads((tmp_path / "dst" / "adapter_config.json").read_text())
    assert config["target_modules"] == ["q_proj"]


def test_convert_key_renames_standard_lora_pattern() -> None:
    converted = _convert_key(
        peft_key="base_model.model.model.layers.5.self_attn.q_proj.lora_A.weight"
    )

    assert converted == "model.layers.5.self_attn.q_proj.lora_a.weight"


def test_convert_key_returns_none_for_unknown_key() -> None:
    assert _convert_key(peft_key="some.other.key.weight") is None
    assert _convert_key(peft_key="base_model.model.foo.lora_C.weight") is None
