import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pihavaillant"))
from backend.metrics import BY_KEY, METRICS, extract, parse_snapshot, parse_verbose
from backend.ebus import EbusClient

FIXTURE = Path(__file__).parent / "fixtures" / "ebusd-export.json"


class ParsingTests(unittest.TestCase):
    def test_real_snapshot(self):
        values = parse_snapshot(json.loads(FIXTURE.read_text(encoding="utf-8")))
        self.assertEqual(values["return_temp"]["value"], 42.12)
        self.assertEqual(values["flow_temp"]["value"], 45.69)
        self.assertEqual(values["pressure"]["value"], 1.532)
        self.assertEqual(values["flame"]["value"], "OFF")
        self.assertEqual(values["hc_hours"]["value"], 4787)
        self.assertEqual(values["current_error"]["value"], "brak")
        self.assertIsNone(values["hwc_temp"]["value"])
        self.assertNotIn("PowerValue", [m.message for m in METRICS])

    def test_live_and_json_agree(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        imported = parse_snapshot(payload)
        for item in payload["messages"]:
            for metric in METRICS:
                if metric.message != item["name"] or item["status"] != "ok":
                    continue
                try:
                    value = extract(metric, parse_verbose(item["raw"]))
                except ValueError:
                    value = None
                self.assertEqual(value, imported[metric.key]["value"], metric.key)

    def test_bad_values(self):
        for raw in ("temp=NaN", "temp=inf", "temp=65535 °C", "temp=- °C", "temp=35 bar", "temp=40 °C;sensor=cutoff", "temp=116.06 °C;sensor=circuit"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                extract(BY_KEY["flow_temp"], parse_verbose(raw))
        with self.assertRaises(ValueError):
            extract(BY_KEY["flow_temp"], {"temp": {"value": 30, "valid_for_metrics": False}})

    def test_zero_and_off_are_valid(self):
        self.assertEqual(extract(BY_KEY["fan_speed"], parse_verbose("value=0 rpm")), 0)
        self.assertEqual(extract(BY_KEY["flame"], parse_verbose("value=off")), "OFF")
        with self.assertRaises(ValueError):
            extract(BY_KEY["flame"], parse_verbose("value=unknown"))

    def test_errors(self):
        self.assertEqual(extract(BY_KEY["current_error"], parse_verbose("error=F.28;error_1=-")), "F.28")
        for raw in ("ERR: invalid position in decode: bai PowerValue", "bai X = no data stored", "", "nonsense"):
            with self.assertRaises(ValueError):
                parse_verbose(raw)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_response_and_allowlist(self):
        commands = []
        async def handle(reader, writer):
            commands.append((await reader.readline()).decode())
            writer.write(b"bai FlowTemp temp=61.")
            await writer.drain()
            await asyncio.sleep(0.01)
            writer.write(b"69 \xc2\xb0C [Temperatur];sensor=ok\n\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        async with server:
            client = EbusClient("127.0.0.1", server.sockets[0].getsockname()[1])
            fields = await client.read("FlowTemp")
            self.assertEqual(extract(BY_KEY["flow_temp"], fields), 61.69)
            with self.assertRaises(ValueError):
                await client.read("FlowTemp\nwrite -c bai X 1")
        self.assertEqual(commands, ["read -V -m 30 -c bai FlowTemp\n"])

    async def test_timeout(self):
        async def handle(reader, writer):
            await reader.read()
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        async with server:
            client = EbusClient("127.0.0.1", server.sockets[0].getsockname()[1], timeout=0.05)
            with self.assertRaises(TimeoutError):
                await client.read("FlowTemp")


class DiscoveryTests(unittest.TestCase):
    def test_discovery_read_only(self):
        from backend.mqtt import discovery
        ids = set()
        for metric in METRICS:
            topic, payload = discovery(metric, "boiler", 200)
            self.assertNotIn("command_topic", payload)
            self.assertEqual(payload["availability_mode"], "all")
            self.assertNotIn(payload["unique_id"], ids)
            ids.add(payload["unique_id"])
            self.assertIn(metric.key, topic)
            if metric.kind == "binary":
                self.assertIn("binary_sensor", topic)
                self.assertNotIn("state_class", payload)

    def test_publish_invalid_and_recovery(self):
        from backend.mqtt import Publisher
        from unittest.mock import MagicMock
        publisher = Publisher({"device_id": "test", "stale_after": 180})
        publisher.client = MagicMock()
        publisher.connected = True
        publisher.publish({"flow_temp": {"value": None}, "flame": {"value": "OFF"}})
        publisher.client.publish.assert_any_call("pihavaillant/test/flow_temp/availability", "offline", qos=1, retain=True)
        publisher.client.publish.assert_any_call("pihavaillant/test/flame/state", "OFF", qos=1, retain=False)
        publisher.publish({"flow_temp": {"value": 35}})
        publisher.client.publish.assert_any_call("pihavaillant/test/flow_temp/availability", "online", qos=1, retain=True)


class PollTests(unittest.IsolatedAsyncioTestCase):
    async def test_poll_isolates_fault_and_slow_schedule(self):
        from backend.main import Monitor, load_options
        from unittest.mock import AsyncMock
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw = {item["name"]: item["raw"] for item in fixture["messages"]}
        async def read(message, age):
            return parse_verbose(raw[message])
        monitor = Monitor(load_options())
        monitor.client.read = AsyncMock(side_effect=read)
        with patch("backend.main.asyncio.sleep", new_callable=AsyncMock):
            await monitor.poll()
            self.assertEqual(monitor.values["delta_temp"]["value"], 3.57)
            self.assertIsNone(monitor.values["hwc_temp"]["value"])
            self.assertFalse(monitor.snapshot()["stale"])
            monitor.client.read.reset_mock()
            await monitor.poll()
            self.assertNotIn("HcHours", [c.args[0] for c in monitor.client.read.call_args_list])
            monitor.client.read.side_effect = TimeoutError()
            await monitor.poll()
            self.assertIsNone(monitor.values["flow_temp"]["value"])
            self.assertIsNone(monitor.values["delta_temp"]["value"])


class ApiTests(unittest.TestCase):
    def test_routes_are_read_only_and_do_not_expose_secrets(self):
        from fastapi.testclient import TestClient
        from backend.main import app, Monitor, load_options
        from unittest.mock import AsyncMock
        with patch.object(Monitor, "run", new_callable=AsyncMock), TestClient(app) as client:
            self.assertEqual(client.get("/").status_code, 200)
            response = client.get("/api/state")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("mqtt_password", response.text)
            self.assertEqual(client.post("/api/state").status_code, 405)
            self.assertEqual(client.get("/api/history").json(), [])
        with patch.object(Monitor, "run", new_callable=AsyncMock), patch.dict("os.environ", {"SUPERVISOR_TOKEN": "test"}), TestClient(app) as client:
            self.assertEqual(client.get("/").status_code, 403)


if __name__ == "__main__":
    unittest.main()
