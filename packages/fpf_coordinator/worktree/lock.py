# -*- coding: utf-8 -*-
"""Repository-level FINALIZATION LOCK.

Two files, two responsibilities: ``lifecycle.lock`` carries *ownership* only
and is never rewritten; the heartbeat file says whether the owner is still
alive and is allowed to change.  Ownership is decided by ``run_id`` plus the
lock file's ``(st_dev, st_ino)``, never by a heartbeat timestamp: a "stale"
heartbeat is a question about liveness, not a grant of authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import arbiter as arbiter_mod
from .noreplace import DestinationExists, NoReplaceUnsupported, rename_noreplace

LOCK_NAME = "lifecycle.lock"
HEARTBEAT_PREFIX = "lifecycle.lock.hb."
RECEIPT_NAME = "lock-release.json"

LOCK_OK = "OK"
LOCK_HELD = "LOCK_HELD"
LOCK_UNREADABLE = "LOCK_UNREADABLE"
LOCK_STALE_REQUIRES_HUMAN = "LOCK_STALE_REQUIRES_HUMAN"
LOCK_LOST = "LOCK_LOST"
LOCK_OWNERSHIP_REVOKED = "LOCK_OWNERSHIP_REVOKED"
LOCK_RELEASE_NAME_COLLISION = "LOCK_RELEASE_NAME_COLLISION"
LOCK_RELEASE_FAILED = "LOCK_RELEASE_FAILED"
LOCK_HEARTBEAT_FAILED = "LOCK_HEARTBEAT_FAILED"
BREAK_LOCK_IDENTITY_MISMATCH = "BREAK_LOCK_IDENTITY_MISMATCH"
BREAK_LOCK_HOLDER_ALIVE = "BREAK_LOCK_HOLDER_ALIVE"
BREAK_LOCK_LIVENESS_UNVERIFIABLE = "BREAK_LOCK_LIVENESS_UNVERIFIABLE"
BREAK_LOCK_REMOVE_IN_FLIGHT = "BREAK_LOCK_REMOVE_IN_FLIGHT"
BREAK_LOCK_ARBITER_DENIED = "BREAK_LOCK_ARBITER_DENIED"
ORPHAN_CLAIM = "ORPHAN_CLAIM"


class LockError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)


@dataclass(frozen=True)
class Lock:
    common_dir: str
    run_id: str
    dev: int
    ino: int
    pid: int
    process_start_time: str
    seq: int = 0
    content_sha256: str = ""

    @property
    def path(self) -> Path:
        return Path(self.common_dir) / LOCK_NAME

    @property
    def heartbeat_path(self) -> Path:
        return Path(self.common_dir) / f"{HEARTBEAT_PREFIX}{self.run_id}"

    @property
    def consuming_path(self) -> Path:
        return Path(self.common_dir) / f"{LOCK_NAME}.consuming.{self.run_id}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _read_json(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise LockError(LOCK_LOST, "lock file missing") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LockError(LOCK_UNREADABLE, "lock is not valid JSON") from exc


def read_lock(common_dir) -> dict:
    return _read_json(Path(common_dir) / LOCK_NAME)


def acquire(common_dir, run_id: str, *, pid: int, process_start_time: str) -> Lock:
    base = Path(common_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / LOCK_NAME
    body = {
        "lock_version": "fpf.lifecycle-lock/v2",
        "run_id": run_id,
        "pid": int(pid),
        "process_start_time": str(process_start_time),
        "acquired_at": _now(),
    }
    payload = json.dumps(body, sort_keys=True, indent=2).encode("utf-8")
    try:
        handle = open(path, "xb")
    except FileExistsError as exc:
        record = None
        try:
            record = _read_json(path)
        except LockError as read_exc:
            raise read_exc from exc
        raise LockError(LOCK_HELD, f"held by {record.get('run_id')}") from exc
    with handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    stat = path.stat()
    lock = Lock(str(base), run_id, stat.st_dev, stat.st_ino, int(pid),
                str(process_start_time),
                content_sha256=hashlib.sha256(payload).hexdigest())
    heartbeat(lock, seq=0)
    return lock


def heartbeat(lock: Lock, *, seq: int) -> Lock:
    body = {
        "run_id": lock.run_id,
        "seq": int(seq),
        "last": _now(),
        "pid": lock.pid,
        "process_start_time": lock.process_start_time,
    }
    tmp = lock.heartbeat_path.with_name(lock.heartbeat_path.name + ".tmp")
    try:
        with open(tmp, "wb") as handle:
            handle.write(json.dumps(body, sort_keys=True).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, lock.heartbeat_path)
    except OSError as exc:
        raise LockError(LOCK_HEARTBEAT_FAILED, str(exc)) from exc
    return Lock(lock.common_dir, lock.run_id, lock.dev, lock.ino, lock.pid,
                lock.process_start_time, seq, lock.content_sha256)


def heartbeat_state(lock: Lock) -> dict | None:
    try:
        return _read_json(lock.heartbeat_path)
    except LockError:
        return None


def reverify(lock: Lock) -> str:
    """Ownership is ``run_id`` + the lock object's stable identity."""
    try:
        record = read_lock(lock.common_dir)
        stat = lock.path.stat()
    except LockError:
        return LOCK_LOST
    except FileNotFoundError:
        return LOCK_LOST
    if str(record.get("run_id")) != lock.run_id:
        return LOCK_OWNERSHIP_REVOKED
    if (stat.st_dev, stat.st_ino) != (lock.dev, lock.ino):
        return LOCK_OWNERSHIP_REVOKED
    if lock.content_sha256:
        try:
            current = lock.path.read_bytes()
        except FileNotFoundError:
            return LOCK_LOST
        if hashlib.sha256(current).hexdigest() != lock.content_sha256:
            return LOCK_OWNERSHIP_REVOKED
    return LOCK_OK


