"""peft → MLX adapter format conversion for local serving.

Reads a peft LoRA adapter directory (``adapter_config.json`` +
``adapter_model.safetensors``) and writes an MLX-format adapter directory
(``adapter_config.json`` + ``adapters.safetensors``) that ``mlx_lm.server``
can load via ``--adapter-path``.

Scope:

* Standard peft LoRA adapters (``peft_type == "LORA"``) trained against
  HuggingFace bases.
* Standard ``target_modules`` (e.g. ``q_proj``, ``v_proj``).
* ``bias == "none"``.

Rejected with :class:`UnsupportedPeftAdapterError`:

* QLoRA / quantized adapters (``quantization_config`` populated) — MLX uses a
  different quantization scheme than ``bitsandbytes``, so weight values do not
  round-trip cleanly.
* ``bias`` other than ``"none"`` — peft writes additional bias tensors that
  have no direct MLX equivalent.
* Non-LoRA peft types.
* safetensors files whose keys do not match the standard peft LoRA pattern.

Caveats the operator should know:

* This converter preserves tensor values byte-for-byte and renames keys per the
  standard convention. It does not verify numerical correctness against the
  trained reference model — operators should sanity-check inference output
  against the training pipeline's eval suite before trusting the adapter in
  production.
* ``safetensors`` is lazy-imported so base/local installs without the
  ``training`` or ``serving`` extras still import this module cleanly.

Key renaming convention (peft → MLX)::

    base_model.model.<path>.lora_A.weight  →  <path>.lora_a.weight
    base_model.model.<path>.lora_B.weight  →  <path>.lora_b.weight
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any


class UnsupportedPeftAdapterError(Exception):
    """Raised when a peft adapter cannot be converted to MLX format."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"peft adapter conversion unsupported: {reason}")
        self.reason = reason


_PEFT_KEY_PATTERN = re.compile(r"^base_model\.model\.(.+)\.lora_([AB])\.weight$")


def is_peft_adapter_directory(path: Path) -> bool:
    """Return True when *path* contains a peft adapter (config + safetensors)."""
    if not path.is_dir():
        return False
    config = path / "adapter_config.json"
    weights = path / "adapter_model.safetensors"
    return config.is_file() and weights.is_file()


def convert_peft_adapter_to_mlx(*, source: Path, destination: Path) -> Path:
    """Convert the peft adapter at *source* into MLX format at *destination*.

    The destination directory is created if missing. On success the directory
    contains ``adapter_config.json`` and ``adapters.safetensors``. On failure
    the destination is left untouched — writes happen in a sibling temp dir and
    are moved into place atomically only after every step succeeds.
    """
    config_path = source / "adapter_config.json"
    weights_path = source / "adapter_model.safetensors"

    if not config_path.is_file():
        raise UnsupportedPeftAdapterError(f"missing adapter_config.json at {source}")
    if not weights_path.is_file():
        raise UnsupportedPeftAdapterError(
            f"missing adapter_model.safetensors at {source}"
        )

    with config_path.open("r", encoding="utf-8") as fh:
        peft_config: dict[str, Any] = json.load(fh)

    _validate_peft_config(peft_config=peft_config)
    mlx_config = _translate_config(peft_config=peft_config)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent)
    )
    try:
        (staging / "adapter_config.json").write_text(
            json.dumps(mlx_config, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        _rename_safetensors_keys(
            source=weights_path,
            destination=staging / "adapters.safetensors",
        )
        if destination.exists():
            shutil.rmtree(destination)
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def _validate_peft_config(*, peft_config: dict[str, Any]) -> None:
    peft_type = peft_config.get("peft_type")
    if peft_type != "LORA":
        raise UnsupportedPeftAdapterError(
            f"peft_type must be 'LORA' (got {peft_type!r})"
        )
    if peft_config.get("quantization_config") is not None:
        raise UnsupportedPeftAdapterError(
            "QLoRA / quantized adapters are not supported "
            "(MLX uses a different quantization scheme than bitsandbytes)"
        )
    bias = peft_config.get("bias", "none")
    if bias != "none":
        raise UnsupportedPeftAdapterError(
            f"bias must be 'none' for conversion (got {bias!r})"
        )


def _translate_config(*, peft_config: dict[str, Any]) -> dict[str, Any]:
    rank = int(peft_config.get("r", 8))
    alpha = float(peft_config.get("lora_alpha", rank * 2))
    dropout = float(peft_config.get("lora_dropout", 0.0))
    raw_target_modules = peft_config.get("target_modules") or []
    target_modules = (
        [raw_target_modules]
        if isinstance(raw_target_modules, str)
        else list(raw_target_modules)
    )
    scale = alpha / rank if rank > 0 else 1.0
    return {
        "fine_tune_type": "lora",
        "lora_parameters": {
            "rank": rank,
            "alpha": alpha,
            "dropout": dropout,
            "scale": scale,
        },
        "target_modules": target_modules,
    }


def _rename_safetensors_keys(*, source: Path, destination: Path) -> None:
    """Read peft safetensors, rename keys to MLX convention, write to destination.

    Raises :class:`UnsupportedPeftAdapterError` if any tensor key does not match
    the standard peft LoRA pattern — partial conversion would silently drop
    weights from the served model, which is worse than rejecting outright.
    """
    from safetensors.numpy import load_file, save_file

    tensors = load_file(str(source))
    renamed: dict[str, Any] = {}
    unmatched: list[str] = []
    for key, tensor in tensors.items():
        new_key = _convert_key(peft_key=key)
        if new_key is None:
            unmatched.append(key)
            continue
        renamed[new_key] = tensor
    if unmatched:
        raise UnsupportedPeftAdapterError(
            "safetensors contains keys that do not match the standard peft LoRA "
            f"pattern; first offenders: {unmatched[:5]}"
        )
    if not renamed:
        raise UnsupportedPeftAdapterError(
            "no convertible LoRA keys found in safetensors"
        )
    save_file(renamed, str(destination))


def _convert_key(*, peft_key: str) -> str | None:
    """Map a peft LoRA tensor key to its MLX equivalent. Returns None if unknown."""
    match = _PEFT_KEY_PATTERN.match(peft_key)
    if match is None:
        return None
    base_path = match.group(1)
    suffix = match.group(2).lower()
    return f"{base_path}.lora_{suffix}.weight"
