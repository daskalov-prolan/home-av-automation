from avhub.core.events import Event, EventBus


async def test_pattern_matching():
    bus = EventBus()
    received: list[str] = []

    async def handler(event: Event) -> None:
        received.append(event.topic)

    bus.subscribe("receiver.*", handler)
    bus.subscribe("*.power", handler)

    await bus.publish(Event("receiver", "volume", 30))
    await bus.publish(Event("tv", "power", True))
    await bus.publish(Event("tv", "input", "HDMI1"))

    assert received == ["receiver.volume", "tv.power"]


async def test_unsubscribe_and_failing_handler():
    bus = EventBus()
    received: list[str] = []

    async def broken(event: Event) -> None:
        raise RuntimeError("boom")

    async def ok(event: Event) -> None:
        received.append(event.topic)

    bus.subscribe("*", broken)
    unsubscribe = bus.subscribe("*", ok)

    await bus.publish(Event("a", "x"))
    unsubscribe()
    await bus.publish(Event("a", "y"))

    assert received == ["a.x"]
