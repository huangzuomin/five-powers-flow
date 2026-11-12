# -*- coding: utf-8 -*-
"""Single-name arbitration between a delete claim and a lock revocation.

Two actors must never both believe they may act: the holder removing a
worktree, and an operator revoking that holder's lock.  Checking each other's
state is not enough -- a read and the write that follows it are two operations,
so an interleaving always exists where both reads look safe and both writes
succeed.

The fix is to stop inspecting the other side and start competing for one name.
Both parties pre-write a complete candidate record, then attempt an atomic
no-replace rename onto ``lifecycle.arbiter``.  Exactly one wins; the loser must
read the winner's record and obey it.

Winning the name is *not* an authorization to act on a lock.  Authorization is
bound to the original lock identity (run_id, device, inode).  The arbiter name
is reusable; the authorization is not.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .noreplace import DestinationExists, rename_noreplace

ARBITER_NAME = "lifecycle.arbiter"
ARBITER_VERSION = "fpf.lifecycle-arbiter/v1"

CLAIM = "CLAIM"
REVOKE = "REVOKE"


class ArbiterError(RuntimeError):
    pass


class ArbiterUnreadable(ArbiterError):
    """The winning record is missing, truncated, or fails its digest."""


@dataclass(frozen=True)
class Outcome:
    won: bool
    decision_seen: str | None
    run_id_seen: str | None
    reason: str


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _digest(body: dict) -> str:
    import hashlib
    return hashlib.sha256(_canonical(body)).hexdigest()


def build_record(decision: str, run_id: str, lock_dev: int, lock_ino: int,
                 pid: int, process_start_time: str,
                 targets: list[str] | None = None) -> dict:
    if decision not in (CLAIM, REVOKE):
        raise ValueError(f"unknown decision: {decision!r}")
    body = {
        "arbiter_version": ARBITER_VERSION,
        "decision": decision,
        "run_id": str(run_id),
        "lock_dev": int(lock_dev),
        "lock_ino": int(lock_ino),
        "pid": int(pid),
        "process_start_time": str(process_start_time),
        "targets": list(targets or []),
        "decided_at": _now(),
    }
    body["content_sha256"] = _digest(body)
    return body


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_candidate(root: Path, record: dict) -> Path:
    name = f"{ARBITER_NAME}.candidate.{record['decision']}.{record['run_id']}"
    path = root / name
    payload = json.dumps(record, sort_keys=True, indent=2,
                         ensure_ascii=False).encode("utf-8")
    with open(path, "xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def read_arbiter(root: Path) -> dict:
    path = Path(root) / ARBITER_NAME
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise ArbiterUnreadable("arbiter record missing") from exc
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArbiterUnreadable("arbiter record is not valid JSON") from exc
    claimed = record.pop("content_sha256", None)
    if claimed != _digest(record):
        raise ArbiterUnreadable("arbiter digest mismatch")
    record["content_sha256"] = claimed
    return record


def acquire(root: os.PathLike[str] | str, record: dict) -> Outcome:
    """Compete for the arbiter name; never inspects the other party first."""
    base = Path(root)
    candidate = _write_candidate(base, record)
    try:
        rename_noreplace(candidate, base / ARBITER_NAME)
        return Outcome(True, record["decision"], record["run_id"], "won")
    except DestinationExists:
        try:
            holder = read_arbiter(base)
        except ArbiterUnreadable:
            _retire(base, candidate, record, "lost")
            return Outcome(False, None, None, "ARBITER_UNREADABLE")
        _retire(base, candidate, record, "lost")
        return Outcome(False, holder["decision"], holder["run_id"],
                       "held_by_other")


def _retire(base: Path, candidate: Path, record: dict, tag: str) -> None:
    try:
        rename_noreplace(candidate, base / f"{candidate.name}.{tag}")
    except (DestinationExists, FileNotFoundError):
        pass


def release(root: os.PathLike[str] | str, record: dict, tag: str) -> Path:
    """Archive the arbiter record; the name becomes free again."""
    base = Path(root)
    suffix = f"{ARBITER_NAME}.{tag}.{record['run_id']}"
    target = base / suffix
    rename_noreplace(base / ARBITER_NAME, target)
    return target
