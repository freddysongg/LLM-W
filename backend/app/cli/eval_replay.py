from __future__ import annotations

import sys

from app.core.database import async_session_factory
from app.services.eval.replay import (
    EvalCallNotFoundError,
    ReplayOutcome,
    replay_eval_call,
)

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_NOT_FOUND = 2


def _print_outcome(*, outcome: ReplayOutcome) -> None:
    if outcome.hash_matched:
        print(f"[llmw] replay match: response_hash = {outcome.new_response_hash}")
    else:
        print(
            "[llmw] replay divergence: "
            f"stored={outcome.original_response_hash} new={outcome.new_response_hash}"
        )
    print(f"[llmw] new eval_call row: {outcome.new_eval_call_id}")


async def run_eval_replay_command(*, eval_call_id: str) -> int:
    """Execute `llmw eval replay <eval_call_id>` and return a shell exit code."""
    try:
        async with async_session_factory() as session:
            outcome = await replay_eval_call(
                eval_call_id=eval_call_id,
                session=session,
            )
    except EvalCallNotFoundError:
        print(f"[llmw] eval_call {eval_call_id} not found", file=sys.stderr)
        return _EXIT_NOT_FOUND
    except Exception as exc:
        print(f"[llmw] replay failed: {exc}", file=sys.stderr)
        return _EXIT_ERROR

    _print_outcome(outcome=outcome)
    return _EXIT_OK