def _default_start_time(pid: int) -> str | None:
    """Best-effort process start time; ``None`` means "cannot tell"."""
    if os.name == "nt":
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Process -Id {int(pid)} -ErrorAction Stop)"
             f".StartTime.ToUniversalTime().ToString('o')"],
            capture_output=True, text=True)
        text = (result.stdout or "").strip()
        return text or None
    try:
        stat = open(f"/proc/{int(pid)}/stat", encoding="utf-8").read()
    except OSError:
        return None
    fields = stat.rsplit(")", 1)[-1].split()
    return fields[19] if len(fields) > 19 else None


def start_time_for(pid: int) -> str:
    """The process start time recorded in the lock.

    Never substitute a wall-clock timestamp: doing so makes every live holder
    look dead to ``pid_liveness`` and turns break-lock into a delete-anytime
    primitive.  ``""`` means "cannot tell" and stays fail-closed downstream.
    """
    value = _default_start_time(int(pid))
    return str(value) if value else ""


def pid_liveness(pid: int, process_start_time: str, probe=None) -> str:
    """``ALIVE`` / ``DEAD`` / ``UNVERIFIABLE``.

    A PID that exists but has a different start time is a *reused* PID: the
    process that took the lock is gone, so the answer is DEAD, not ALIVE.
    """
    if not pid or pid <= 0:
        return "UNVERIFIABLE"
    if not str(process_start_time).strip():
        return "UNVERIFIABLE"
    try:
        current = probe(pid) if probe else _default_start_time(pid)
    except Exception:  # noqa: BLE001 - any probe failure is "cannot tell"
        return "UNVERIFIABLE"
    if current is None:
        return "DEAD"
    if str(current) != str(process_start_time):
        return "DEAD"
    return "ALIVE"


