"""Validate the supplied snapshot without connecting to eBUS or MQTT."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pihavaillant"))
from backend.metrics import parse_snapshot

source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests/fixtures/ebusd-export.json"
print(json.dumps(parse_snapshot(json.loads(source.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
