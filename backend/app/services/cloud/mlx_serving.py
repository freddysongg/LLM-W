"""Local MLX-LM HTTP server supervisor for Apple Silicon.

This adapter spawns `python -m mlx_lm.server` as a subprocess, polls
`/v1/models` for readiness, and exposes the same lifecycle shape
(`start / read_event / cancel / is_alive / wait`) as
`ModalTrainingAdapter` so the rest of the orchestration layer can manage
it identically.

Two contracts the rest of the codebase depends on:

1. **Lazy import.** `mlx_lm` is imported only inside `start()` so base/local
   installs without the optional `serving` extra still import this module
   cleanly. Consumers must place `MLXServingAdapter` behind `TYPE_CHECKING`
   if they want strict typing without forcing the dependency at import.

2. **Adapter format is MLX-only at this layer.** The registry converts peft
   adapters to MLX format before constructing :class:`MLXServingConfig` (see
   `mlx_adapter_conversion.py`). This adapter therefore assumes
   `adapter_path` already points at an MLX-format directory; it only refuses
   the combination of any adapter against a non-MLX base model, because
   `mlx_lm.server` cannot host a HuggingFace base regardless of adapter shape.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import platform
import socket
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

import httpx

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "localhost"})

_MLX_FORMAT_HINTS: tuple[str, ...] = ("mlx-community/", "mlx_community/")

_CANCEL_GRACE_SECONDS: float = 5.0
_HEALTH_POLL_INTERVAL_SECONDS: float = 0.5
_HEALTH_PROBE_TIMEOUT_SECONDS: float = 3.0


class UnsupportedServingPlatformError(Exception):
    """Raised when MLX serving is attempted on a non-Darwin / non-arm64 host."""

    def __init__(self, *, system: str, machine: str) -> None:
        super().__init__(
            f"MLX serving requires Darwin/arm64 (Apple Silicon). "
            f"Detected: system={system!r} machine={machine!r}."
        )
        self.system = system
        self.machine = machine


class MLXNotInstalledError(Exception):
    """Raised when `mlx_lm` is not installed but a serve was attempted."""

    def __init__(self) -> None:
        super().__init__(
            "MLX serving requires the `mlx-lm` optional dependency. "
            "Install with 'pip install -e \".[serving]\"' on Apple Silicon."
        )


class MLXServerStartupTimeoutError(Exception):
    """Raised when the subprocess starts but never serves a 200 on /v1/models."""

    def __init__(self, *, timeout_seconds: int, tail: str) -> None:
        super().__init__(
            f"mlx_lm.server did not become ready within {timeout_seconds}s. "
            f"Last stderr lines: {tail}"
        )
        self.timeout_seconds = timeout_seconds
        self.tail = tail


class ServingStartupError(Exception):
    """Raised when the subprocess fails to spawn or the port is unavailable."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AdapterConversionUnsupportedError(Exception):
    """Raised when an adapter cannot be loaded for the requested serving model.

    Triggered in two situations:

    * The base model is not MLX-format. ``mlx_lm.server`` cannot host a
      HuggingFace base regardless of adapter format, so the operator must
      point ``serving_model_id`` at an MLX-format model
      (e.g. ``mlx-community/...``).
    * The adapter is a peft directory that the converter rejected (QLoRA,
      non-``"none"`` bias, non-LoRA peft type, or non-standard tensor keys).
      The originating
      :class:`~app.services.cloud.mlx_adapter_conversion.UnsupportedPeftAdapterError`
      is chained as ``__cause__``.
    """

    def __init__(self, *, serving_model_id: str, reason: str | None = None) -> None:
        message = (
            f"Cannot load adapter against base model {serving_model_id!r}. "
            "Point serving_model_id at an MLX-format model "
            "(e.g. mlx-community/...) or supply a peft LoRA adapter the "
            "converter can translate."
        )
        if reason:
            message = f"{message} Details: {reason}"
        super().__init__(message)
        self.serving_model_id = serving_model_id
        self.reason = reason


class _SubprocessLike(Protocol):
    """The subset of asyncio.subprocess.Process this module relies on.

    Declared as a Protocol so tests can substitute a fake without inheriting
    from a private asyncio class.
    """

    @property
    def returncode(self) -> int | None: ...

    @property
    def pid(self) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    async def wait(self) -> int: ...


class ServingProcess(Protocol):
    """Lifecycle contract for any serving backend (MLX local, future remote)."""

    async def start(self) -> None: ...

    async def read_event(self) -> dict[str, object] | None: ...

    async def cancel(self) -> None: ...

    async def is_alive(self) -> bool: ...

    async def wait(self) -> int: ...

    @property
    def base_url(self) -> str: ...


def _current_system() -> str:
    return platform.system()


