"""A small in-process event bus.

Every state change of a device is published as an Event with the topic
"<device id>.<state name>", e.g. "receiver.power". Subscribers use glob
patterns such as "receiver.*" or "*.power".
"""

from __future__ import annotations

import fnmatch
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    source: str  # device id
    name: str  # state name, e.g. "power", "volume", "input"
    value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def topic(self) -> str:
        return f"{self.source}.{self.name}"


Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[tuple[str, Handler]] = []

    def subscribe(self, pattern: str, handler: Handler) -> Callable[[], None]:
        """Register a handler for topics matching `pattern`. Returns an unsubscribe function."""
        entry = (pattern, handler)
        self._subscribers.append(entry)

        def unsubscribe() -> None:
            if entry in self._subscribers:
                self._subscribers.remove(entry)

        return unsubscribe

    async def publish(self, event: Event) -> None:
        for pattern, handler in list(self._subscribers):
            if fnmatch.fnmatchcase(event.topic, pattern):
                try:
                    await handler(event)
                except Exception:
                    # One failing subscriber must not stop the others.
                    log.exception("Handler for %s failed on event %s", pattern, event.topic)
