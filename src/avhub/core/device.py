"""Base class for all device drivers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from avhub.core.events import Event, EventBus

log = logging.getLogger(__name__)


class Device(ABC):
    """A controllable device.

    A driver subclass:
      - opens its connection in `start()` and closes it in `stop()`,
      - reports what it learns from the device via `update_state()`,
      - lists the coroutine methods automations may call in `ACTIONS`.
    """

    ACTIONS: ClassVar[frozenset[str]] = frozenset()

    def __init__(self, device_id: str, bus: EventBus, name: str | None = None) -> None:
        self.id = device_id
        self.name = name or device_id
        self.bus = bus
        self.state: dict[str, Any] = {}

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    async def update_state(self, key: str, value: Any) -> None:
        """Store a state value and publish an event if it changed."""
        if key in self.state and self.state[key] == value:
            return
        self.state[key] = value
        await self.bus.publish(Event(self.id, key, value))

    async def call(self, action: str, **kwargs: Any) -> None:
        """Run one of the device's actions by name (used by automations)."""
        if action not in self.ACTIONS:
            raise ValueError(f"{type(self).__name__} '{self.id}' has no action '{action}'")
        log.info("%s: %s(%s)", self.id, action, kwargs or "")
        await getattr(self, action)(**kwargs)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.id}>"
