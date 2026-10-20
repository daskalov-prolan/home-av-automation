"""Simple "when <device state> changes -> run actions" automations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from avhub.core.device import Device
from avhub.core.events import Event, EventBus

log = logging.getLogger(__name__)

_ANY = object()


@dataclass
class Trigger:
    device: str
    state: str
    equals: Any = _ANY  # only fire when the new value equals this

    def matches(self, event: Event) -> bool:
        return self.equals is _ANY or event.value == self.equals


@dataclass
class Action:
    device: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Rule:
    name: str
    trigger: Trigger
    actions: list[Action]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rule:
        when = data["when"]
        trigger = Trigger(when["device"], when["state"], when.get("equals", _ANY))
        actions = [Action(a["device"], a["action"], a.get("args", {})) for a in data["then"]]
        return cls(data.get("name", trigger.device + "." + trigger.state), trigger, actions)


class AutomationEngine:
    def __init__(self, bus: EventBus, devices: dict[str, Device], rules: list[Rule]) -> None:
        self.bus = bus
        self.devices = devices
        self.rules = rules
        self._unsubscribers: list = []
        self._validate()

    def _validate(self) -> None:
        for rule in self.rules:
            if rule.trigger.device not in self.devices:
                raise ValueError(f"Rule '{rule.name}': unknown device '{rule.trigger.device}'")
            for action in rule.actions:
                device = self.devices.get(action.device)
                if device is None:
                    raise ValueError(f"Rule '{rule.name}': unknown device '{action.device}'")
                if action.action not in device.ACTIONS:
                    raise ValueError(
                        f"Rule '{rule.name}': device '{action.device}' has no action "
                        f"'{action.action}' (available: {sorted(device.ACTIONS)})"
                    )

    def start(self) -> None:
        for rule in self.rules:
            topic = f"{rule.trigger.device}.{rule.trigger.state}"
            self._unsubscribers.append(self.bus.subscribe(topic, self._handler(rule)))

    def stop(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    def _handler(self, rule: Rule):
        async def handle(event: Event) -> None:
            if not rule.trigger.matches(event):
                return
            log.info("Automation '%s' triggered by %s=%r", rule.name, event.topic, event.value)
            for action in rule.actions:
                await self.devices[action.device].call(action.action, **action.args)

        return handle
