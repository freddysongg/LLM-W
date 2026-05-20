"""Shared pytest configuration for the backend test suite.

This module is intentionally minimal — most tests still own their own engine
fixture. It exists primarily to surface the pending diagnosis below.

TODO(eventloop-warning): aiosqlite's daemon worker thread races the
function-scoped pytest event loop close at the very end of full-suite runs,
producing one `PytestUnhandledThreadExceptionWarning: Event loop is closed`.
Tests still pass. Root cause and candidate fixes documented at
`.context/event-loop-warning-diagnosis-2026-05-20.md` (workspace-local,
gitignored). Diagnosis only — fix deferred.
"""

from __future__ import annotations
