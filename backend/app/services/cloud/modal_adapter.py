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
    "a100-40gb": "A100",
    "a100-80gb": "A100-80GB",
    "h100": "H100",
}

_WORKSPACE_ROOT = "/workspace"
_WORKSPACE_CONFIGS = f"{_WORKSPACE_ROOT}/configs"
_WORKSPACE_DATASETS = f"{_WORKSPACE_ROOT}/datasets"
_WORKSPACE_CHECKPOINTS = f"{_WORKSPACE_ROOT}/checkpoints"

# backend/ is 4 levels up from this file (cloud/ -> services/ -> app/ -> backend/)
_BACKEND_ROOT = Path(__file__).resolve().parents[3]


class TrainingProcess(Protocol):
    async def read_event(self) -> dict[str, object] | None: ...

    async def cancel(self) -> None: ...

    async def is_alive(self) -> bool: ...

    async def wait(self) -> int: ...


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

        image = self._build_training_image()
        code_mount = modal.Mount.from_local_dir(
            _BACKEND_ROOT,
            remote_path="/root",
            condition=lambda p: (
                "__pycache__" not in p
                and not p.endswith(".pyc")
                and ".venv" not in p
                and "/tests/" not in p
            ),
        )

        gpu_spec = _GPU_TYPE_MAP.get(self._config.gpu_type, "T4")
        # modal.Sandbox.create.aio no longer accepts `mounts` in current stubs;
        # runtime acceptance is validated by integration tests against a live Modal workspace.
        self._sandbox = await modal.Sandbox.create.aio(  # type: ignore[call-arg]
            image=image,
            gpu=gpu_spec,
            volumes={_WORKSPACE_ROOT: self._volume},
            mounts=[code_mount],
            timeout=6 * 3600,
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
        config_path = self._config.config_path
        project_dir = self._config.project_dir
        datasets_dir = project_dir / "datasets"
        configs_dir = project_dir / "configs"

        loop = asyncio.get_running_loop()

        def _sync_upload() -> None:
            with volume.batch_upload() as batch:
                batch.put_file(str(config_path), f"{_WORKSPACE_CONFIGS}/{config_path.name}")
                if datasets_dir.exists():
                    batch.put_directory(str(datasets_dir), _WORKSPACE_DATASETS)
                if configs_dir.exists():
                    batch.put_directory(str(configs_dir), _WORKSPACE_CONFIGS)

        await loop.run_in_executor(None, _sync_upload)

    @staticmethod
    def _build_training_image() -> modal.Image:
        return modal.Image.debian_slim(python_version="3.11").pip_install(
            "torch>=2.2.0",
            "transformers>=4.40.0",
            "peft>=0.10.0",
            "trl>=0.9.0",
            "datasets>=2.0.0",
            "pyyaml>=6.0.0",
            "pydantic>=2.0.0",
            "pydantic-settings>=2.0.0",
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
        local_checkpoints = self._config.project_dir / "checkpoints"
        local_checkpoints.mkdir(parents=True, exist_ok=True)
        volume = self._volume
        loop = asyncio.get_running_loop()

        def _sync_download() -> None:
            try:
                entries = list(volume.listdir(_WORKSPACE_CHECKPOINTS, recursive=True))
            except Exception:
                logger.warning(
                    "No checkpoints found in Modal Volume for run %s",
                    self._config.run_id,
                )
                return
            for entry in entries:
                try:
                    entry_path: str = entry.path
                    # Directory entries end with / — skip, only process files
                    if entry_path.endswith("/"):
                        continue
                    rel = entry_path[len(_WORKSPACE_CHECKPOINTS) :].lstrip("/")
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
