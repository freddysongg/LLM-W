from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

import yaml

from app.core.config import settings
from app.schemas.workbench_config import ExecutionConfig


class UnsupportedEnvironmentError(Exception):
    """Raised when dispatch_training is called for an environment with no adapter."""


class TrainingProcess(ABC):
    """Abstract handle returned by dispatch_training — supports event streaming and cancellation."""

    @property
    @abstractmethod
    def pid(self) -> int | None: ...

    @property
    @abstractmethod
    def stdout(self) -> asyncio.StreamReader | None: ...

    @property
    @abstractmethod
    def stderr(self) -> asyncio.StreamReader | None: ...

    @property
    @abstractmethod
    def returncode(self) -> int | None: ...

    @abstractmethod
    async def wait(self) -> int: ...

    @abstractmethod
    def terminate(self) -> None:
        """Signal cancellation — cooperative cancel flag then forceful termination."""

    @abstractmethod
    def send_signal(self, sig: int) -> None:
        """Forward a signal to the underlying process (Unix only)."""

    @abstractmethod
    def cleanup(self) -> None:
        """Release any resources after the process has exited."""


class LocalTrainingProcess(TrainingProcess):
    """Wraps asyncio.subprocess.Process for local execution."""

    _IS_UNIX: ClassVar[bool] = sys.platform != "win32"

    def __init__(
        self,
        *,
        proc: asyncio.subprocess.Process,
        cancel_flag_path: Path | None,
    ) -> None:
        self._proc = proc
        self._cancel_flag_path = cancel_flag_path

    @property
    def pid(self) -> int | None:
        return self._proc.pid

    @property
    def stdout(self) -> asyncio.StreamReader | None:
        return self._proc.stdout

    @property
    def stderr(self) -> asyncio.StreamReader | None:
        return self._proc.stderr

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode

    async def wait(self) -> int:
        return await self._proc.wait()

    def terminate(self) -> None:
        # On Windows, touch the cooperative cancel flag before forceful termination.
        if not self._IS_UNIX and self._cancel_flag_path is not None:
            with contextlib.suppress(OSError):
                self._cancel_flag_path.touch()
        with contextlib.suppress(ProcessLookupError):
            self._proc.terminate()

    def send_signal(self, sig: int) -> None:
        with contextlib.suppress(ProcessLookupError, OSError):
            self._proc.send_signal(sig)

    def cleanup(self) -> None:
        if self._cancel_flag_path is not None:
            with contextlib.suppress(OSError):
                self._cancel_flag_path.unlink(missing_ok=True)


async def dispatch_training(
    *,
    run_id: str,
    config_path: Path,
    project_dir: Path,
    resume_from_checkpoint: str | None,
) -> TrainingProcess:
    """Dispatch a training job and return a handle for event streaming and cancellation.

    Reads execution.environment from the YAML config at config_path.
    'local' spawns a subprocess using the existing trainer module.
    'modal' raises UnsupportedEnvironmentError until the modal adapter is wired.
    """
    raw_config: dict[str, object] = yaml.safe_load(config_path.read_text()) or {}
    execution_raw = raw_config.get("execution", {})
    execution_dict = execution_raw if isinstance(execution_raw, dict) else {}
    execution = ExecutionConfig.model_validate(execution_dict)

    if execution.environment == "modal":
        raise UnsupportedEnvironmentError(
            "Modal training adapter is not yet available. "
            "Set execution.environment to 'local' or wait for modal adapter support."
        )

    return await _spawn_local_process(
        run_id=run_id,
        config_path=config_path,
        project_dir=project_dir,
        resume_from_checkpoint=resume_from_checkpoint,
    )


_IS_UNIX = sys.platform != "win32"


async def _spawn_local_process(
    *,
    run_id: str,
    config_path: Path,
    project_dir: Path,
    resume_from_checkpoint: str | None,
) -> LocalTrainingProcess:
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "app.services.trainer",
        "--run-id",
        run_id,
        "--config-path",
        str(config_path),
        "--project-dir",
        str(project_dir),
        "--heartbeat-interval",
        str(settings.watchdog_heartbeat_interval_seconds),
    ]
    if resume_from_checkpoint:
        cmd += ["--resume-from-checkpoint", resume_from_checkpoint]

    cancel_flag_path: Path | None = None
    if not _IS_UNIX:
        cancel_flag_path = project_dir / f".cancel_{run_id}"
        cmd += ["--cancel-flag-path", str(cancel_flag_path)]

    subprocess_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(Path(__file__).parent.parent.parent),
        env=subprocess_env,
    )
    return LocalTrainingProcess(proc=proc, cancel_flag_path=cancel_flag_path)
