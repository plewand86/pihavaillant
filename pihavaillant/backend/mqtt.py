import json
import paho.mqtt.client as mqtt
from .metrics import METRICS


def discovery(metric, device_id, expiry):
    base = f"pihavaillant/{device_id}"
    component = "binary_sensor" if metric.kind == "binary" else "sensor"
    config = {
        "name": metric.name,
        "unique_id": f"pihavaillant_{device_id}_{metric.key}",
        "object_id": f"pihavaillant_{device_id}_{metric.key}",
        "state_topic": f"{base}/{metric.key}/state",
        "availability": [{"topic": f"{base}/status"}, {"topic": f"{base}/{metric.key}/availability"}],
        "availability_mode": "all",
        "expire_after": expiry,
        "device": {"identifiers": [f"pihavaillant_{device_id}"], "name": f"Vaillant {device_id}", "manufacturer": "Vaillant", "model": "ecoTEC plus (ebusd)", "sw_version": "0.1.0"},
    }
    for key, value in [("unit_of_measurement", metric.unit), ("device_class", metric.device_class), ("state_class", metric.state_class)]:
        if value:
            config[key] = value
    if metric.diagnostic:
        config["entity_category"] = "diagnostic"
    return f"homeassistant/{component}/pihavaillant_{device_id}/{metric.key}/config", config


class Publisher:
    def __init__(self, options):
        self.options = options
        self.base = f"pihavaillant/{options['device_id']}"
        self.connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"pihavaillant_{options['device_id']}")
        self.client.max_queued_messages_set(500)
        self.client.will_set(f"{self.base}/status", "offline", qos=1, retain=True)
        if options.get("mqtt_username"):
            self.client.username_pw_set(options["mqtt_username"], options.get("mqtt_password", ""))
        if options.get("mqtt_tls"):
            self.client.tls_set()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.reconnect_delay_set(1, 60)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = not reason_code.is_failure
        if not self.connected:
            return
        client.publish(f"{self.base}/status", "offline", qos=1, retain=True)
        for metric in METRICS:
            topic, payload = discovery(metric, self.options["device_id"], self.options["stale_after"])
            client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False

    def start(self):
        self.client.connect_async(self.options["mqtt_host"], self.options["mqtt_port"], 30)
        self.client.loop_start()

    def publish(self, values):
        if not self.connected:
            return
        for metric in METRICS:
            item = values.get(metric.key, {})
            value = item.get("value")
            prefix = f"{self.base}/{metric.key}"
            if value is not None:
                self.client.publish(f"{prefix}/state", str(value), qos=1, retain=False)
            self.client.publish(f"{prefix}/availability", "online" if value is not None else "offline", qos=1, retain=True)
        self.client.publish(f"{self.base}/status", "online", qos=1, retain=True)

    def stop(self):
        if self.connected:
            self.client.publish(f"{self.base}/status", "offline", qos=1, retain=True).wait_for_publish(timeout=3)
        self.client.disconnect()
        self.client.loop_stop()
