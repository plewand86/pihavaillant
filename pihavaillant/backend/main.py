import asyncio
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import time
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from .ebus import EbusClient
from .metrics import METRICS, MESSAGES, extract
from .mqtt import Publisher

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent


def load_options():
    path = Path(os.getenv("PIH_OPTIONS", "/data/options.json"))
    options = dict(ebusd_host="", ebusd_port=8888, circuit="bai", timeout=5,
                   poll_interval=30, device_id="boiler", mqtt_host="", mqtt_port=1883,
                   mqtt_username="", mqtt_password="", mqtt_tls=False)
    if path.exists():
        options.update(json.loads(path.read_text(encoding="utf-8")))
    for key, low, high in [("ebusd_port", 1, 65535), ("mqtt_port", 1, 65535), ("timeout", 1, 15), ("poll_interval", 15, 300)]:
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"Invalid {key}")
    if not re.fullmatch(r"[a-z0-9_]+", options["device_id"]):
        raise ValueError("Invalid device_id")
    options["stale_after"] = options["poll_interval"] + len(MESSAGES) * options["timeout"] + 30
    return options


def supervisor_mqtt():
    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        return None
    request = urllib.request.Request("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)["data"]


class Monitor:
    def __init__(self, options):
        self.options = options
        self.client = EbusClient(options["ebusd_host"], options["ebusd_port"], options["circuit"], options["timeout"])
        self.values = {}
        self.history = deque(maxlen=720)
        self.due = {}
        self.publisher = None
        self.last_cycle = None
        self.last_cycle_mono = None

    async def setup_mqtt(self):
        if self.publisher:
            return
        options = dict(self.options)
        try:
            if not options["mqtt_host"]:
                service = await asyncio.to_thread(supervisor_mqtt)
                if not service:
                    return
                options.update(mqtt_host=service["host"], mqtt_port=service["port"],
                               mqtt_username=service["username"], mqtt_password=service["password"],
                               mqtt_tls=service.get("ssl", False))
            self.publisher = Publisher(options)
            self.publisher.start()
        except Exception as exc:
            LOG.warning("MQTT setup failed: %s", type(exc).__name__)
            self.publisher = None

    async def poll(self):
        for message in sorted(MESSAGES):
            if time.monotonic() < self.due.get(message, 0):
                continue
            metrics = [m for m in METRICS if m.message == message]
            slow = all(m.slow for m in metrics)
            error = None
            fields = {}
            try:
                fields = await self.client.read(message, 300 if slow else self.options["poll_interval"])
            except (OSError, TimeoutError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
                error = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            stamp = datetime.now(timezone.utc).isoformat()
            for metric in metrics:
                value, reason = None, error
                if not error:
                    try:
                        value = extract(metric, fields)
                    except ValueError as exc:
                        reason = str(exc)
                self.values[metric.key] = {"value": value, "error": reason, "updated_at": stamp}
            self.due[message] = time.monotonic() + (300 if slow or error == "ebusd_error" else 0)
            # Sequential requests with a pause; no parallel bus traffic.
            await asyncio.sleep(0.15)
        flow = self.values.get("flow_temp", {}).get("value")
        ret = self.values.get("return_temp", {}).get("value")
        self.values["delta_temp"] = {"value": round(flow - ret, 2) if flow is not None and ret is not None else None, "error": None if flow is not None and ret is not None else "missing_source"}
        self.values["invalid_count"] = {"value": sum(self.values.get(m.key, {}).get("value") is None for m in METRICS if m.message), "error": None}
        self.last_cycle = datetime.now(timezone.utc).isoformat()
        self.last_cycle_mono = time.monotonic()
        self.values["last_poll"] = {"value": self.last_cycle, "error": None}
        self.history.append({"time": self.last_cycle, **{key: self.values.get(key, {}).get("value") for key in ("flow_temp", "return_temp", "storage_temp", "modulation", "flame")}})
        if self.publisher:
            self.publisher.publish(self.values)

    async def run(self):
        while True:
            started = time.monotonic()
            try:
                await self.setup_mqtt()
                await self.poll()
            except Exception as exc:
                LOG.exception("Polling failed (%s)", type(exc).__name__)
            await asyncio.sleep(max(1, self.options["poll_interval"] - (time.monotonic() - started)))

    def snapshot(self):
        stale = self.last_cycle_mono is None or time.monotonic() - self.last_cycle_mono > self.options["stale_after"]
        return {"device_id": self.options["device_id"], "last_cycle": self.last_cycle,
                "stale": stale, "mqtt_connected": bool(self.publisher and self.publisher.connected),
                "metrics": [{"key": m.key, "name": m.name, "unit": m.unit, "kind": m.kind,
                             **self.values.get(m.key, {"value": None, "error": "waiting"})} for m in METRICS]}


@asynccontextmanager
async def lifespan(app):
    monitor = Monitor(load_options())
    app.state.monitor = monitor
    task = asyncio.create_task(monitor.run())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        if monitor.publisher:
            await asyncio.to_thread(monitor.publisher.stop)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def ingress_only(request: Request, call_next):
    allowed = {"172.30.32.2"} if os.getenv("SUPERVISOR_TOKEN") else {"127.0.0.1", "::1", "testclient"}
    if request.client is None or request.client.host not in allowed:
        return JSONResponse({"error": "Ingress or localhost only"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
async def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/api/state")
async def state():
    return app.state.monitor.snapshot()


@app.get("/api/history")
async def history():
    return list(app.state.monitor.history)
