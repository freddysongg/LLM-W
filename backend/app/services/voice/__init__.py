"""Voice subdomain services for the Pipecat-powered shopping demo.

This package is intentionally light: importing it must not pull in `pipecat-ai`,
which is an optional `voice` extra. The heavyweight pipeline construction lives
in `pipecat_session.py` and is guarded by lazy imports.
"""

from __future__ import annotations

from app.services.voice import pipecat_session, shopping_tools, transcript_writer
from app.services.voice import voice_service as voice_service

__all__ = [
    "pipecat_session",
    "shopping_tools",
    "transcript_writer",
    "voice_service",
]
