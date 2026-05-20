from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import modal
import yaml

from app.core.config import settings

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


_MODAL_UPLOAD_STAGING_DIR = ".modal-uploads"


def _rewrite_config_for_modal_upload(
    *,
    src_config_path: Path,
    dst_path: Path,
    normalized: bool | None = None,
) -> None:
    """Write a copy of the config whose dataset section points at the uploaded
    sanitized artifact.

    The remote trainer reads `dataset.source` / `dataset.dataset_id` from the
    config we upload. Without this rewrite, a `local_jsonl` config would point
    at a host path that does not exist in the Modal sandbox, and a
    `huggingface` config would re-download the raw dataset, bypassing the
    `sanitized_cloud` data policy.

    `normalized` reflects the sanitizer manifest's `normalized` flag. Only when
    `normalized is True` do we force `format="openai"` — otherwise the original
    format is preserved (the sanitizer wrote rows in the source schema).
    """
    raw = yaml.safe_load(src_config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"Config at {src_config_path} did not parse as a mapping (got {type(raw).__name__})."
        )
    dataset_section = raw.get("dataset", {})
    if not isinstance(dataset_section, dict):
        dataset_section = {}
    rewritten_dataset: dict[str, object] = {
        **dataset_section,
        "source": "local_jsonl",
        "dataset_id": f"{_WORKSPACE_DATASETS}/{_SANITIZED_DATASET_FILENAME}",
    }
    if normalized is True:
        rewritten_dataset["format"] = "openai"
    raw["dataset"] = rewritten_dataset
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dst_path.with_suffix(dst_path.suffix + ".tmp")
    tmp_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    os.replace(tmp_path, dst_path)


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
    # Stage a rewritten config under project_dir/.modal-uploads/ so the
    # uploaded file points dataset.source/dataset_id at the sanitized artifact
    # instead of carrying the host's raw source. The remote name continues to
    # match the original so the trainer's --config-path argument is unchanged.
    staging_path = project_dir / _MODAL_UPLOAD_STAGING_DIR / config_path.name
    normalized_flag = _read_sanitized_normalized_flag(project_dir=project_dir)
    _rewrite_config_for_modal_upload(
        src_config_path=config_path,
        dst_path=staging_path,
        normalized=normalized_flag,
    )

    files: list[tuple[Path, str]] = [
        (staging_path, f"{_WORKSPACE_CONFIGS}/{config_path.name}"),
        (sanitized, f"{_WORKSPACE_DATASETS}/{sanitized.name}"),
    ]
    manifest = project_dir / "datasets" / _SANITIZED_MANIFEST_FILENAME
    if manifest.is_file():
        files.append((manifest, f"{_WORKSPACE_DATASETS}/{manifest.name}"))
    # Intentionally no directory uploads. Uploading project_dir/configs/ would
    # clobber the rewritten config above with its raw-source original.
    return ModalUploadPlan(files=tuple(files), directories=())


def _workspace_checkpoints_path(run_id: str) -> str:
    # Matches the per-run layout used by the local trainer (trainer._run_checkpoints_dir)
    return f"{_WORKSPACE_ROOT}/runs/{run_id}/checkpoints"


def _read_sanitized_content_hash(*, project_dir: Path) -> str | None:
    """Return the sanitized artifact's content hash from its local manifest, if present.

    The manifest is written next to `sanitized.jsonl` whenever the sanitizer
    runs with persist=true. Absent manifest → caller must upload (no hash to
    compare). Malformed manifest → treat as missing rather than crashing.
    """
    manifest_path = project_dir / "datasets" / _SANITIZED_MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    try:
        parsed = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    content_hash = parsed.get("content_hash")
    if isinstance(content_hash, str) and content_hash:
        return content_hash
    return None


