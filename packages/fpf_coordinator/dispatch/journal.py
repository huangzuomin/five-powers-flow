# -*- coding: utf-8 -*-
"""FPF Autonomous Engineering Coordinator SQLite Journal & CAS Concurrency Engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any
import uuid

from .states import Phase


class ConcurrencyConflictError(Exception):
    """Raised when a CAS optimistic lock precondition fails."""


class AttemptLimitExceededError(Exception):
    """Raised when attempts exceed max_attempts."""


class TaskNotFoundError(Exception):
    """Raised when a task_id is not found in the journal."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    project_id: str
    phase: Phase
    version: int
    attempt: int
    max_attempts: int
    baseline_sha: str
    head_sha: str | None
    last_failure: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Lease:
    task_id: str
    owner_id: str
    lease_token: str
    acquired_at: str
    expires_at: str

    @property
    def is_expired(self) -> bool:
        exp = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) > exp


@dataclass(frozen=True)
class IntentRecord:
    request_id: str
    task_id: str
    idempotency_key: str
    role: str
    action: str
    phase: Phase
    payload: dict
    receipt: dict | None
    status: str  # PENDING, DISPATCHED, SETTLED, FAILED
    created_at: str
    updated_at: str


class StateJournal:
    """Thread-safe SQLite persistent state journal with CAS concurrency control."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    attempt INTEGER NOT NULL DEFAULT 1,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    baseline_sha TEXT NOT NULL,
                    head_sha TEXT,
                    last_failure TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leases (
                    task_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    lease_token TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS intents (
                    request_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    receipt_json TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
            """)
            self._conn.commit()

    def create_task(
        self,
        task_id: str,
        project_id: str,
        baseline_sha: str,
        phase: Phase = Phase.TASK_INTAKE,
        max_attempts: int = 3,
    ) -> TaskRecord:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO tasks (
                    task_id, project_id, phase, version, attempt, max_attempts,
                    baseline_sha, head_sha, last_failure, created_at, updated_at
                ) VALUES (?, ?, ?, 1, 1, ?, ?, NULL, '', ?, ?);
                """,
                (task_id, project_id, phase.value, max_attempts, baseline_sha, now, now),
            )
            self._conn.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> TaskRecord:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM tasks WHERE task_id = ?;", (task_id,))
            row = cur.fetchone()
        if not row:
            raise TaskNotFoundError(f"Task {task_id!r} not found in state journal")
        return TaskRecord(
            task_id=row["task_id"],
            project_id=row["project_id"],
            phase=Phase(row["phase"]),
            version=row["version"],
            attempt=row["attempt"],
            max_attempts=row["max_attempts"],
            baseline_sha=row["baseline_sha"],
            head_sha=row["head_sha"],
            last_failure=row["last_failure"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update_phase(
        self,
        task_id: str,
        expected_version: int,
        new_phase: Phase,
        head_sha: str | None = None,
        last_failure: str = "",
    ) -> int:
        """Atomic CAS (Compare-And-Swap) phase update.

        Raises ConcurrencyConflictError if expected_version does not match current version.
        Returns the new version number upon success.
        """
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            if head_sha is not None:
                cur.execute(
                    """
                    UPDATE tasks
                    SET phase = ?, version = version + 1, head_sha = ?, last_failure = ?, updated_at = ?
                    WHERE task_id = ? AND version = ?;
                    """,
                    (new_phase.value, head_sha, last_failure, now, task_id, expected_version),
                )
            else:
                cur.execute(
                    """
                    UPDATE tasks
                    SET phase = ?, version = version + 1, last_failure = ?, updated_at = ?
                    WHERE task_id = ? AND version = ?;
                    """,
                    (new_phase.value, last_failure, now, task_id, expected_version),
                )
            if cur.rowcount == 0:
                self._conn.rollback()
                raise ConcurrencyConflictError(
                    f"CAS conflict for task {task_id!r}: expected version {expected_version}"
                )
            self._conn.commit()
            return expected_version + 1

    def increment_attempt(
        self,
        task_id: str,
        expected_version: int,
        last_failure: str = "",
    ) -> int:
        """Monotonically increment attempt counter under CAS control.

        If attempt reaches max_attempts, state transitions to BLOCKED.
        Returns the new version number.
        """
        task = self.get_task(task_id)
        if task.version != expected_version:
            raise ConcurrencyConflictError(f"CAS conflict for task {task_id!r}")
        if task.attempt >= task.max_attempts:
            # Force transition to BLOCKED
            return self.update_phase(
                task_id=task_id,
                expected_version=expected_version,
                new_phase=Phase.BLOCKED,
                last_failure=f"Max attempts ({task.max_attempts}) reached: {last_failure}",
            )

        now = utc_now_iso()
        new_attempt = task.attempt + 1
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE tasks
                SET attempt = ?, version = version + 1, last_failure = ?, updated_at = ?
                WHERE task_id = ? AND version = ?;
                """,
                (new_attempt, last_failure, now, task_id, expected_version),
            )
            if cur.rowcount == 0:
                self._conn.rollback()
                raise ConcurrencyConflictError(f"CAS conflict for task {task_id!r}")
            self._conn.commit()
            return expected_version + 1

    # Lease management
    def acquire_lease(self, task_id: str, owner_id: str, ttl_seconds: int = 45) -> tuple[bool, str | None]:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=ttl_seconds)).isoformat()
        token = str(uuid.uuid4())

        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM leases WHERE task_id = ?;", (task_id,))
            row = cur.fetchone()

            if row:
                exp = datetime.fromisoformat(row["expires_at"])
                if now > exp or row["owner_id"] == owner_id:
                    # Lease expired or owned by same caller: re-acquire
                    cur.execute(
                        """
                        UPDATE leases
                        SET owner_id = ?, lease_token = ?, acquired_at = ?, expires_at = ?
                        WHERE task_id = ?;
                        """,
                        (owner_id, token, now_iso, expires_iso, task_id),
                    )
                    self._conn.commit()
                    return True, token
                # Still active and owned by another
                return False, None
            else:
                cur.execute(
                    """
                    INSERT INTO leases (task_id, owner_id, lease_token, acquired_at, expires_at)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (task_id, owner_id, token, now_iso, expires_iso),
                )
                self._conn.commit()
                return True, token

    def renew_lease(self, task_id: str, owner_id: str, lease_token: str, ttl_seconds: int = 45) -> bool:
        now = datetime.now(timezone.utc)
        expires_iso = (now + timedelta(seconds=ttl_seconds)).isoformat()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE leases
                SET expires_at = ?
                WHERE task_id = ? AND owner_id = ? AND lease_token = ?;
                """,
                (expires_iso, task_id, owner_id, lease_token),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def release_lease(self, task_id: str, owner_id: str, lease_token: str) -> bool:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                DELETE FROM leases
                WHERE task_id = ? AND owner_id = ? AND lease_token = ?;
                """,
                (task_id, owner_id, lease_token),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def is_lease_active(self, task_id: str) -> tuple[bool, str | None]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM leases WHERE task_id = ?;", (task_id,))
            row = cur.fetchone()
        if not row:
            return False, None
        exp = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) <= exp:
            return True, row["owner_id"]
        return False, None

    # Intent logging (Write-Ahead Intent before dispatch)
    def record_intent(
        self,
        task_id: str,
        request_id: str,
        idempotency_key: str,
        role: str,
        action: str,
        phase: Phase,
        payload: dict,
    ) -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO intents (
                    request_id, task_id, idempotency_key, role, action, phase,
                    payload_json, receipt_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'PENDING', ?, ?);
                """,
                (
                    request_id,
                    task_id,
                    idempotency_key,
                    role,
                    action,
                    phase.value,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            self._conn.commit()

    def mark_intent_dispatched(self, request_id: str, receipt: dict) -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE intents
                SET receipt_json = ?, status = 'DISPATCHED', updated_at = ?
                WHERE request_id = ?;
                """,
                (json.dumps(receipt, ensure_ascii=False), now, request_id),
            )
            self._conn.commit()

    def mark_intent_settled(self, request_id: str, outcome: str = "SETTLED") -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE intents
                SET status = ?, updated_at = ?
                WHERE request_id = ?;
                """,
                (outcome, now, request_id),
            )
            self._conn.commit()

    def get_intent(self, request_id: str) -> IntentRecord | None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM intents WHERE request_id = ?;", (request_id,))
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_intent(row)

    def get_intent_by_idempotency_key(self, idempotency_key: str) -> IntentRecord | None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM intents WHERE idempotency_key = ?;", (idempotency_key,))
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_intent(row)

    def get_pending_intents(self, task_id: str | None = None) -> list[IntentRecord]:
        with self._lock:
            cur = self._conn.cursor()
            if task_id:
                cur.execute(
                    "SELECT * FROM intents WHERE task_id = ? AND status IN ('PENDING', 'DISPATCHED') ORDER BY created_at ASC;",
                    (task_id,),
                )
            else:
                cur.execute(
                    "SELECT * FROM intents WHERE status IN ('PENDING', 'DISPATCHED') ORDER BY created_at ASC;"
                )
            rows = cur.fetchall()
        return [self._row_to_intent(r) for r in rows]

    def _row_to_intent(self, row: sqlite3.Row) -> IntentRecord:
        receipt = json.loads(row["receipt_json"]) if row["receipt_json"] else None
        return IntentRecord(
            request_id=row["request_id"],
            task_id=row["task_id"],
            idempotency_key=row["idempotency_key"],
            role=row["role"],
            action=row["action"],
            phase=Phase(row["phase"]),
            payload=json.loads(row["payload_json"]),
            receipt=receipt,
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # Checkpoint management
    def save_checkpoint(self, task_id: str, phase: Phase, version: int, snapshot: dict) -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO checkpoints (task_id, phase, version, snapshot_json, recorded_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (task_id, phase.value, version, json.dumps(snapshot, ensure_ascii=False), now),
            )
            self._conn.commit()

    def get_latest_checkpoint(self, task_id: str) -> tuple[Phase, int, dict] | None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT phase, version, snapshot_json FROM checkpoints
                WHERE task_id = ? ORDER BY id DESC LIMIT 1;
                """,
                (task_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return Phase(row["phase"]), row["version"], json.loads(row["snapshot_json"])
