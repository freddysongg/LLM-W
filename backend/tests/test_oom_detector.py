from __future__ import annotations

from app.services.oom_detector import detect_oom


def test_cuda_pattern_detected_on_cuda_device() -> None:
    result = detect_oom(
        device="cuda",
        exit_code=1,
        stderr_tail="RuntimeError: CUDA out of memory. Tried to allocate 256 MiB",
    )
    assert result.is_oom is True
    assert result.trigger == "stderr_regex"
    assert "CUDA out of memory" in result.detail


def test_cuda_pattern_detected_on_modal_device() -> None:
    result = detect_oom(
        device="modal",
        exit_code=1,
        stderr_tail="torch.cuda.OutOfMemoryError: CUDA out of memory",
    )
    assert result.is_oom is True
    assert result.trigger == "stderr_regex"


def test_mps_pattern_detected_on_mps_device() -> None:
    result = detect_oom(
        device="mps",
        exit_code=1,
        stderr_tail="MPS backend out of memory (MPS allocated: 17.00 GB)",
    )
    assert result.is_oom is True
    assert result.trigger == "stderr_regex"
    assert "MPS backend out of memory" in result.detail


def test_cpu_oom_exit_code_137_on_cpu() -> None:
    result = detect_oom(device="cpu", exit_code=137, stderr_tail="")
    assert result.is_oom is True
    assert result.trigger == "exit_code"
    assert "137" in result.detail


def test_cpu_oom_exit_code_neg9_on_cpu() -> None:
    result = detect_oom(device="cpu", exit_code=-9, stderr_tail="")
    assert result.is_oom is True
    assert result.trigger == "exit_code"


def test_modal_exception_takes_precedence() -> None:
    result = detect_oom(
        device="modal",
        exit_code=0,
        stderr_tail="",
        exception_type_name="SandboxOutOfMemoryError",
    )
    assert result.is_oom is True
    assert result.trigger == "modal_exception"
    assert result.detail == "SandboxOutOfMemoryError"


def test_unrelated_failure_is_not_oom() -> None:
    result = detect_oom(
        device="cuda",
        exit_code=1,
        stderr_tail="ImportError: No module named 'foo'",
    )
    assert result.is_oom is False
    assert result.trigger is None


def test_cpu_normal_exit_code_is_not_oom() -> None:
    result = detect_oom(device="cpu", exit_code=1, stderr_tail="generic error")
    assert result.is_oom is False


def test_case_insensitive_cuda_pattern_matches() -> None:
    result = detect_oom(
        device="cuda",
        exit_code=1,
        stderr_tail="cuda Out Of Memory while loading model",
    )
    assert result.is_oom is True
    assert result.trigger == "stderr_regex"
