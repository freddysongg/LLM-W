"""Seed the v1 rubric set into the eval database.

Iterates ``rubrics/*.yaml`` and invokes the ``load_rubric_from_yaml`` service
for each file. Idempotent: re-running against a database that already
contains the same content hashes is a no-op and reports ``[cached]``.

Usage::

    python3 scripts/eval/seed_rubrics.py
    python3 scripts/eval/seed_rubrics.py --rubrics-dir path/to/rubrics
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from app.core.database import async_session_factory, create_tables
from app.services.eval.rubric_loader import RubricVersionRecord, load_rubric_from_yaml

_STDERR_PREFIX = "[seed_rubrics]"
_DEFAULT_RUBRICS_DIR = Path(__file__).resolve().parents[2] / "rubrics"


@dataclass(frozen=True)
class SeedOutcome:
    """Result of attempting to load one rubric YAML."""

    rubric_name: str
    is_new: bool
    content_hash: str
    version_number: int


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the v1 rubric set into the eval database.",
    )
    parser.add_argument(
        "--rubrics-dir",
        type=Path,
        default=_DEFAULT_RUBRICS_DIR,
        help="Directory containing rubric YAML files (default: repo-root/rubrics).",
    )
    return parser.parse_args(argv)


def _discover_yaml_files(*, rubrics_dir: Path) -> list[Path]:
    if not rubrics_dir.is_dir():
        raise FileNotFoundError(f"rubrics directory does not exist: {rubrics_dir}")
    yaml_paths = sorted(rubrics_dir.glob("*.yaml"))
    if not yaml_paths:
        raise FileNotFoundError(f"no *.yaml files found in {rubrics_dir}")
    return yaml_paths


async def _seed_one(*, yaml_path: Path) -> SeedOutcome:
    async with async_session_factory() as session:
        record: RubricVersionRecord = await load_rubric_from_yaml(
            yaml_path=yaml_path,
            session=session,
        )
    return SeedOutcome(
        rubric_name=yaml_path.stem,
        is_new=record.is_new,
        content_hash=record.content_hash,
        version_number=record.version_number,
    )


def _format_outcome(outcome: SeedOutcome) -> str:
    tag = "seeded" if outcome.is_new else "cached"
    short_hash = outcome.content_hash[:12]
    return f"[{tag}] {outcome.rubric_name} v{outcome.version_number} (content_hash={short_hash}...)"


async def _seed_all(*, rubrics_dir: Path) -> int:
    await create_tables()
    yaml_paths = _discover_yaml_files(rubrics_dir=rubrics_dir)
    failure_count = 0
    for yaml_path in yaml_paths:
        try:
            outcome = await _seed_one(yaml_path=yaml_path)
        except Exception as exc:
            failure_count += 1
            print(
                f"{_STDERR_PREFIX} failed to load {yaml_path.name}: {exc}",
                file=sys.stderr,
            )
            continue
        print(_format_outcome(outcome))
    return failure_count


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    failure_count = asyncio.run(_seed_all(rubrics_dir=args.rubrics_dir))
    return 1 if failure_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
