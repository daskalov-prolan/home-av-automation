import pytest

from avhub.automation.rules import AutomationEngine, Rule
from avhub.core.device import Device
from avhub.core.events import EventBus


class FakeDevice(Device):
    ACTIONS = frozenset({"set_volume", "power_on"})

    def __init__(self, device_id: str, bus: EventBus) -> None:
        super().__init__(device_id, bus)
        self.calls: list[tuple[str, dict]] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def set_volume(self, volume: float) -> None:
        self.calls.append(("set_volume", {"volume": volume}))

    async def power_on(self) -> None:
        self.calls.append(("power_on", {}))


RULE = {
    "name": "TV on -> receiver on",
    "when": {"device": "tv", "state": "power", "equals": True},
    "then": [
        {"device": "receiver", "action": "power_on"},
        {"device": "receiver", "action": "set_volume", "args": {"volume": 30}},
    ],
}


async def test_rule_fires_only_on_matching_value():
    bus = EventBus()
    tv, receiver = FakeDevice("tv", bus), FakeDevice("receiver", bus)
    engine = AutomationEngine(bus, {"tv": tv, "receiver": receiver}, [Rule.from_dict(RULE)])
    engine.start()

    await tv.update_state("power", False)
    assert receiver.calls == []

    await tv.update_state("power", True)
    assert receiver.calls == [("power_on", {}), ("set_volume", {"volume": 30})]

    # Same value again is not a change, so nothing fires.
    await tv.update_state("power", True)
    assert len(receiver.calls) == 2


def test_invalid_rule_is_rejected():
    bus = EventBus()
    devices = {"tv": FakeDevice("tv", bus)}
    with pytest.raises(ValueError, match="unknown device 'receiver'"):
        AutomationEngine(bus, devices, [Rule.from_dict(RULE)])
