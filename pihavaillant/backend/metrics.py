"""Explicit allowlist: never infer a metric from an arbitrary boiler register."""
from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class Metric:
    key: str
    name: str
    message: str
    field: str = "value"
    unit: str | None = None
    low: float = 0
    high: float = 1e9
    kind: str = "number"
    device_class: str | None = None
    state_class: str | None = "measurement"
    diagnostic: bool = False
    slow: bool = False
    circuit: str | None = None


METRICS = [
    Metric("room_temp", "Temperatura pokojowa (strefa 1)", "Z1RoomTemp", unit="°C", low=-30, high=60, device_class="temperature", circuit="ctlv2"),
    Metric("flow_temp", "Zasilanie", "FlowTemp", "temp", "°C", -30, 130, device_class="temperature"),
    Metric("return_temp", "Powrót", "ReturnTemp", "temp", "°C", -30, 130, device_class="temperature"),
    Metric("storage_temp", "Zasobnik CWU", "StorageTemp", "temp", "°C", -30, 100, device_class="temperature"),
    Metric("hwc_temp", "Czujnik CWU", "HwcTemp", "temp", "°C", -30, 100, device_class="temperature"),
    Metric("outdoor_temp", "Na zewnątrz", "OutdoorstempSensor", "temp", "°C", -60, 70, device_class="temperature"),
    Metric("flow_target", "Zadana zasilania", "FlowTempDesired", unit="°C", high=100, device_class="temperature"),
    Metric("storage_target", "Zadana zasobnika", "StorageTempDesired", unit="°C", high=100, device_class="temperature"),
    Metric("pressure", "Ciśnienie", "WaterPressure", "press", "bar", 0, 6, device_class="pressure"),
    Metric("flame", "Płomień", "Flame", kind="binary", device_class="heat", state_class=None),
    Metric("circulation", "Pompa cyrkulacyjna", "CirPump", kind="binary", state_class=None),
    Metric("hwc_demand", "Zapotrzebowanie CWU", "HwcDemand", kind="binary", state_class=None),
    Metric("lockout", "Blokada kotła", "VolatileLockout", kind="binary", device_class="problem", state_class=None),
    Metric("fan_speed", "Wentylator", "FanSpeed", unit="rpm", high=15000),
    Metric("fan_target", "Zadane obroty wentylatora", "TargetFanSpeed", unit="rpm", high=15000),
    Metric("fan_min", "Minimalne obroty wentylatora", "FanMinSpeedOperation", unit="rpm", high=15000, diagnostic=True, slow=True),
    Metric("modulation", "Modulacja zadana", "ModulationDesired", unit="%", high=100),
    Metric("pump_power", "Wysterowanie pompy (surowe)", "PumpPower", high=100),
    Metric("primary_flow", "Przepływ obiegu", "PrimaryCircuitFlowrate", unit="L/min", high=200, device_class="volume_flow_rate"),
    Metric("pump_state", "Stan pompy", "Status01", "pumpstate", kind="text", state_class=None),
    Metric("pump_mode", "Tryb pompy CO", "HcPumpMode", kind="text", state_class=None),
    Metric("current_error", "Błędy kotła", "Currenterror", kind="errors", state_class=None, diagnostic=True),
    *[Metric(key, name, msg, unit="h", device_class="duration", state_class="total_increasing", slow=True)
      for key, name, msg in [("hc_hours", "Czas pracy CO", "HcHours"), ("hwc_hours", "Czas pracy CWU", "HwcHours"), ("fan_hours", "Czas pracy wentylatora", "FanHours"), ("pump_hours", "Czas pracy pompy", "PumpHours")]],
    *[Metric(key, name, msg, state_class="total_increasing", slow=True)
      for key, name, msg in [("hc_starts", "Starty CO", "HcStarts"), ("hwc_starts", "Starty CWU", "HwcStarts"), ("fan_starts", "Starty wentylatora", "FanStarts"), ("pump_starts", "Starty pompy CO", "HcPumpStarts")]],
    Metric("delta_temp", "Różnica zasilanie–powrót", "", unit="°C", low=-100, high=100),
    Metric("invalid_count", "Niedostępne odczyty", "", diagnostic=True),
    Metric("last_poll", "Ostatni cykl odczytu", "", kind="text", device_class="timestamp", state_class=None, diagnostic=True),
]
BY_KEY = {m.key: m for m in METRICS}
MESSAGES = {m.message for m in METRICS if m.message}


def parse_verbose(raw: str) -> dict:
    if not raw or "ERR:" in raw or "no data stored" in raw or raw.startswith("usage:"):
        raise ValueError("ebusd_error")
    fields = {}
    for name, value in re.findall(r"([A-Za-z][A-Za-z0-9_]*)=([^;\n]*)", raw):
        value = value.split("[", 1)[0].strip()
        fields[name] = {"value": value, "valid_for_metrics": True}
    if not fields:
        raise ValueError("missing_fields")
    return fields


def extract(metric: Metric, fields: dict):
    if "sensor" in fields and str(fields["sensor"].get("value", "")).strip() != "ok":
        raise ValueError("sensor_fault")
    if metric.kind == "errors":
        values = [str(v.get("value") or "").strip() for k, v in fields.items() if re.fullmatch(r"error(?:_\d+)?", k)]
        if not values or any(not v for v in values):
            raise ValueError("missing_fields")
        return ", ".join(v for v in values if v != "-") or "brak"
    item = fields.get(metric.field)
    if not isinstance(item, dict) or item.get("valid_for_metrics") is False:
        raise ValueError("invalid_field")
    value = item.get("value")
    if value is None or isinstance(value, bool):
        raise ValueError("missing_value")
    value = str(value).strip()
    if metric.kind == "binary":
        if value.lower() in ("on", "yes", "1", "true"):
            return "ON"
        if value.lower() in ("off", "no", "0", "false"):
            return "OFF"
        raise ValueError("invalid_boolean")
    if metric.kind == "text":
        if not value or value == "-" or len(value) > 128:
            raise ValueError("invalid_text")
        return value
    match = re.fullmatch(r"([-+]?\d+(?:\.\d+)?)\s*(°C|bar|rpm|%|h|L/min|l/min)?", value)
    if not match or (match[2] and match[2].lower() != (metric.unit or "").lower()):
        raise ValueError("invalid_number_or_unit")
    declared_unit = item.get("unit")
    if declared_unit and str(declared_unit).lower() != (metric.unit or "").lower():
        raise ValueError("unexpected_unit")
    number = float(match[1])
    if not math.isfinite(number) or not metric.low <= number <= metric.high:
        raise ValueError("out_of_range")
    return number


def parse_snapshot(payload: dict) -> dict:
    """Import the supplied export for offline replay; never publish it as live data."""
    result = {}
    for item in payload["messages"]:
        fields = {f["field"]: f for f in item.get("fields", [])}
        for metric in METRICS:
            if metric.message != item["name"] or item.get("circuit") != (metric.circuit or "bai"):
                continue
            try:
                if item.get("status") != "ok":
                    raise ValueError("ebusd_error")
                # The exporter converts '-' to null. Only the original raw
                # error slots can distinguish 'no fault' from missing data.
                if metric.kind == "errors" and item.get("raw"):
                    fields = parse_verbose(item["raw"])
                result[metric.key] = {"value": extract(metric, fields), "error": None}
            except ValueError as exc:
                result[metric.key] = {"value": None, "error": str(exc)}
    return result
