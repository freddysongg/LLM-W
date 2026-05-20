from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import modal

logger = logging.getLogger(__name__)

_GPU_TYPE_MAP: dict[str, str] = {
    "t4": "T4",
    "a10": "A10G",
    "l40s": "L40S",
    "a100-40gb": "A100",
    "a100-80gb": "A100-80GB",
    "h100": "H100",
}

_DEFAULT_MODAL_GPU: str = "A10G"


def is_valid_modal_gpu_type(gpu_type: str) -> bool:
    """Return True if gpu_type maps to a Modal GPU spec the adapter knows about."""
    return gpu_type in _GPU_TYPE_MAP


def resolve_modal_gpu_spec(gpu_type: str) -> str | None:
    """Return the Modal GPU spec string (e.g. 'A10G') for a workbench GPU type.

    Returns None when the GPU type is not recognized — callers must validate
    via `is_valid_modal_gpu_type` first when they need to distinguish missing
    keys from a valid default.
    """
    return _GPU_TYPE_MAP.get(gpu_type)


_WORKSPACE_ROOT = "/workspace"
_WORKSPACE_CONFIGS = f"{_WORKSPACE_ROOT}/configs"
_WORKSPACE_DATASETS = f"{_WORKSPACE_ROOT}/datasets"

_SANITIZED_DATASET_FILENAME = "sanitized.jsonl"
_SANITIZED_MANIFEST_FILENAME = "sanitized.meta.json"


class SanitizedArtifactMissingError(RuntimeError):
    """Raised when the adapter cannot find a persisted sanitized dataset.

    The orchestrator gate at `_require_sanitized_artifact` should catch this
    earlier; this exception is the defense-in-depth check at the upload
    boundary so raw datasets are never sent even if the gate is bypassed.
    """


@dataclass(frozen=True)
class ModalUploadPlan:
    """Files and directories the adapter will upload to the Modal volume.

    Only the sanitized dataset artifact (and its optional manifest) is
    uploaded under `datasets/`. The raw `datasets/` directory is never sent.
    """

    files: tuple[tuple[Path, str], ...]
    directories: tuple[tuple[Path, str], ...]


def build_modal_upload_plan(*, project_dir: Path, config_path: Path) -> ModalUploadPlan:
    """Return the upload plan for a Modal cloud run.

    Modal runs require `data_policy=sanitized_cloud`, which means a persisted
    sanitized artifact at `datasets/sanitized.jsonl` must exist. Raises when
    the artifact is absent so the upload pipeline cannot send raw data.
    """
    sanitized = project_dir / "datasets" / _SANITIZED_DATASET_FILENAME
    if not sanitized.is_file():
        raise SanitizedArtifactMissingError(
            f"Modal upload requires a sanitized dataset artifact at {sanitized}. "
            "Call POST /api/v1/projects/{project_id}/datasets/sanitize with "
            "persist=true before launching the cloud run."
        )
    files: list[tuple[Path, str]] = [
        (config_path, f"{_WORKSPACE_CONFIGS}/{config_path.name}"),
        (sanitized, f"{_WORKSPACE_DATASETS}/{sanitized.name}"),
    ]
    manifest = project_dir / "datasets" / _SANITIZED_MANIFEST_FILENAME
    if manifest.is_file():
        files.append((manifest, f"{_WORKSPACE_DATASETS}/{manifest.name}"))
    directories: list[tuple[Path, str]] = []
    configs_dir = project_dir / "configs"
    if configs_dir.is_dir():
        directories.append((configs_dir, _WORKSPACE_CONFIGS))
    return ModalUploadPlan(files=tuple(files), directories=tuple(directories))


def _workspace_checkpoints_path(run_id: str) -> str:
    # Matches the per-run layout used by the local trainer (trainer._run_checkpoints_dir)
    return f"{_WORKSPACE_ROOT}/runs/{run_id}/checkpoints"


# backend/ is 4 levels up from this file (cloud/ -> services/ -> app/ -> backend/)
_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _should_ignore_backend_path(path: Path) -> bool:
    # Exclusion predicate for modal.Image.add_local_dir: keeps source code lean by
    # dropping caches, compiled artifacts, virtualenvs, and test fixtures that would
    # otherwise bloat the remote workspace image.
    parts = path.parts
    if "__pycache__" in parts:
        return True
    if path.suffix == ".pyc":
        return True
    if ".venv" in parts:
        return True
    return "tests" in parts