def begin_consuming(lock: Lock) -> Path:
    """Step 11.5: declare "removal in flight" before touching the worktree."""
    body = {
        "run_id": lock.run_id,
        "lock_dev": lock.dev,
        "lock_ino": lock.ino,
        "pid": lock.pid,
        "process_start_time": lock.process_start_time,
        "created_at": _now(),
    }
    path = lock.consuming_path
    try:
        with open(path, "xb") as handle:
            handle.write(json.dumps(body, sort_keys=True, indent=2).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise LockError(ORPHAN_CLAIM, str(path)) from exc
    state = reverify(lock)
    if state != LOCK_OK:
        path.unlink(missing_ok=True)
        raise LockError(state)
    return path


def remove_in_flight(common_dir, run_id: str | None = None) -> list[Path]:
    base = Path(common_dir)
    pattern = f"{LOCK_NAME}.consuming.*" if run_id is None else \
        f"{LOCK_NAME}.consuming.{run_id}"
    return sorted(base.glob(pattern))


def break_lock(common_dir, *, expected_dev: int, expected_ino: int, by: str,
               reason: str, liveness, stale_after_seconds: int = 300,
               assume_dead: bool = False, arbiter_root=None) -> dict:
    """Revoke a lock, but only when the holder is provably not running.

    ``liveness(pid, process_start_time)`` returns ``ALIVE``, ``DEAD`` or
    ``UNVERIFIABLE``.  A heartbeat older than ``stale_after_seconds`` only
    *asks the question*; it never answers it.
    """
    base = Path(common_dir)
    try:
        record = read_lock(base)
        stat = (base / LOCK_NAME).stat()
    except FileNotFoundError as exc:
        raise LockError(LOCK_LOST) from exc
    except LockError:
        raise
    if (stat.st_dev, stat.st_ino) != (int(expected_dev), int(expected_ino)):
        raise LockError(BREAK_LOCK_IDENTITY_MISMATCH)
    run_id = str(record.get("run_id"))
    if remove_in_flight(base, run_id):
        raise LockError(BREAK_LOCK_REMOVE_IN_FLIGHT)

    heartbeat_age = _heartbeat_age(base / f"{HEARTBEAT_PREFIX}{run_id}")
    verdict = liveness(int(record.get("pid") or 0),
                       str(record.get("process_start_time") or ""))
    proof = {"liveness": verdict, "heartbeat_age_seconds": heartbeat_age,
             "assume_dead": bool(assume_dead)}
    if verdict == "ALIVE":
        raise LockError(BREAK_LOCK_HOLDER_ALIVE)
    if verdict == "UNVERIFIABLE" and not assume_dead:
        if heartbeat_age is None or heartbeat_age <= stale_after_seconds:
            raise LockError(LOCK_STALE_REQUIRES_HUMAN)
        raise LockError(BREAK_LOCK_LIVENESS_UNVERIFIABLE)
    if verdict == "UNVERIFIABLE" and assume_dead:
        proof["override"] = "assume_dead"

    revoked = None
    if arbiter_root is not None:
        # A revocation competes with a delete claim for one name; the loser
        # must not act, so this happens strictly before the lock is renamed.
        revoked = arbiter_mod.build_record(
            arbiter_mod.REVOKE, run_id, int(expected_dev), int(expected_ino),
            os.getpid(), _default_start_time(os.getpid()) or "")
        outcome = arbiter_mod.acquire(arbiter_root, revoked)
        if not outcome.won:
            raise LockError(
                BREAK_LOCK_ARBITER_DENIED,
                f"{outcome.decision_seen}:{outcome.run_id_seen}:{outcome.reason}")

    target = base / f"{LOCK_NAME}.break.{_stamp()}.{run_id}"
    try:
        rename_noreplace(base / LOCK_NAME, target)
    except NoReplaceUnsupported as exc:
        if revoked is not None:
            arbiter_mod.release(arbiter_root, revoked, arbiter_mod.ABORTED)
        raise LockError("RENAME_NOREPLACE_UNSUPPORTED", str(exc)) from exc
    except DestinationExists as exc:
        if revoked is not None:
            arbiter_mod.release(arbiter_root, revoked, arbiter_mod.ABORTED)
        raise LockError(LOCK_RELEASE_NAME_COLLISION, str(exc)) from exc
    proof.update({
        "by": by,
        "reason": reason,
        "revoked_as": target.name,
        "record_sha256": hashlib.sha256(_canonical(record)).hexdigest(),
    })
    (base / f"{target.name}.proof.json").write_text(
        json.dumps(proof, sort_keys=True, indent=2), encoding="utf-8")
    if revoked is not None:
        arbiter_mod.release(arbiter_root, revoked, "revoked")
    return proof


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _heartbeat_age(path: Path) -> float | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        moment = datetime.strptime(data["last"], "%Y-%m-%dT%H:%M:%SZ")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError):
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - moment).total_seconds()


