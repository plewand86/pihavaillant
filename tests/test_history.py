import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pihavaillant"))
from backend.history import History


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.h = History(":memory:", max_gap=12)
        self.addCleanup(self.h.close)

    def test_complete_cycle(self):
        for ts, state in [(100,"OFF"),(105,"ON"),(110,"ON"),(115,"OFF"),(120,"OFF")]:
            self.h.observe(state, ts)
        result = self.h.report(100,120)
        self.assertEqual(result["on_seconds"],10)
        self.assertEqual(result["off_seconds"],10)
        self.assertEqual(result["starts"],1)
        self.assertEqual(result["unknown_seconds"],0)
        on = [s for s in result["segments"] if s["state"]=="ON"][0]
        self.assertTrue(on["start_known"] and on["end_known"])

    def test_error_not_counted_as_work(self):
        for ts, state in [(100,"ON"),(105,"ON"),(110,None),(115,"ON"),(120,"ON")]:
            self.h.observe(state,ts)
        result=self.h.report(100,120)
        self.assertEqual(result["on_seconds"],10)
        self.assertEqual(result["unknown_seconds"],10)
        self.assertEqual(result["starts"],0)
        self.assertEqual(len(result["segments"]),2)

    def test_long_gap_and_no_tail_extrapolation(self):
        self.h.observe("ON",100)
        self.h.observe("ON",105)
        self.h.observe("ON",200)
        result=self.h.report(100,210)
        self.assertEqual(result["on_seconds"],5)
        self.assertEqual(result["unknown_seconds"],105)

    def test_clip_across_range_boundary(self):
        for ts, state in [(100,"OFF"),(105,"ON"),(110,"ON"),(115,"OFF")]:
            self.h.observe(state,ts)
        result=self.h.report(107,113)
        self.assertEqual(result["on_seconds"],6)
        self.assertEqual(result["starts"],0)

    def test_restart_does_not_join_running_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"test.sqlite3"
            h=History(path)
            h.observe("ON",100)
            h.observe("ON",105)
            h.close()
            h=History(path)
            h.observe("ON",110)
            h.observe("OFF",115)
            result=h.report(100,115)
            self.assertEqual(result["on_seconds"],10)
            self.assertEqual(result["unknown_seconds"],5)
            self.assertEqual(len(result["segments"]),3)
            h.close()

    def test_ongoing_is_fresh_only(self):
        self.h.observe("ON",100)
        self.h.observe("ON",105)
        with patch("backend.history.time.time",return_value=110):
            self.assertTrue(self.h.report(100,110)["segments"][0]["ongoing"])
        with patch("backend.history.time.time",return_value=200):
            self.assertFalse(self.h.report(100,200)["segments"][0]["ongoing"])

    def test_retention_and_temperatures(self):
        self.h.add_temperatures({"flow_temp":{"value":60}},100)
        self.h.add_temperatures({"flow_temp":{"value":None}},105)
        self.assertEqual(self.h.temperatures(99,106)[1]["flow_temp"],None)
        self.h.observe("OFF",100)
        self.h.observe("OFF",100+91*86400)
        self.assertEqual(self.h.temperatures(99,106),[])

    def test_room_history_preserves_older_records_and_gaps(self):
        self.h.db.execute("INSERT INTO temperatures VALUES(?,?)", (100, '{"flow_temp":60}'))
        self.h.add_temperatures({"room_temp": {"value": 24.1}}, 105)
        self.h.add_temperatures({"room_temp": {"value": None}}, 110)
        rows = self.h.temperatures(99, 111)
        self.assertEqual(rows[0]["flow_temp"], 60)
        self.assertNotIn("room_temp", rows[0])
        self.assertEqual(rows[1]["room_temp"], 24.1)
        self.assertIsNone(rows[2]["room_temp"])

    def test_temperature_response_bounded(self):
        for i in range(1600):
            self.h.add_temperatures({"flow_temp":{"value":i%100}},100+i)
        self.assertLessEqual(len(self.h.temperatures(100,1700)),801)

    def test_clock_rollback_does_not_double_count(self):
        for ts in [100,105,90,95,100,105,110,115]:
            self.h.observe("ON",ts)
        report=self.h.report(90,120)
        self.assertEqual(report["on_seconds"],10)
        self.assertEqual(report["unknown_seconds"],20)

    def test_mode_switch_is_not_an_ignition(self):
        self.h.observe("OFF", 100)
        self.h.observe("ON", 105, "heating")
        self.h.observe("ON", 110, "heating")
        self.h.observe("ON", 115, "dhw")
        self.h.observe("ON", 120, "unknown")
        self.h.observe("OFF", 125)
        result = self.h.report(100, 125)
        self.assertEqual(result["starts"], 1)
        self.assertEqual(result["heating_seconds"], 10)
        self.assertEqual(result["dhw_seconds"], 5)
        self.assertEqual(result["unclassified_seconds"], 5)
        self.assertEqual(result["on_seconds"], 20)
        clipped = self.h.report(108, 122)
        self.assertEqual(clipped["heating_seconds"], 7)
        self.assertEqual(clipped["unclassified_seconds"], 2)

    def test_old_database_migration(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.sqlite3"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE intervals(id INTEGER PRIMARY KEY,start REAL,end REAL,state TEXT,start_known INTEGER,end_known INTEGER DEFAULT 0)")
            db.execute("INSERT INTO intervals VALUES(1,100,110,'ON',1,1)")
            db.commit()
            db.close()
            h = History(path)
            result = h.report(99, 115)
            self.assertEqual(result["unclassified_seconds"], 10)
            self.assertEqual(result["starts"], 1)
            h.close()
            h = History(path)
            self.assertEqual(h.report(99, 115)["starts"], 1)
            h.close()