class TrainingProcess(Protocol):
    async def read_event(self) -> dict[str, object] | None: ...

    async def cancel(self) -> None: ...

    async def is_alive(self) -> bool: ...

    async def wait(self) -> int: ...


# Hard ceiling on sandbox lifetime regardless of the configured budget — Modal
# sandboxes cannot run forever. Six hours matches the prior default and is the
# fallback when no per-run budget is supplied.
_MAX_SANDBOX_TIMEOUT_SECONDS: int = 6 * 3600

# Packages installed into the Modal training image. `accelerate` is required by
# the trainer's launch wrapper; `bitsandbytes` is required by QLoRA / 4-bit
# quantization paths — without it `adapters.type=qlora` configs raise at model
# resolution time even though the config validates locally.
_TRAINING_IMAGE_PACKAGES: tuple[str, ...] = (
    "torch>=2.2.0",
    "transformers>=4.40.0",
    "accelerate>=0.30.0",
    "peft>=0.10.0",
    "trl>=0.9.0",
    "datasets>=2.0.0",
    "bitsandbytes>=0.43.0",
    "pyyaml>=6.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
)


@dataclass(frozen=True)
class ModalAdapterConfig:
    run_id: str
    config_path: Path
    project_dir: Path
    gpu_type: str
    modal_token_id: str
    modal_token_secret: str
    heartbeat_path: Path
    heartbeat_interval_seconds: int = 10
    sandbox_timeout_seconds: int = _MAX_SANDBOX_TIMEOUT_SECONDS
    resume_from_checkpoint: str | None = None


