"""Local recoverable dispatch checkpoint. Not a second project truth source."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterator
from .core import TaskPacket, Target
from .transports import Receipt, Observation


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def instance_lock(path: Path) -> Iterator[None]:
    """OS kernel lock; a crashed process releases it (Windows and POSIX)."""
    lock = path.with_name(path.name + ".coordlock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another FPF coordinator holds this workspace") from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Another FPF coordinator holds this workspace") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class DispatchJournal:
    """Single-writer append-only event journal and current request cache."""
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS dispatches (
            request_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL, role TEXT NOT NULL, attempt INTEGER NOT NULL,
            target TEXT NOT NULL, packet TEXT NOT NULL,
            phase TEXT NOT NULL, receipt TEXT, observation TEXT,
            poll_count INTEGER NOT NULL DEFAULT 0,
            next_poll_at REAL NOT NULL DEFAULT 0,
            updated TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
            UNIQUE(task_id,role,attempt))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS dispatch_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
            at TEXT NOT NULL, phase TEXT NOT NULL, digest TEXT NOT NULL,
            details TEXT NOT NULL)""")
        columns={row[1] for row in self.db.execute("PRAGMA table_info(dispatches)")}
        if "next_poll_at" not in columns:
            self.db.execute("ALTER TABLE dispatches ADD COLUMN next_poll_at REAL NOT NULL DEFAULT 0")
        self.db.commit()

    def close(self):
        self.db.close()

    def _event(self, request_id: str, phase: str, details: str):
        material = (request_id + "|" + phase + "|" + details).encode()
        self.db.execute(
            "INSERT INTO dispatch_events(request_id,at,phase,digest,details) VALUES (?,?,?,?,?)",
            (request_id, utcnow(), phase, hashlib.sha256(material).hexdigest(), details[:500]))

    def row(self, request_id: str) -> dict | None:
        line = self.db.execute("SELECT * FROM dispatches WHERE request_id=?",
                               (request_id,)).fetchone()
        return dict(line) if line else None

    def existing(self, packet: TaskPacket) -> dict | None:
        line = self.db.execute(
            "SELECT * FROM dispatches WHERE task_id=? AND role=? AND attempt=?",
            (packet.task_id, packet.role, packet.attempt)).fetchone()
        if not line:
            return None
        row = dict(line)
        if row["request_id"] != packet.request_id or row["packet"] != packet.brief():
            raise ValueError("Canonical revision/target drift; reconcile before another dispatch")
        return row

    def create(self, packet: TaskPacket, target: Target) -> dict:
        current = self.existing(packet)
        if current:
            return current
        with self.db:
            self.db.execute(
                """INSERT INTO dispatches
                (request_id,task_id,role,attempt,target,packet,phase,updated)
                VALUES(?,?,?,?,?,?,?,?)""",
                (packet.request_id,packet.task_id,packet.role,packet.attempt,
                 json.dumps(vars(target),sort_keys=True),packet.brief(),"CREATED",utcnow()))
            self._event(packet.request_id,"CREATED","Canonical packet prepared")
        return self.row(packet.request_id)

    def set_phase(self, request_id: str, phase: str, *, receipt: Receipt | None = None,
                  observation: Observation | None = None, reason: str = "",
                  increment_poll: bool = False,
                  next_poll_at: float | None = None) -> dict:
        current = self.row(request_id)
        if not current:
            raise ValueError("Dispatch request not registered")
        with self.db:
            self.db.execute("""UPDATE dispatches SET phase=?,receipt=?,observation=?,
                            poll_count=?,next_poll_at=?,updated=?,reason=? WHERE request_id=?""",
                            (phase,
                             json.dumps(vars(receipt),sort_keys=True) if receipt
                                else current["receipt"],
                             json.dumps(vars(observation),sort_keys=True) if observation
                                else current["observation"],
                             current["poll_count"] + int(increment_poll),
                             current["next_poll_at"] if next_poll_at is None else next_poll_at,
                             utcnow(),reason[:500],request_id))
            self._event(request_id,phase,reason)
        return self.row(request_id)

    def events(self, request_id: str) -> list[dict]:
        cur = self.db.execute(
            "SELECT seq,at,phase,digest,details FROM dispatch_events "
            "WHERE request_id=? ORDER BY seq", (request_id,))
        return [dict(r) for r in cur.fetchall()]
