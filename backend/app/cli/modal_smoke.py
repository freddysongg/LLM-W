from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

from app.services import settings_service

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_TIMEOUT = 2

_DEFAULT_SMOKE_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "modal_smoke.yaml"
_DEFAULT_TIMEOUT_SECONDS = 600


def register_subcommand(*, subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "smoke",
        help="provision a Modal sandbox and run the smoke training config",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=_DEFAULT_SMOKE_CONFIG,
        help="path to the smoke YAML config (defaults to configs/modal_smoke.yaml)",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="local project directory used for checkpoints; defaults to a tmp dir",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=_DEFAULT_TIMEOUT_SECONDS,
        help="abort the smoke run if no terminal event arrives within this window",
    )
    parser.add_argument(
        "--gpu-type",
        type=str,
        default="a10",
        help="workbench GPU type key (e.g. 'a10', 'h100'); resolved to Modal spec",
    )


async def run(*, args: argparse.Namespace) -> int:
    # Deferred so `from app.cli import modal_smoke` does not transitively load
    # `modal` — the optional cloud extra is only required to actually run this
    # subcommand, mirroring the lazy-import contract on training_dispatcher,
    # mlx_serving, and pipecat_session.
    from app.services.cloud.modal_adapter import ModalAdapterConfig, ModalTrainingAdapter

    credentials = settings_service.get_modal_credentials()
    if credentials is None:
        print(
            "[llmw modal smoke] Modal credentials are not configured. "
            "Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET in the environment "
            "(or via PATCH /api/v1/settings to the running backend).",
            file=sys.stderr,
        )
        return _EXIT_ERROR

    config_path: Path = args.config_path
    if not config_path.is_file():
        print(
            f"[llmw modal smoke] config not found at {config_path}",
            file=sys.stderr,
        )
        return _EXIT_ERROR

    project_dir: Path = (
        args.project_dir
        if args.project_dir is not None
        else Path(f"/tmp/modal-smoke-{uuid.uuid4().hex[:8]}")
    )
    project_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"smoke-{uuid.uuid4().hex[:8]}"
    modal_token_id, modal_token_secret = credentials
    adapter_config = ModalAdapterConfig(
        run_id=run_id,
        config_path=config_path,
        project_dir=project_dir,
        gpu_type=args.gpu_type,
        modal_token_id=modal_token_id,
        modal_token_secret=modal_token_secret,
        heartbeat_path=project_dir / ".heartbeat",
    )
    adapter = ModalTrainingAdapter(config=adapter_config)

    try:
        await adapter.start()
    except Exception as exc:
        print(
            f"[llmw modal smoke] adapter start failed: {exc}",
            file=sys.stderr,
        )
        return _EXIT_ERROR

    deadline = time.monotonic() + args.timeout_seconds
    events_seen = 0
    final_event: dict[str, object] | None = None
    is_success = False

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print(
                    "[llmw modal smoke] timed out before terminal event",
                    file=sys.stderr,
                )
                await adapter.cancel()
                return _EXIT_TIMEOUT
            try:
                event = await asyncio.wait_for(adapter.read_event(), timeout=remaining)
            except TimeoutError:
                print(
                    "[llmw modal smoke] timed out before terminal event",
                    file=sys.stderr,
                )
                await adapter.cancel()
                return _EXIT_TIMEOUT
            if event is None:
                break
            events_seen += 1
            final_event = event
            print(json.dumps(event), flush=True)
            event_type = event.get("type")
            if event_type == "complete":
                is_success = event.get("status") == "completed"
                break
            if event_type == "error":
                is_success = False
                break

        exit_code = await adapter.wait()
    except Exception as exc:
        print(
            f"[llmw modal smoke] event pump failed: {exc}",
            file=sys.stderr,
        )
        await adapter.cancel()
        return _EXIT_ERROR

    if events_seen == 0:
        print(
            "[llmw modal smoke] no events were emitted by the adapter",
            file=sys.stderr,
        )
        return _EXIT_ERROR

    if not is_success:
        last_type = final_event.get("type") if final_event is not None else "none"
        print(
            f"[llmw modal smoke] terminal event was not 'completed' (last type={last_type}, "
            f"adapter exit={exit_code})",
            file=sys.stderr,
        )
        return _EXIT_ERROR

    print(
        f"[llmw modal smoke] success: {events_seen} events, adapter exit={exit_code}",
    )
    return _EXIT_OK
