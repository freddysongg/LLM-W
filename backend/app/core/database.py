from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, NamedTuple

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import event, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from alembic import command as alembic_command
from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# A generous busy timeout lets BEGIN IMMEDIATE wait out transient
# contention (watchdog, event-bus writers, HTTP writes landing at the
# same moment) instead of failing with "database is locked".
_SQLITE_BUSY_TIMEOUT_MS = 30_000


engine = create_async_engine(
    str(settings.database_url),
    echo=settings.debug,
    connect_args={"check_same_thread": False, "timeout": _SQLITE_BUSY_TIMEOUT_MS / 1000},
)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite_connection(dbapi_connection: Any, _record: Any) -> None:
    """Enable WAL and a long busy timeout for every new SQLite connection.

    WAL lets readers and a single writer run concurrently, so the REST
    poll traffic no longer blocks behind in-flight writes. The busy
    timeout is a backstop: if two writers still collide, SQLite waits
    up to N ms for the lock instead of immediately erroring. Matches
    the serialization intent of `_emit_begin_immediate` below without
    surfacing OperationalError to the user under normal contention.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
        # synchronous=NORMAL is the documented WAL-safe pairing — durable to
        # app crash, trades a small durability window on power loss for
        # dramatically lower write latency under concurrent load.
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


@event.listens_for(engine.sync_engine, "begin")
def _emit_begin_immediate(conn: Connection) -> None:
    """Promote SQLAlchemy's default BEGIN (DEFERRED) to BEGIN IMMEDIATE.

    BEGIN IMMEDIATE acquires a RESERVED lock at transaction start, so
    concurrent writers serialize deterministically rather than racing
    and failing at commit-time with IntegrityError. Read-only sessions
    are unaffected. Required for the rubric_loader version_number
    serialization guarantee; also hardens every other service.
    """
    conn.exec_driver_sql("BEGIN IMMEDIATE")


async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def _alembic_config() -> AlembicConfig:
    """Build an Alembic config that points at the runtime database.

    Using settings.database_url here means the CLI and in-process paths
    both migrate the same file. The script_location is resolved relative
    to this module so the behaviour is independent of the backend's cwd.
    """
    backend_root = Path(__file__).resolve().parent.parent.parent
    config = AlembicConfig()
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", str(settings.database_url))
    return config


class _DatabaseState(NamedTuple):
    current_revision: str | None
    has_alembic_version: bool
    has_schema: bool


def _inspect_database_state(sync_connection: Connection) -> _DatabaseState:
    inspector = inspect(sync_connection)
    has_alembic_version = inspector.has_table("alembic_version")
    has_schema = inspector.has_table("projects")
    if has_alembic_version:
        context = MigrationContext.configure(sync_connection)
        return _DatabaseState(context.get_current_revision(), True, has_schema)
    return _DatabaseState(None, False, has_schema)


async def create_tables() -> None:
    """Ensure the runtime database matches the current model schema.

    Driven by alembic — `Base.metadata.create_all` can only add missing
    tables and is blind to column additions, which is how this project
    ended up with an `artifacts` table that lacked the `is_best` column
    introduced in migration 0004. Running migrations on startup keeps
    the DB in lockstep with the code.

    Alembic's command API is synchronous and opens its own sync engine
    against the same SQLite file. Running it on a worker thread keeps
    the asyncio event loop responsive while migrations execute.
    """
    config = _alembic_config()
    head_revision = ScriptDirectory.from_config(config).get_current_head()

    async with engine.connect() as conn:
        state = await conn.run_sync(_inspect_database_state)

    if state.current_revision == head_revision and state.has_alembic_version:
        return

    if not state.has_alembic_version and state.has_schema:
        logger.info("Legacy database detected — stamping to alembic head %s", head_revision)
        await asyncio.to_thread(alembic_command.stamp, config, "head")
        return

    logger.info(
        "Running alembic upgrade: %s -> %s", state.current_revision or "base", head_revision
    )
    await asyncio.to_thread(alembic_command.upgrade, config, "head")
