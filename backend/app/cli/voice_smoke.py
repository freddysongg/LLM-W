from __future__ import annotations

import argparse
import sys

from app.core.config import settings
from app.core.exceptions import VoicePipecatNotInstalledError
from app.services import settings_service
from app.services.voice.pipecat_session import _import_pipecat_modules

_EXIT_OK = 0
_EXIT_ERROR = 1

_REQUIRED_CREDENTIAL_KEYS: tuple[str, ...] = (
    "deepgram_api_key",
    "cartesia_api_key",
    "openai_api_key",
)


def register_subcommand(*, subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "smoke",
        help="check voice provider credentials and pipecat-ai availability",
    )


def _is_credential_set(*, key: str) -> bool:
    override = settings_service._overrides.get(key)
    if override:
        return True
    fallback = getattr(settings, key, None)
    return bool(fallback)


def _check_pipecat_importable() -> bool:
    """Try importing pipecat modules without instantiating any service.

    `_import_pipecat_modules` raises `VoicePipecatNotInstalledError` if any
    required pipecat submodule is missing. We deliberately do not catch any
    other exception type so that import-time failures unrelated to the optional
    extra surface to the operator.
    """
    try:
        _import_pipecat_modules()
    except VoicePipecatNotInstalledError:
        return False
    return True


async def run(*, args: argparse.Namespace) -> int:
    del args
    missing_credentials: list[str] = []
    for key in _REQUIRED_CREDENTIAL_KEYS:
        if _is_credential_set(key=key):
            print(f"[llmw voice smoke] {key}: set")
        else:
            print(f"[llmw voice smoke] {key}: missing", file=sys.stderr)
            missing_credentials.append(key)

    is_pipecat_importable = _check_pipecat_importable()
    if is_pipecat_importable:
        print("[llmw voice smoke] pipecat-ai modules importable")
    else:
        print(
            "[llmw voice smoke] pipecat-ai not installed (run 'pip install -e \".[voice]\"')",
            file=sys.stderr,
        )

    if missing_credentials or not is_pipecat_importable:
        problems = list(missing_credentials)
        if not is_pipecat_importable:
            problems.append("pipecat-ai")
        print(
            f"[llmw voice smoke] failed: {', '.join(problems)}",
            file=sys.stderr,
        )
        return _EXIT_ERROR

    print("[llmw voice smoke] success: voice stack ready")
    return _EXIT_OK
