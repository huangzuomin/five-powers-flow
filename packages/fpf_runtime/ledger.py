"""Durable single-slice state transitions and append-only local event log."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
TERMINAL = {"READY_FOR_OWNER_REVIEW", "BLOCKED", "BLOCKED_RECONCILIATION"}
IN_FLIGHT = {"PLAN_RUNNING", "DEV_RUNNING", "QA_RUNNING"}


class Ledger:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), timeout=10)
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.execute("CREATE TABLE IF NOT EXISTS slices (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
                          "slice_id TEXT, at TEXT, state TEXT, note TEXT)")
        self.conn.commit()

    def create(self, slice_id: str, goal: str, base_sha: str, max_attempts: int) -> dict:
        if not ID_PATTERN.fullmatch(slice_id) or not goal.strip() or max_attempts < 1:
            raise ValueError("Invalid slice id, goal or attempt limit")
        found = self.read(slice_id)
        if found:
            if found["goal"] != goal or found["base_sha"] != base_sha:
                raise ValueError("Slice ID is already used with a different goal/base")
            return found
        state = {"id": slice_id, "goal": goal, "base_sha": base_sha, "head_sha": None,
                 "phase": "NEW", "attempt": 0, "max_attempts": max_attempts,
                 "sessions": {}, "dev_order": "", "qa_plan": "", "last_failure": "", "report": ""}
        try:
            with self.conn:
                self.conn.execute("INSERT INTO slices VALUES (?,?)",
                                  (slice_id, json.dumps(state)))
                self._event(slice_id, "NEW", "Created")
        except sqlite3.IntegrityError:
            return self.read(slice_id)
        return state

    def read(self, slice_id: str) -> dict | None:
        row = self.conn.execute("SELECT data FROM slices WHERE id=?", (slice_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, state: dict, phase: str, note: str = "") -> dict:
        state = {**state, "phase": phase}
        with self.conn:
            cur = self.conn.execute("UPDATE slices SET data=? WHERE id=?",
                                    (json.dumps(state), state["id"]))
            if cur.rowcount != 1:
                raise RuntimeError("Slice disappeared during update")
            self._event(state["id"], phase, note[:400])
        return state

    def _event(self, task: str, phase: str, note: str):
        self.conn.execute("INSERT INTO events (slice_id,at,state,note) VALUES (?,?,?,?)",
                          (task, datetime.now(timezone.utc).isoformat(), phase, note))

    def events(self, task: str) -> list[dict]:
        rows = self.conn.execute("SELECT at,state,note FROM events WHERE slice_id=? ORDER BY seq", (task,))
        return [dict(zip(("at", "state", "note"), row)) for row in rows]
