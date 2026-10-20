"""Denon / Marantz AV receivers - Telnet control protocol (TCP port 23).

Commands and replies are ASCII terminated by CR, e.g.
    PWON / PWSTANDBY / PW?     power
    MV50 / MV505 / MV?         master volume (0..98, "505" means 50.5)
    MUON / MUOFF / MU?         mute
    SIGAME / SITV / SI?        input source
The receiver also pushes these lines on its own when something changes
(e.g. someone turns the volume knob).

Note: most models accept only ONE telnet connection at a time.
"""

from __future__ import annotations

import asyncio
from typing import Any

from avhub.core.device import Device
from avhub.core.events import EventBus
from avhub.transports.tcp import TcpLineClient

MAX_VOLUME = 98.0
QUERIES = ("PW?", "MV?", "MU?", "SI?")


def parse_line(line: str) -> tuple[str, Any] | None:
    """Turn a receiver reply into (state name, value), or None if not handled."""
    if line.startswith("PW"):
        return "power", line[2:] == "ON"
    if line.startswith("MVMAX"):
        return None
    if line.startswith("MV"):
        raw = line[2:].strip()
        if not raw.isdigit() or len(raw) not in (2, 3):
            return None
        volume = float(raw[:2])
        if len(raw) == 3:
            volume += 0.5
        return "volume", volume
    if line.startswith("MU"):
        return "mute", line[2:] == "ON"
    if line.startswith("SI"):
        return "input", line[2:]
    return None


def volume_command(volume: float) -> str:
    volume = max(0.0, min(MAX_VOLUME, round(volume * 2) / 2))
    whole = int(volume)
    return f"MV{whole:02d}5" if volume - whole else f"MV{whole:02d}"


class DenonAvr(Device):
    ACTIONS = frozenset(
        {"power_on", "power_off", "set_volume", "volume_up", "volume_down", "mute",
         "select_input", "refresh"}
    )

    def __init__(
        self,
        device_id: str,
        bus: EventBus,
        host: str,
        port: int = 23,
        name: str | None = None,
        command_delay: float = 0.1,
    ) -> None:
        super().__init__(device_id, bus, name)
        self.command_delay = command_delay  # Denon asks for a short gap between commands
        self._lock = asyncio.Lock()
        self.client = TcpLineClient(host, port, self._on_line, on_connect=self.refresh)

    async def start(self) -> None:
        await self.client.start()

    async def stop(self) -> None:
        await self.client.stop()

    async def _send(self, command: str) -> None:
        async with self._lock:
            await self.client.send(command)
            await asyncio.sleep(self.command_delay)

    async def _on_line(self, line: str) -> None:
        parsed = parse_line(line)
        if parsed is not None:
            await self.update_state(*parsed)

    # ---- actions -------------------------------------------------------

    async def refresh(self) -> None:
        for query in QUERIES:
            await self._send(query)

    async def power_on(self) -> None:
        await self._send("PWON")

    async def power_off(self) -> None:
        await self._send("PWSTANDBY")

    async def set_volume(self, volume: float) -> None:
        await self._send(volume_command(volume))

    async def volume_up(self) -> None:
        await self._send("MVUP")

    async def volume_down(self) -> None:
        await self._send("MVDOWN")

    async def mute(self, on: bool = True) -> None:
        await self._send("MUON" if on else "MUOFF")

    async def select_input(self, source: str) -> None:
        await self._send(f"SI{source.upper()}")
