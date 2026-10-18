import asyncio
import re
from .metrics import METRICS, MESSAGES, parse_verbose


class EbusClient:
    def __init__(self, host, port=8888, circuit="bai", timeout=5):
        if not re.fullmatch(r"[A-Za-z0-9_]+", circuit):
            raise ValueError("Invalid circuit")
        self.host, self.port, self.circuit, self.timeout = host, port, circuit, timeout

    async def read(self, message, max_age=30):
        if message not in MESSAGES:
            raise ValueError("Message is not in the read allowlist")
        circuit = next(m.circuit for m in METRICS if m.message == message) or self.circuit
        async with asyncio.timeout(self.timeout):
            reader, writer = await asyncio.open_connection(self.host, self.port, limit=65536)
            try:
                writer.write(f"read -V -m {int(max_age)} -c {circuit} {message}\n".encode())
                await writer.drain()
                response = await reader.readuntil(b"\n\n")
                return parse_verbose(response.decode("utf-8", errors="replace"))
            finally:
                writer.close()
                await writer.wait_closed()

    async def set_room_override(self, temperature, duration):
        """Write only the two confirmed CTLV2 Quick Veto settings."""
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 5 <= temperature <= 30 or round(temperature * 2) != temperature * 2:
            raise ValueError("Invalid room temperature")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 0.5 <= duration <= 12 or round(duration * 2) != duration * 2:
            raise ValueError("Invalid Quick Veto duration")
        replies = []
        for message, value in (("Z1QuickVetoTemp", f"{temperature:.1f}"), ("Z1QuickVetoDuration", f"{duration:.1f}")):
            replies.append(await self._command(f"write -c ctlv2 {message} {value}"))
        return replies

    async def _command(self, command):
        async with asyncio.timeout(self.timeout):
            reader, writer = await asyncio.open_connection(self.host, self.port, limit=65536)
            try:
                writer.write((command + "\n").encode("ascii"))
                await writer.drain()
                response = (await reader.readuntil(b"\n\n")).decode("utf-8", errors="replace").strip()
                if not response or "ERR:" in response:
                    raise ValueError(response or "ebusd_write_failed")
                return response
            finally:
                writer.close()
                await writer.wait_closed()
