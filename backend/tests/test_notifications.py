from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.models.notification import Notification


@pytest.fixture
async def db_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[async_sessionmaker[Any]]:
    db_path = tmp_path / "workbench.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session() -> AsyncIterator[Any]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


@pytest.fixture
async def client(db_session: async_sessionmaker[Any]) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_list_notifications_returns_empty_array_when_table_is_empty(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/notifications")
    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_list_notifications_returns_rows_in_descending_created_at_order(
    client: AsyncClient, db_session: async_sessionmaker[Any]
) -> None:
    async with db_session() as session:
        session.add(
            Notification(
                id="n1",
                type="run_started",
                title="run_abc started",
                subtitle=None,
                created_at="2026-05-19T00:00:00+00:00",
                read_at=None,
            )
        )
        session.add(
            Notification(
                id="n2",
                type="run_completed",
                title="run_abc completed",
                subtitle="eval loss 0.4",
                created_at="2026-05-20T00:00:00+00:00",
                read_at=None,
            )
        )
        await session.commit()

    response = await client.get("/api/v1/notifications")
    body = response.json()
    assert [item["id"] for item in body["items"]] == ["n2", "n1"]


async def test_mark_notification_read_sets_read_at_and_is_idempotent(
    client: AsyncClient, db_session: async_sessionmaker[Any]
) -> None:
    async with db_session() as session:
        session.add(
            Notification(
                id="n1",
                type="run_started",
                title="run_abc started",
                subtitle=None,
                created_at=datetime.now(UTC).isoformat(),
                read_at=None,
            )
        )
        await session.commit()

    first = await client.post("/api/v1/notifications/n1/read")
    assert first.status_code == 200
    first_read_at = first.json()["read_at"]
    assert first_read_at is not None

    second = await client.post("/api/v1/notifications/n1/read")
    assert second.status_code == 200
    assert second.json()["read_at"] == first_read_at


async def test_mark_notification_read_returns_404_for_missing_id(client: AsyncClient) -> None:
    response = await client.post("/api/v1/notifications/missing/read")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"