def _read_sanitized_normalized_flag(*, project_dir: Path) -> bool | None:
    """Return the sanitizer manifest's `normalized` boolean if present.

    Returns None when the manifest is missing, malformed, or the key is absent
    or non-boolean. Callers treat None as "do not assume openai shape" so the
    rewritten config preserves the user's original `dataset.format`.
    """
    manifest_path = project_dir / "datasets" / _SANITIZED_MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    try:
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    value = parsed.get("normalized")
    return value if isinstance(value, bool) else None


def _remote_sanitized_hash_matches(*, volume: modal.Volume, expected_hash: str) -> bool:
    """Return True iff the remote sanitized manifest carries the same content hash.

    Best-effort: any read error means we fall through to the safer behavior of
    re-uploading (returns False) rather than skipping an upload we should do.
    """
    remote_manifest = f"{_WORKSPACE_DATASETS}/{_SANITIZED_MANIFEST_FILENAME}"
    try:
        chunks = list(volume.read_file(remote_manifest))
    except Exception:
        return False
    try:
        raw = b"".join(chunks).decode("utf-8", errors="replace")
        parsed = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(parsed, dict):
        return False
    return parsed.get("content_hash") == expected_hash


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


# Cap on stderr tail captured for OOM detection. The detector only needs the
# trailing message, and the orchestrator persists this string into the failure
# reason — keeping it bounded prevents a 100MB stderr from blowing up the DB row.
_STDERR_TAIL_MAX_BYTES: int = 4096

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
    sandbox_timeout_seconds: int = field(
        default_factory=lambda: settings.max_sandbox_timeout_seconds
    )
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
        # Surface trailing stderr and any Modal-specific exception class name so
        # the orchestrator's OOM classifier can disambiguate container-OOM kills
        # from generic exits.
        self._stderr_tail: str = ""
        self._exception_type_name: str | None = None

    @property
    def last_exit_code(self) -> int | None:
        return self._exit_code

    @property
    def last_stderr_tail(self) -> str:
        return self._stderr_tail

    @property
    def last_exception_type_name(self) -> str | None:
        return self._exception_type_name

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
            settings.max_sandbox_timeout_seconds,
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
            try:
                self._exit_code = await self._process.wait.aio()
            except Exception as exc:
                # Modal raises typed exceptions for sandbox-level failures (e.g.
                # OOM kills, infra timeouts). Capture the class name so the
                # orchestrator can classify the failure without speculating on
                # Modal's internal exception class hierarchy.
                self._exception_type_name = type(exc).__name__
                logger.warning(
                    "Modal process.wait failed for run %s: %s",
                    self._config.run_id,
                    type(exc).__name__,
                    exc_info=True,
                )
            await self._capture_stderr_tail()
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

    async def _capture_stderr_tail(self) -> None:
        if self._process is None:
            return
        stderr_stream = getattr(self._process, "stderr", None)
        if stderr_stream is None:
            return
        try:
            chunks: list[str] = []
            async for line in stderr_stream:
                text = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
                chunks.append(text)
            if chunks:
                self._stderr_tail = "".join(chunks)[-_STDERR_TAIL_MAX_BYTES:]
        except Exception:
            logger.debug(
                "Failed to read Modal stderr for run %s",
                self._config.run_id,
                exc_info=True,
            )

    async def _upload_training_data(self, *, volume: modal.Volume) -> None:
        plan = build_modal_upload_plan(
            project_dir=self._config.project_dir,
            config_path=self._config.config_path,
        )

        loop = asyncio.get_running_loop()
        local_hash = _read_sanitized_content_hash(project_dir=self._config.project_dir)

        def _sync_upload() -> None:
            # On retry, the sandbox is new but the named Volume persists. Skip
            # re-uploading the sanitized artifact if its content hash matches the
            # one already on the volume — uploads are network-expensive and the
            # artifact is immutable per spec.
            if local_hash is not None and _remote_sanitized_hash_matches(
                volume=volume, expected_hash=local_hash
            ):
                logger.info(
                    "Skipping sanitized artifact upload for run %s — volume hash matches",
                    self._config.run_id,
                )
                return
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
