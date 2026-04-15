from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from app.cli.eval_replay import run_eval_replay_command

_PROG_NAME = "llmw"
_EVAL_COMMAND = "eval"
_EVAL_REPLAY_SUBCOMMAND = "replay"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=_PROG_NAME)
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser(_EVAL_COMMAND, help="eval operations")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)

    replay_parser = eval_subparsers.add_parser(
        _EVAL_REPLAY_SUBCOMMAND,
        help="re-run a stored eval_call to detect judge-model drift",
    )
    replay_parser.add_argument(
        "eval_call_id",
        help="id of the eval_calls row to replay",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a shell exit code.

    Setuptools' console-script wrapper passes the return value to sys.exit,
    so no explicit sys.exit call is needed here.
    """
    parser = _build_parser()
    namespace = parser.parse_args(argv)

    if namespace.command == _EVAL_COMMAND and namespace.eval_command == _EVAL_REPLAY_SUBCOMMAND:
        return asyncio.run(run_eval_replay_command(eval_call_id=namespace.eval_call_id))

    parser.error(f"unknown command: {namespace.command} {namespace.eval_command}")
    return 2