def _current_machine() -> str:
    return platform.machine()


def _import_mlx_lm() -> object:
    """Lazy import isolated in a function so tests can patch the import path."""
    import mlx_lm

    return mlx_lm


def is_mlx_format_model(serving_model_id: str) -> bool:
    """Heuristic check: is this id likely an MLX-format model?

    True when the id starts with a known MLX namespace prefix or resolves to a
    local directory. False for raw HuggingFace ids (e.g. `Qwen/...`). v1 uses
    this to gate adapter loading and refuse adapter+non-MLX-base combinations.
    """
    if any(serving_model_id.startswith(prefix) for prefix in _MLX_FORMAT_HINTS):
        return True
    candidate = Path(serving_model_id)
    return bool(candidate.exists() and candidate.is_dir())


def reserve_free_port(*, host: str) -> int:
    """Bind a probe socket on port 0, capture the kernel-assigned port, release.

    There is a tiny TOCTOU window before the real subprocess re-binds. In
    practice this only matters under concurrent serve starts, which v1 already
    forbids via the capacity cap in the registry.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind((host, 0))
        assigned_port: int = probe.getsockname()[1]
    finally:
        probe.close()
    return assigned_port


def build_server_argv(*, config: MLXServingConfig, port: int) -> list[str]:
    """Construct the argv passed to `asyncio.create_subprocess_exec`."""
    argv: list[str] = [
        sys.executable,
        "-u",
        "-m",
        "mlx_lm.server",
        "--model",
        config.serving_model_id,
        "--host",
        config.host,
        "--port",
        str(port),
        "--log-level",
        config.log_level.upper(),
    ]
    if config.adapter_path is not None:
        argv.extend(["--adapter-path", str(config.adapter_path)])
    if config.trust_remote_code:
        argv.append("--trust-remote-code")
    return argv


@dataclass(frozen=True)
class MLXServingConfig:
    project_id: str
    serving_model_id: str
    host: str = "127.0.0.1"
    port: int = 0
    adapter_path: Path | None = None
    trust_remote_code: bool = False
    max_tokens: int = 1024
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    startup_timeout_seconds: int = 120

    def __post_init__(self) -> None:
        if self.host not in _LOOPBACK_HOSTS:
            raise ValueError(
                f"MLX serving host must be a loopback address (got {self.host!r}). "
                "Binding to non-loopback interfaces is explicitly forbidden for v1."
            )


@dataclass
class _ServingState:
    """Mutable fields owned by the adapter. Held separately so the public
    config dataclass remains frozen.
    """

    proc: _SubprocessLike | None = None
    port: int = 0
    is_started: bool = False
    is_terminated: bool = False
    event_queue: asyncio.Queue[dict[str, object] | None] = field(
        default_factory=lambda: asyncio.Queue()
    )
    stderr_tail: list[str] = field(default_factory=list)
    stdout_pump_task: asyncio.Task[None] | None = None
    stderr_pump_task: asyncio.Task[None] | None = None


class MLXServingAdapter:
    """Local MLX-LM HTTP server process supervisor."""

    def __init__(self, *, config: MLXServingConfig) -> None:
        self._config = config
        self._state = _ServingState()

    @property
    def base_url(self) -> str:
        if not self._state.is_started:
            raise RuntimeError("base_url is undefined until start() succeeds")
        return f"http://{self._config.host}:{self._state.port}"

    @property
    def pid(self) -> int | None:
        proc = self._state.proc
        if proc is None:
            return None
        return proc.pid

    async def start(self) -> None:
        self._guard_platform()
        self._guard_adapter_compatibility()
        try:
            _import_mlx_lm()
        except ImportError as exc:
            raise MLXNotInstalledError() from exc

        try:
            port = reserve_free_port(host=self._config.host)
        except OSError as exc:
            raise ServingStartupError(
                f"Could not reserve a free port for mlx_lm.server: {exc}"
            ) from exc
        self._state.port = port

        argv = build_server_argv(config=self._config, port=port)
        env = self._build_subprocess_env()
        try:
            proc = await _spawn_subprocess(argv=argv, env=env)
        except OSError as exc:
            raise ServingStartupError(
                f"Failed to spawn mlx_lm.server subprocess: {exc}"
            ) from exc
        self._state.proc = proc
        self._attach_stream_pumps(proc=proc)

        ready = await self._await_server_ready(port=port)
        if not ready:
            await self._force_terminate(proc=proc)
            tail = "\n".join(self._state.stderr_tail[-50:])
            raise MLXServerStartupTimeoutError(
                timeout_seconds=self._config.startup_timeout_seconds,
                tail=tail,
            )

        self._state.is_started = True
        await self._state.event_queue.put(
            {
                "type": "serving_ready",
                "port": port,
                "base_url": f"http://{self._config.host}:{port}",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    async def read_event(self) -> dict[str, object] | None:
        event = await self._state.event_queue.get()
        return event

    async def cancel(self) -> None:
        self._state.is_terminated = True
        proc = self._state.proc
        if proc is None:
            return
        await self._force_terminate(proc=proc)
        await self._cancel_pump_tasks()
        await self._state.event_queue.put(
            {
                "type": "serving_stopped",
                "exit_code": proc.returncode if proc.returncode is not None else -1,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        await self._state.event_queue.put(None)

    async def is_alive(self) -> bool:
        return self.is_subprocess_alive

    @property
    def is_subprocess_alive(self) -> bool:
        """Sync alive check usable from non-async paths like the registry."""
        if self._state.is_terminated:
            return False
        proc = self._state.proc
        if proc is None:
            return False
        return proc.returncode is None

    @property
    def last_exit_code(self) -> int | None:
        proc = self._state.proc
        if proc is None:
            return None
        return proc.returncode

    async def wait(self) -> int:
        proc = self._state.proc
        if proc is None:
            return 1
        exit_code = await proc.wait()
        await self._cancel_pump_tasks()
        return exit_code

    def _guard_platform(self) -> None:
        system = _current_system()
        machine = _current_machine()
        if system != "Darwin" or machine != "arm64":
            raise UnsupportedServingPlatformError(system=system, machine=machine)

    def _guard_adapter_compatibility(self) -> None:
        if self._config.adapter_path is None:
            return
        if not is_mlx_format_model(self._config.serving_model_id):
            raise AdapterConversionUnsupportedError(
                serving_model_id=self._config.serving_model_id,
            )

    def _build_subprocess_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.setdefault("PYTHONUNBUFFERED", "1")
        return env

    def _attach_stream_pumps(self, *, proc: _SubprocessLike) -> None:
        stdout = getattr(proc, "stdout", None)
        stderr = getattr(proc, "stderr", None)
        if stdout is not None:
            self._state.stdout_pump_task = asyncio.create_task(
                self._pump_stream(stream=stdout, severity="info"),
                name=f"mlx-serving-stdout-{self._config.project_id}",
            )
        if stderr is not None:
            self._state.stderr_pump_task = asyncio.create_task(
                self._pump_stream(stream=stderr, severity="warning"),
                name=f"mlx-serving-stderr-{self._config.project_id}",
            )

    async def _pump_stream(
        self,
        *,
        stream: object,
        severity: Literal["info", "warning"],
    ) -> None:
        readline = getattr(stream, "readline", None)
        if readline is None:
            return
        while True:
            try:
                raw = await readline()
            except (asyncio.CancelledError, ConnectionResetError):
                return
            if not raw:
                return
            line = raw.decode("utf-8", errors="replace").strip() if isinstance(raw, bytes) else raw
            if not line:
                continue
            if severity == "warning":
                self._state.stderr_tail.append(line)
                if len(self._state.stderr_tail) > 200:
                    del self._state.stderr_tail[:100]
            await self._state.event_queue.put(
                {
                    "type": "log",
                    "severity": severity,
                    "message": line,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

    async def _await_server_ready(self, *, port: int) -> bool:
        deadline = asyncio.get_event_loop().time() + self._config.startup_timeout_seconds
        base_url = f"http://{self._config.host}:{port}"
        while asyncio.get_event_loop().time() < deadline:
            proc = self._state.proc
            if proc is not None and proc.returncode is not None:
                return False
            ok = await _probe_models_endpoint(
                base_url=base_url,
                timeout_s=_HEALTH_PROBE_TIMEOUT_SECONDS,
            )
            if ok:
                return True
            await asyncio.sleep(_HEALTH_POLL_INTERVAL_SECONDS)
        return False

    async def _force_terminate(self, *, proc: _SubprocessLike) -> None:
        if proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=_CANCEL_GRACE_SECONDS)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.kill()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(proc.wait(), timeout=_CANCEL_GRACE_SECONDS)

    async def _cancel_pump_tasks(self) -> None:
        for task in (self._state.stdout_pump_task, self._state.stderr_pump_task):
            if task is None or task.done():
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def _spawn_subprocess(
    *,
    argv: list[str],
    env: dict[str, str],
) -> _SubprocessLike:
    """Indirection point so tests can replace subprocess creation wholesale."""
    return await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )


async def _probe_models_endpoint(*, base_url: str, timeout_s: float) -> bool:
    """Return True when GET /v1/models returns 200."""
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            response = await client.get(f"{base_url}/v1/models")
        except httpx.HTTPError:
            return False
    return response.status_code == 200
