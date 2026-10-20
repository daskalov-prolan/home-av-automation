import asyncio

import pytest

from avhub.core.events import Event, EventBus
from avhub.drivers.denon_avr import DenonAvr, parse_line, volume_command


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("PWON", ("power", True)),
        ("PWSTANDBY", ("power", False)),
        ("MV50", ("volume", 50.0)),
        ("MV505", ("volume", 50.5)),
        ("MV05", ("volume", 5.0)),
        ("MVMAX 98", None),
        ("MUON", ("mute", True)),
        ("MUOFF", ("mute", False)),
        ("SIGAME", ("input", "GAME")),
        ("ZMON", None),
    ],
)
def test_parse_line(line, expected):
    assert parse_line(line) == expected


@pytest.mark.parametrize(
    ("volume", "command"),
    [(30, "MV30"), (30.5, "MV305"), (5, "MV05"), (-3, "MV00"), (150, "MV98"), (30.4, "MV305")],
)
def test_volume_command(volume, command):
    assert volume_command(volume) == command


class FakeReceiver:
    """A tiny TCP server that behaves like a Denon receiver."""

    def __init__(self) -> None:
        self.state = {"PW": "STANDBY", "MV": "20", "MU": "OFF", "SI": "TV"}
        self.received: list[str] = []

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        while not reader.at_eof():
            try:
                data = await reader.readuntil(b"\r")
            except asyncio.IncompleteReadError:
                break
            cmd = data[:-1].decode()
            self.received.append(cmd)
            prefix, arg = cmd[:2], cmd[2:]
            if arg != "?":
                self.state[prefix] = arg
            writer.write(f"{prefix}{self.state[prefix]}\r".encode())
            await writer.drain()
        writer.close()


async def wait_for(condition) -> None:
    """Poll until condition() is true; fail after 2 seconds."""
    async with asyncio.timeout(2.0):
        while not condition():  # noqa: ASYNC110 - simple polling is fine in tests
            await asyncio.sleep(0.01)


async def test_driver_against_fake_receiver():
    fake = FakeReceiver()
    server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    bus = EventBus()
    events: list[Event] = []

    async def collect(event: Event) -> None:
        events.append(event)

    bus.subscribe("avr.*", collect)
    avr = DenonAvr("avr", bus, host="127.0.0.1", port=port, command_delay=0)
    await avr.start()
    try:
        # On connect the driver queries the current state.
        await wait_for(lambda: len(avr.state) == 4)
        assert avr.state == {"power": False, "volume": 20.0, "mute": False, "input": "TV"}

        await avr.call("power_on")
        await avr.call("set_volume", volume=35.5)
        await avr.call("select_input", source="game")
        await wait_for(lambda: avr.state["input"] == "GAME")

        assert avr.state == {"power": True, "volume": 35.5, "mute": False, "input": "GAME"}
        assert fake.received[-3:] == ["PWON", "MV355", "SIGAME"]
        assert [e.topic for e in events][-3:] == ["avr.power", "avr.volume", "avr.input"]
    finally:
        await avr.stop()
        server.close()
        await server.wait_closed()


async def test_unknown_action_is_rejected():
    avr = DenonAvr("avr", EventBus(), host="127.0.0.1")
    with pytest.raises(ValueError):
        await avr.call("self_destruct")
