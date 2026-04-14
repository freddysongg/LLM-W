from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    str(settings.database_url),
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)


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


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
