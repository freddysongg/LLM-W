from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import yaml

from app.core.config import settings
from app.schemas.workbench_config import ExecutionConfig
from app.services import settings_service

if TYPE_CHECKING:
    # Avoid eager import of `modal` (an optional cloud extra). Tests and local-only
    # installs would otherwise fail at import time before any route is served.
    from app.services.cloud.modal_adapter import ModalTrainingAdapter

logger = logging.getLogger(__name__)


class UnsupportedEnvironmentError(Exception):
    """Raised when dispatch_training is called for an environment with no adapter."""


class ModalCredentialsMissingError(UnsupportedEnvironmentError):
    """Raised when execution.environment == 'modal' but no Modal token is configured."""


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


class ModalTrainingProcess(TrainingProcess):
    """Bridges a ModalTrainingAdapter into the TrainingProcess interface.

    The Modal adapter emits typed event dicts via `read_event()`. The orchestrator
    iterates `proc.stdout` expecting newline-delimited JSON, so a pump task
    serializes each event back to a JSON line and feeds a local
    `asyncio.StreamReader`. This keeps the orchestrator unaware of remote vs.
    local execution.
    """

    def __init__(
        self,
        *,
        adapter: ModalTrainingAdapter,
        stdout_reader: asyncio.StreamReader,
    ) -> None:
        self._adapter = adapter
        self._stdout = stdout_reader
        self._returncode: int | None = None
        self._pump_task: asyncio.Task[None] | None = None
        self._cancel_task: asyncio.Task[None] | None = None
        self._terminate_requested: bool = False

    @property
    def adapter(self) -> ModalTrainingAdapter:
        return self._adapter

    @property
    def terminate_requested(self) -> bool:
        return self._terminate_requested

    @property
    def pid(self) -> int | None:
        # Modal sandboxes do not expose a meaningful local PID.
        return None

    @property
    def stdout(self) -> asyncio.StreamReader | None:
        return self._stdout

    @property
    def stderr(self) -> asyncio.StreamReader | None:
        # Modal adapter funnels stderr into the same event stream.
        return None

    @property
    def returncode(self) -> int | None:
        return self._returncode

    def attach_pump_task(self, task: asyncio.Task[None]) -> None:
        self._pump_task = task

    async def wait(self) -> int:
        if self._pump_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._pump_task
        rc = await self._adapter.wait()
        self._returncode = rc
        return rc

    def terminate(self) -> None:
        # Modal cancel is async; schedule it on the running loop so the
        # synchronous orchestrator.cancel_run contract holds. The pump uses
        # `terminate_requested` to inject a synthetic cancelled terminal event
        # before EOF so the orchestrator's terminal-status fallback does not
        # rewrite the DB row from `cancelled` back to `failed`.
        self._terminate_requested = True
        self._cancel_task = asyncio.create_task(self._adapter.cancel())

    def send_signal(self, sig: int) -> None:
        # Modal sandbox processes do not accept POSIX signal forwarding.
        return None

    def cleanup(self) -> None:
        if self._pump_task is not None and not self._pump_task.done():
            self._pump_task.cancel()


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
    'modal' provisions a Modal sandbox via ModalTrainingAdapter and bridges its
    JSON-line event stream into a TrainingProcess-shaped handle.
    """
    raw_config: dict[str, object] = yaml.safe_load(config_path.read_text()) or {}
    execution_raw = raw_config.get("execution", {})
    execution_dict = execution_raw if isinstance(execution_raw, dict) else {}
    execution = ExecutionConfig.model_validate(execution_dict)

    if execution.environment == "modal":
        return await _spawn_modal_process(
            run_id=run_id,
            config_path=config_path,
            project_dir=project_dir,
            resume_from_checkpoint=resume_from_checkpoint,
            execution=execution,
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


async def _spawn_modal_process(
    *,
    run_id: str,
    config_path: Path,
    project_dir: Path,
    resume_from_checkpoint: str | None,
    execution: ExecutionConfig,
) -> ModalTrainingProcess:
    credentials = settings_service.get_modal_credentials()
    if credentials is None:
        raise ModalCredentialsMissingError(
            "Modal training requires modal_token_id and modal_token_secret to be set "
            "in workbench settings. Configure them via /api/v1/settings before launching "
            "a cloud run."
        )

    # Deferred import: `modal` lives behind the optional `cloud` extra. Importing
    # it here keeps base/local installs from failing at backend startup.
    try:
        from app.services.cloud.modal_adapter import (
            ModalAdapterConfig,
            ModalTrainingAdapter,
        )
    except ImportError as exc:
        raise UnsupportedEnvironmentError(
            "Modal cloud extras are not installed. Install with "
            "'pip install llm-workbench-backend[cloud]' to enable Modal training."
        ) from exc

    modal_token_id, modal_token_secret = credentials
    adapter_config = ModalAdapterConfig(
        run_id=run_id,
        config_path=config_path,
        project_dir=project_dir,
        gpu_type=execution.modal_gpu_type,
        modal_token_id=modal_token_id,
        modal_token_secret=modal_token_secret,
        heartbeat_path=project_dir / ".heartbeat",
        heartbeat_interval_seconds=settings.watchdog_heartbeat_interval_seconds,
        sandbox_timeout_seconds=execution.max_run_minutes * 60,
        resume_from_checkpoint=resume_from_checkpoint,
    )
    adapter = ModalTrainingAdapter(config=adapter_config)
    await adapter.start()

    stdout_reader = asyncio.StreamReader()
    process = ModalTrainingProcess(adapter=adapter, stdout_reader=stdout_reader)
    pump_task = asyncio.create_task(
        _pump_modal_events(process=process, reader=stdout_reader),
        name=f"modal-event-pump-{run_id}",
    )
    process.attach_pump_task(pump_task)
    return process


async def _pump_modal_events(
    *,
    process: ModalTrainingProcess,
    reader: asyncio.StreamReader,
) -> None:
    """Serialize ModalTrainingAdapter events as JSON lines into a StreamReader.

    Bridges read_event() into the byte-stream the orchestrator expects. When
    `terminate()` was called before the adapter drained, the pump synthesizes a
    final `complete` event with `status="cancelled"` so the orchestrator records
    cancellation instead of mapping the non-zero sandbox exit code to `failed`.
    """
    adapter = process.adapter
    try:
        while True:
            event = await adapter.read_event()
            if event is None:
                break
            line = (json.dumps(event) + "\n").encode("utf-8")
            reader.feed_data(line)
    except Exception as exc:
        logger.warning("Modal event pump failed", exc_info=exc)
    finally:
        if process.terminate_requested:
            cancelled_line = (
                json.dumps({"type": "complete", "status": "cancelled"}) + "\n"
            ).encode("utf-8")
            with contextlib.suppress(Exception):
                reader.feed_data(cancelled_line)
        reader.feed_eof()