class ModalTrainingAdapter:
    """TrainingProcess implementation backed by a Modal cloud sandbox."""

    def __init__(self, *, config: ModalAdapterConfig) -> None:
        self._config = config
        self._sandbox: modal.Sandbox | None = None
        self._process: modal.container_process.ContainerProcess[str] | None = None
        self._stdout_aiter: AsyncIterator[bytes | str] | None = None
        self._is_terminated: bool = False
        self._exit_code: int | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._volume: modal.Volume | None = None

    async def start(self) -> None:
        os.environ["MODAL_TOKEN_ID"] = self._config.modal_token_id
        os.environ["MODAL_TOKEN_SECRET"] = self._config.modal_token_secret

        self._volume = modal.Volume.from_name(
            f"llm-workbench-{self._config.run_id}",
            create_if_missing=True,
        )
        await self._upload_training_data(volume=self._volume)

        image = self._build_training_image().add_local_dir(
            _BACKEND_ROOT,
            remote_path="/root",
            ignore=_should_ignore_backend_path,
        )

        gpu_spec = _GPU_TYPE_MAP.get(self._config.gpu_type, _DEFAULT_MODAL_GPU)
        # Clamp to a sane bound — a misconfigured timeout shouldn't be able to
        # request a sandbox lifetime longer than Modal will actually allow.
        timeout_seconds = min(
            max(self._config.sandbox_timeout_seconds, 60),
            _MAX_SANDBOX_TIMEOUT_SECONDS,
        )
        self._sandbox = await modal.Sandbox.create.aio(
            image=image,
            gpu=gpu_spec,
            volumes={_WORKSPACE_ROOT: self._volume},
            timeout=timeout_seconds,
        )

        config_name = self._config.config_path.name
        cmd = [
            "python",
            "-u",
            "-m",
            "app.services.trainer",
            "--run-id",
            self._config.run_id,
            "--config-path",
            f"{_WORKSPACE_CONFIGS}/{config_name}",
            "--project-dir",
            _WORKSPACE_ROOT,
            "--heartbeat-interval",
            str(self._config.heartbeat_interval_seconds),
        ]
        if self._config.resume_from_checkpoint is not None:
            cmd += ["--resume-from-checkpoint", self._config.resume_from_checkpoint]

        self._process = await self._sandbox.exec.aio(*cmd)
        self._stdout_aiter = self._process.stdout.__aiter__()
        self._heartbeat_task = asyncio.create_task(self._synthesize_heartbeats())

    async def read_event(self) -> dict[str, object] | None:
        if self._stdout_aiter is None:
            return None
        while True:
            try:
                line = await self._stdout_aiter.__anext__()
                raw = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    parsed: dict[str, object] = json.loads(stripped)
                    return parsed
                except json.JSONDecodeError:
                    return {
                        "type": "log",
                        "severity": "debug",
                        "message": stripped,
                        "stage": "",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
            except (StopAsyncIteration, StopIteration):
                self._stdout_aiter = None
                return None

    async def cancel(self) -> None:
        self._is_terminated = True
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
        if self._sandbox is not None:
            try:
                await self._sandbox.terminate.aio()
            except Exception:
                logger.warning(
                    "Failed to terminate Modal sandbox for run %s",
                    self._config.run_id,
                    exc_info=True,
                )

    async def is_alive(self) -> bool:
        if self._is_terminated or self._sandbox is None:
            return False
        try:
            poll_result = await self._sandbox.poll.aio()
            return poll_result is None
        except Exception:
            return False

    async def wait(self) -> int:
        if self._process is not None:
            self._exit_code = await self._process.wait.aio()
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
        if not self._is_terminated:
            await self._download_checkpoints()
        if self._sandbox is not None:
            with contextlib.suppress(Exception):
                await self._sandbox.terminate.aio()
        return self._exit_code if self._exit_code is not None else 1

    async def _upload_training_data(self, *, volume: modal.Volume) -> None:
        plan = build_modal_upload_plan(
            project_dir=self._config.project_dir,
            config_path=self._config.config_path,
        )

        loop = asyncio.get_running_loop()

        def _sync_upload() -> None:
            with volume.batch_upload() as batch:
                for local, remote in plan.files:
                    batch.put_file(str(local), remote)
                for local_dir, remote_dir in plan.directories:
                    batch.put_directory(str(local_dir), remote_dir)

        await loop.run_in_executor(None, _sync_upload)

    @staticmethod
    def _build_training_image() -> modal.Image:
        return modal.Image.debian_slim(python_version="3.11").pip_install(
            *_TRAINING_IMAGE_PACKAGES,
        )

    async def _synthesize_heartbeats(self) -> None:
        """Write synthetic heartbeat files so the watchdog sees the remote job as alive."""
        heartbeat_path = self._config.heartbeat_path
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                await asyncio.sleep(self._config.heartbeat_interval_seconds)
                if not await self.is_alive():
                    break
                payload = {
                    "run_id": self._config.run_id,
                    "pid": 0,
                    "current_step": 0,
                    "total_steps": 0,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "stage": "remote_execution",
                    "metrics": {},
                    "remote": True,
                    "environment": "modal",
                }
                tmp = heartbeat_path.with_suffix(".tmp")
                with contextlib.suppress(OSError):
                    tmp.write_text(json.dumps(payload))
                    tmp.rename(heartbeat_path)
            except asyncio.CancelledError:
                break

    async def _download_checkpoints(self) -> None:
        """Download checkpoint artifacts from Modal Volume to local project storage."""
        if self._volume is None:
            return
        run_id = self._config.run_id
        remote_checkpoints = _workspace_checkpoints_path(run_id)
        local_checkpoints = self._config.project_dir / "runs" / run_id / "checkpoints"
        local_checkpoints.mkdir(parents=True, exist_ok=True)
        volume = self._volume
        loop = asyncio.get_running_loop()

        def _sync_download() -> None:
            try:
                entries = list(volume.listdir(remote_checkpoints, recursive=True))
            except Exception:
                logger.warning(
                    "No checkpoints found in Modal Volume for run %s",
                    run_id,
                )
                return
            for entry in entries:
                try:
                    entry_path: str = entry.path
                    # Directory entries end with / — skip, only process files
                    if entry_path.endswith("/"):
                        continue
                    rel = entry_path[len(remote_checkpoints) :].lstrip("/")
                    local_dest = local_checkpoints / rel
                    local_dest.parent.mkdir(parents=True, exist_ok=True)
                    with local_dest.open("wb") as f:
                        for chunk in volume.read_file(entry_path):
                            f.write(chunk)
                except Exception:
                    logger.warning(
                        "Failed to download checkpoint file %s from Modal Volume",
                        entry.path,
                        exc_info=True,
                    )

        await loop.run_in_executor(None, _sync_download)