def release(lock: Lock, *, audit: dict) -> dict:
    """Archive (never unlink) the lock and heartbeat, then bind the receipt."""
    state = reverify(lock)
    if state != LOCK_OK:
        raise LockError(state)
    stamp = _stamp()
    released = Path(lock.common_dir) / f"{LOCK_NAME}.released.{stamp}.{lock.run_id}"
    try:
        rename_noreplace(lock.path, released)
    except DestinationExists as exc:
        raise LockError(LOCK_RELEASE_NAME_COLLISION, str(exc)) from exc
    except NoReplaceUnsupported as exc:
        raise LockError("RENAME_NOREPLACE_UNSUPPORTED", str(exc)) from exc
    except OSError as exc:
        raise LockError(LOCK_RELEASE_FAILED, str(exc)) from exc
    hb_released = Path(lock.common_dir) / \
        f"{HEARTBEAT_PREFIX}released.{stamp}.{lock.run_id}"
    try:
        rename_noreplace(lock.heartbeat_path, hb_released)
    except DestinationExists as exc:
        raise LockError(LOCK_RELEASE_NAME_COLLISION, str(exc)) from exc
    except FileNotFoundError:
        hb_released = None
    except OSError as exc:
        raise LockError("HEARTBEAT_ARCHIVE_FAILED", str(exc)) from exc
    released_bytes = released.read_bytes()
    receipt = {
        "run_id": lock.run_id,
        "released_at": _now(),
        "released_path": str(released),
        "released_bytes": len(released_bytes),
        "released_sha256": hashlib.sha256(released_bytes).hexdigest(),
        "lock_content_sha256": hashlib.sha256(released_bytes).hexdigest(),
        "heartbeat_path": str(hb_released) if hb_released else None,
        "heartbeat_bytes": hb_released.stat().st_size if hb_released else 0,
        "heartbeat_sha256": hashlib.sha256(hb_released.read_bytes()).hexdigest()
        if hb_released else None,
        "heartbeat_semantics": "last_captured_at_archive",
        "audit_path": audit.get("audit_path"),
        "audit_bytes": audit.get("audit_bytes"),
        "audit_sha256": audit.get("audit_sha256"),
        "lock_state": "LOCK_AND_HEARTBEAT_ARCHIVED_RECEIPT_PENDING",
    }
    (Path(lock.common_dir) / RECEIPT_NAME).write_text(
        json.dumps(receipt, sort_keys=True, indent=2), encoding="utf-8")
    return receipt


def orphan_heartbeats(common_dir, live_run_id: str | None = None) -> list[str]:
    base = Path(common_dir)
    out = []
    for path in sorted(base.glob(f"{HEARTBEAT_PREFIX}*")):
        name = path.name
        if ".released." in name or ".break." in name:
            continue
        run_id = name[len(HEARTBEAT_PREFIX):]
        if live_run_id and run_id == live_run_id:
            continue
        if not (base / LOCK_NAME).exists() or live_run_id != run_id:
            out.append(run_id)
    return out
