"""Accumulator + atomic JSON writer for voice session transcripts and tool traces.

A `TranscriptWriter` is a per-session, single-writer record of three streams
ordered by index: assistant + user transcript lines, tool calls, and pipeline
errors. The writer is purely synchronous — flushing is cheap enough that there
is no benefit to deferring it to a thread. Atomic writes follow the existing
repo convention (`trainer._write_heartbeat`, `trainer._atomic_checkpoint_write`):
write to a `.tmp` sibling then `Path.replace` onto the final path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

TranscriptRole = Literal["user", "assistant"]


_SCHEMA_VERSION: int = 1


@dataclass(frozen=True)
class TranscriptEntry:
    """One spoken or written turn from either the user or the assistant."""

    role: TranscriptRole
    text: str
    started_at_iso: str
    ended_at_iso: str
    is_interim: bool


@dataclass(frozen=True)
class ToolTraceEntry:
    """One captured tool invocation with arguments, result, and timing."""

    tool_call_id: str
    name: str
    arguments: dict[str, object]
    result: dict[str, object]
    started_at_iso: str
    ended_at_iso: str
    is_error: bool
    duration_ms: int


@dataclass(frozen=True)
class TranscriptErrorEntry:
    """One pipeline-level error captured during the session."""

    error_code: str
    message: str
    captured_at_iso: str


@dataclass(frozen=True)
class TranscriptSnapshot:
    """Immutable view of accumulator state for tests and observers."""

    session_id: str
    started_at_iso: str
    ended_at_iso: str | None
    termination_reason: str | None
    config_snapshot: dict[str, str]
    transcript: tuple[TranscriptEntry, ...]
    tool_trace: tuple[ToolTraceEntry, ...]
    errors: tuple[TranscriptErrorEntry, ...]


@dataclass
class _MutableAccumulator:
    transcript: list[TranscriptEntry] = field(default_factory=list)
    tool_trace: list[ToolTraceEntry] = field(default_factory=list)
    errors: list[TranscriptErrorEntry] = field(default_factory=list)
    ended_at_iso: str | None = None
    termination_reason: str | None = None


def _parse_iso_to_epoch_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    return int(parsed.timestamp() * 1000)


def _atomic_replace(*, source: Path, target: Path) -> None:
    """Move `source` to `target` atomically. Indirection exists so tests can spy on it."""
    source.replace(target)


class TranscriptWriter:
    """Per-session accumulator that serializes to disk atomically.

    Construction does not touch disk. The first `flush()` creates the parent
    directory and writes the JSON artifact. Subsequent flushes overwrite via the
    standard tmp-write + rename dance.
    """

    def __init__(
        self,
        *,
        session_id: str,
        artifact_path: Path,
        started_at_iso: str,
        config_snapshot: dict[str, str],
    ) -> None:
        self._session_id = session_id
        self._artifact_path = artifact_path
        self._started_at_iso = started_at_iso
        self._config_snapshot = dict(config_snapshot)
        self._state = _MutableAccumulator()

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def artifact_path(self) -> Path:
        return self._artifact_path

    def record_transcript(self, entry: TranscriptEntry) -> None:
        self._state.transcript.append(entry)

    def record_tool_call(
        self,
        *,
        tool_call_id: str,
        name: str,
        arguments: dict[str, object],
        result: dict[str, object],
        started_at_iso: str,
        ended_at_iso: str,
        is_error: bool,
    ) -> None:
        started_ms = _parse_iso_to_epoch_ms(started_at_iso)
        ended_ms = _parse_iso_to_epoch_ms(ended_at_iso)
        duration_ms = max(0, ended_ms - started_ms)
        self._state.tool_trace.append(
            ToolTraceEntry(
                tool_call_id=tool_call_id,
                name=name,
                arguments=dict(arguments),
                result=dict(result),
                started_at_iso=started_at_iso,
                ended_at_iso=ended_at_iso,
                is_error=is_error,
                duration_ms=duration_ms,
            )
        )

    def record_error(self, *, error_code: str, message: str) -> None:
        self._state.errors.append(
            TranscriptErrorEntry(
                error_code=error_code,
                message=message,
                captured_at_iso=datetime.now().astimezone().isoformat(),
            )
        )

    def finalize(self, *, ended_at_iso: str, termination_reason: str) -> None:
        self._state.ended_at_iso = ended_at_iso
        self._state.termination_reason = termination_reason

    def snapshot(self) -> TranscriptSnapshot:
        return TranscriptSnapshot(
            session_id=self._session_id,
            started_at_iso=self._started_at_iso,
            ended_at_iso=self._state.ended_at_iso,
            termination_reason=self._state.termination_reason,
            config_snapshot=dict(self._config_snapshot),
            transcript=tuple(self._state.transcript),
            tool_trace=tuple(self._state.tool_trace),
            errors=tuple(self._state.errors),
        )

    def flush(self) -> None:
        payload = self._serialize()
        self._artifact_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._artifact_path.with_name(self._artifact_path.name + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2))
        _atomic_replace(source=tmp_path, target=self._artifact_path)

    def _serialize(self) -> dict[str, object]:
        transcript_entries: list[dict[str, object]] = [
            {
                "index": index,
                "role": entry.role,
                "text": entry.text,
                "started_at": entry.started_at_iso,
                "ended_at": entry.ended_at_iso,
                "is_interim": entry.is_interim,
            }
            for index, entry in enumerate(self._state.transcript)
        ]
        tool_trace_entries: list[dict[str, object]] = [
            {
                "index": index,
                "tool_call_id": entry.tool_call_id,
                "name": entry.name,
                "arguments": entry.arguments,
                "result": entry.result,
                "started_at": entry.started_at_iso,
                "ended_at": entry.ended_at_iso,
                "duration_ms": entry.duration_ms,
                "is_error": entry.is_error,
            }
            for index, entry in enumerate(self._state.tool_trace)
        ]
        error_entries: list[dict[str, object]] = [
            {
                "error_code": entry.error_code,
                "message": entry.message,
                "captured_at": entry.captured_at_iso,
            }
            for entry in self._state.errors
        ]
        return {
            "session_id": self._session_id,
            "schema_version": _SCHEMA_VERSION,
            "started_at": self._started_at_iso,
            "ended_at": self._state.ended_at_iso,
            "termination_reason": self._state.termination_reason,
            "config": dict(self._config_snapshot),
            "transcript": transcript_entries,
            "tool_trace": tool_trace_entries,
            "errors": error_entries,
        }
