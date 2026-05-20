from __future__ import annotations

from dataclasses import dataclass

_SECONDS_PER_HOUR: int = 3600


@dataclass(frozen=True)
class ModalGpuOption:
    gpu_type: str
    label: str
    vram_gb: int
    rate_usd_hr: float


MODAL_GPU_CATALOG: tuple[ModalGpuOption, ...] = (
    ModalGpuOption(gpu_type="t4", label="T4 16GB", vram_gb=16, rate_usd_hr=0.5904),
    ModalGpuOption(gpu_type="a10", label="A10 24GB", vram_gb=24, rate_usd_hr=1.1016),
    ModalGpuOption(gpu_type="l40s", label="L40S 48GB", vram_gb=48, rate_usd_hr=1.9512),
    ModalGpuOption(gpu_type="a100-40gb", label="A100 40GB", vram_gb=40, rate_usd_hr=3.24),
    ModalGpuOption(gpu_type="a100-80gb", label="A100 80GB", vram_gb=80, rate_usd_hr=3.8412),
    ModalGpuOption(gpu_type="h100", label="H100 80GB", vram_gb=80, rate_usd_hr=5.1912),
)


_GPU_INDEX: dict[str, ModalGpuOption] = {option.gpu_type: option for option in MODAL_GPU_CATALOG}


# Map workbench GPU keys to Modal SDK GPU specs. Lives here (not in
# `modal_adapter`) so callers like the settings test-connection helper can
# validate a GPU type without importing `modal` — base installs that omit the
# `cloud` extra should still be able to round-trip GPU type validation.
MODAL_GPU_SPEC_MAP: dict[str, str] = {
    "t4": "T4",
    "a10": "A10G",
    "l40s": "L40S",
    "a100-40gb": "A100",
    "a100-80gb": "A100-80GB",
    "h100": "H100",
}

DEFAULT_MODAL_GPU_SPEC: str = "A10G"


def get_modal_gpu_option(*, gpu_type: str) -> ModalGpuOption | None:
    return _GPU_INDEX.get(gpu_type)


def get_modal_gpu_rate_usd_per_second(*, gpu_type: str) -> float:
    option = _GPU_INDEX.get(gpu_type)
    if option is None:
        return 0.0
    return option.rate_usd_hr / _SECONDS_PER_HOUR


def is_valid_modal_gpu_type(gpu_type: str) -> bool:
    """Return True if gpu_type maps to a Modal GPU spec the adapter knows about."""
    return gpu_type in MODAL_GPU_SPEC_MAP


def resolve_modal_gpu_spec(gpu_type: str) -> str | None:
    """Return the Modal GPU spec string (e.g. 'A10G') for a workbench GPU type.

    Returns None when the GPU type is not recognized — callers must validate
    via `is_valid_modal_gpu_type` first when they need to distinguish missing
    keys from a valid default.
    """
    return MODAL_GPU_SPEC_MAP.get(gpu_type)
