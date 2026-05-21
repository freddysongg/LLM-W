from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

OomTrigger = Literal["modal_exception", "stderr_regex", "exit_code"]


@dataclass(frozen=True)
class OomDetectionResult:
    is_oom: bool
    trigger: OomTrigger | None
    detail: str


_CUDA_PATTERN = re.compile(
    r"CUDA out of memory|torch\.cuda\.OutOfMemoryError|CUDNN_STATUS_NOT_ENOUGH_MEMORY",
    re.IGNORECASE,
)
_MPS_PATTERN = re.compile(r"MPS backend out of memory", re.IGNORECASE)

# Linux SIGKILL convention: process killed by oom-killer typically reports
# exit code 137 (128 + 9). Some asyncio harnesses surface -9 instead, so
# we match either form when the device is cpu (no GPU pattern applies).
_CPU_OOM_EXIT_CODES: frozenset[int] = frozenset({137, -9})


def detect_oom(
    *,
    device: str,
    exit_code: int,
    stderr_tail: str,
    exception_type_name: str | None = None,
) -> OomDetectionResult:
    """Classify a trainer failure as OOM or not.

    Detection order: structured Modal exception (most authoritative) → device-specific
    stderr pattern → CPU exit code. Unknown failures return is_oom=False so the
    existing failure path stays in charge.
    """
    if exception_type_name and "OutOfMemory" in exception_type_name:
        return OomDetectionResult(
            is_oom=True,
            trigger="modal_exception",
            detail=exception_type_name,
        )

    normalized_device = device.lower()

    if normalized_device in ("cuda", "modal"):
        cuda_match = _CUDA_PATTERN.search(stderr_tail)
        if cuda_match is not None:
            return OomDetectionResult(
                is_oom=True,
                trigger="stderr_regex",
                detail=cuda_match.group(0),
            )

    if normalized_device == "mps":
        mps_match = _MPS_PATTERN.search(stderr_tail)
        if mps_match is not None:
            return OomDetectionResult(
                is_oom=True,
                trigger="stderr_regex",
                detail=mps_match.group(0),
            )

    if normalized_device == "cpu" and exit_code in _CPU_OOM_EXIT_CODES:
        return OomDetectionResult(
            is_oom=True,
            trigger="exit_code",
            detail=f"exit_code={exit_code}",
        )

    return OomDetectionResult(is_oom=False, trigger=None, detail="")
