"""Line-based TCP client with automatic reconnect.

Many AV devices (receivers, projectors, HDMI matrices) expose a simple
text protocol on a TCP port: you send a command terminated by CR or CRLF
and the device answers, and also pushes status changes, line by line.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)


class TcpLineClient:
    def __init__(
        self,
        host: str,
        port: int,
        on_line: Callable[[str], Awaitable[None]],
        *,
        terminator: bytes = b"\r",
        encoding: str = "ascii",
        reconnect_delay: float = 5.0,
        on_connect: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.on_line = on_line
        self.terminator = terminator
        self.encoding = encoding
        self.reconnect_delay = reconnect_delay
        self.on_connect = on_connect
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._writer is not None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name=f"tcp:{self.host}:{self.port}")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def wait_connected(self) -> None:
        """Wait until connected; wrap in `asyncio.timeout(...)` to limit the wait."""
        await self._connected.wait()

    async def send(self, line: str) -> None:
        if self._writer is None:
            raise ConnectionError(f"Not connected to {self.host}:{self.port}")
        log.debug("-> %s:%s %r", self.host, self.port, line)
        self._writer.write(line.encode(self.encoding) + self.terminator)
        await self._writer.drain()

    async def _run(self) -> None:
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                self._writer = writer
                self._connected.set()
                log.info("Connected to %s:%s", self.host, self.port)
                if self.on_connect is not None:
                    await self.on_connect()
                while True:
                    data = await reader.readuntil(self.terminator)
                    line = data[: -len(self.terminator)].decode(self.encoding, errors="replace")
                    line = line.strip()
                    if line:
                        log.debug("<- %s:%s %r", self.host, self.port, line)
                        await self.on_line(line)
            except (OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
                log.warning(
                    "Connection to %s:%s lost (%s); retrying in %ss",
                    self.host,
                    self.port,
                    exc or type(exc).__name__,
                    self.reconnect_delay,
                )
            finally:
                self._connected.clear()
                if self._writer is not None:
                    self._writer.close()
                    self._writer = None
            await asyncio.sleep(self.reconnect_delay)
