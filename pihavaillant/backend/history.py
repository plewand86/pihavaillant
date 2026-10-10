"""Persistent observed burner intervals. Unknown time is never filled as ON."""
import json
import sqlite3
import time
from pathlib import Path


class History:
    def __init__(self, path, max_gap=17, retention_days=90):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS intervals (
                id INTEGER PRIMARY KEY, start REAL NOT NULL, end REAL NOT NULL,
                state TEXT NOT NULL, start_known INTEGER NOT NULL,
                end_known INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS intervals_end ON intervals(end);
            CREATE TABLE IF NOT EXISTS temperatures(ts REAL PRIMARY KEY, payload TEXT NOT NULL);
        """)
        self.active = None  # Never join intervals across a process restart.
        self.last = None
        self.max_gap = max_gap
        self.retention_days = retention_days
        self.last_prune = 0
        self.latest = self.db.execute("SELECT MAX(end) FROM intervals").fetchone()[0]

    def observe(self, state, ts=None):
        ts = time.time() if ts is None else ts
        if self.latest is not None and ts <= self.latest:
            # Clock rollback: wait for the clock to catch up, never overlap time.
            self.active = None
            self.last = None
            return
        self.latest = ts
        previous = self.last
        continuous = previous is not None and 0 < ts - previous[0] <= self.max_gap
        if not continuous or state not in ("ON", "OFF"):
            self.active = None
        if state in ("ON", "OFF"):
            if self.active is not None and continuous:
                self.db.execute("UPDATE intervals SET end=? WHERE id=?", (ts, self.active))
                if state != previous[1]:
                    self.db.execute("UPDATE intervals SET end_known=1 WHERE id=?", (self.active,))
                    self.active = None
            if self.active is None:
                known = continuous and previous[1] in ("ON", "OFF") and state != previous[1]
                cursor = self.db.execute("INSERT INTO intervals(start,end,state,start_known) VALUES(?,?,?,?)", (ts, ts, state, int(known)))
                self.active = cursor.lastrowid
        self.last = (ts, state)
        self.db.commit()
        if ts - self.last_prune > 3600:
            cutoff = ts - self.retention_days * 86400
            self.db.execute("DELETE FROM intervals WHERE end < ?", (cutoff,))
            self.db.execute("DELETE FROM temperatures WHERE ts < ?", (cutoff,))
            self.db.commit()
            self.last_prune = ts

    def add_temperatures(self, values, ts=None):
        ts = time.time() if ts is None else ts
        payload = {key: values.get(key, {}).get("value") for key in ("flow_temp", "return_temp", "storage_temp", "modulation")}
        self.db.execute("INSERT OR REPLACE INTO temperatures VALUES(?,?)", (ts, json.dumps(payload)))
        self.db.commit()

    def temperatures(self, start, end):
        # One actual observation per time bucket; do not invent averaged samples.
        width = max(1, (end - start) / 800)
        rows = self.db.execute("""SELECT ts,payload FROM temperatures WHERE ts IN
            (SELECT MAX(ts) FROM temperatures WHERE ts>=? AND ts<=? GROUP BY CAST((ts-?)/? AS INTEGER))
            ORDER BY ts""", (start, end, start, width))
        return [{"ts": ts, **json.loads(payload)} for ts, payload in rows]

    def report(self, start, end):
        end = min(end, time.time())
        if end <= start:
            raise ValueError("Invalid time range")
        totals = self.db.execute("""SELECT state,SUM(MAX(0,MIN(end,?)-MAX(start,?)))
            FROM intervals WHERE end>=? AND start<=? GROUP BY state""", (end, start, start, end)).fetchall()
        sums = dict(totals)
        starts = self.db.execute("SELECT COUNT(*) FROM intervals WHERE state='ON' AND start_known=1 AND start>=? AND start<=?", (start, end)).fetchone()[0]
        count = self.db.execute("SELECT COUNT(*) FROM intervals WHERE end>=? AND start<=?", (start, end)).fetchone()[0]
        rows = self.db.execute("SELECT id,start,end,state,start_known,end_known FROM intervals WHERE end>=? AND start<=? ORDER BY start DESC LIMIT 5000", (start, end)).fetchall()
        segments = [{"start": a, "end": b, "state": state, "start_known": bool(sk), "end_known": bool(ek),
                     "ongoing": ident == self.active and self.last is not None and 0 <= time.time() - self.last[0] <= self.max_gap,
                     "seconds_in_range": max(0, min(b, end) - max(a, start))}
                    for ident, a, b, state, sk, ek in reversed(rows)]
        known = sums.get("ON", 0) + sums.get("OFF", 0)
        return {"start": start, "end": end, "on_seconds": sums.get("ON", 0), "off_seconds": sums.get("OFF", 0),
                "unknown_seconds": max(0, end - start - known), "starts": starts,
                "coverage": min(100, known * 100 / (end - start)), "segments": segments,
                "truncated": count > 5000, "max_gap": self.max_gap, "retention_days": self.retention_days}

    def close(self):
        self.db.close()
