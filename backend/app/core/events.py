from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, *, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, *, event_type: str, handler: EventHandler) -> None:
        subscribers = self._subscribers.get(event_type, [])
        if handler in subscribers:
            subscribers.remove(handler)

    async def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handlers:
            await asyncio.gather(*(h(payload) for h in handlers), return_exceptions=True)


event_bus = EventBus()
