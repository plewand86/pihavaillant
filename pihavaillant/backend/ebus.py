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
            raise ValueError("Message is not in the read-only allowlist")
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
