# -*- coding: utf-8 -*-
"""Two-stage audit chain and failure-state reconciliation.

Stage one writes an immutable ``audit.json`` and a receipt holding its actual
byte digest.  Stage two's release receipt must quote that digest, so a receipt
can be tied to *the* audit it belongs to instead of merely sharing a run id.

Release failures are classified by what is actually on disk, not by how far the
code got: a lock that is still in place and a lock that has already been
archived are different facts and must not share one status.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

LOCK_NAME = "lifecycle.lock"
HEARTBEAT_PREFIX = "lifecycle.lock.hb."

LOCK_STILL_HELD = "LOCK_STILL_HELD"
LOCK_ARCHIVED_HEARTBEAT_PENDING = "LOCK_ARCHIVED_HEARTBEAT_PENDING"
LOCK_AND_HEARTBEAT_ARCHIVED_RECEIPT_PENDING = (
    "LOCK_AND_HEARTBEAT_ARCHIVED_RECEIPT_PENDING"
)


class AuditChainBroken(RuntimeError):
    """The quoted audit is missing, or its bytes are not the quoted bytes."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_stage_one(directory: os.PathLike[str] | str, payload: dict,
                    run_id: str) -> dict:
    base = Path(directory)
    base.mkdir(parents=True, exist_ok=True)
    audit_path = base / "audit.json"
    data = json.dumps(payload, sort_keys=True, indent=2,
                      ensure_ascii=False).encode("utf-8")
    with open(audit_path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    receipt = {
        "run_id": run_id,
        "audit_path": str(audit_path),
        "audit_bytes": len(data),
        "audit_sha256": _sha256_file(audit_path),
    }
    with open(base / "audit.receipt.json", "xb") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, indent=2,
                                ensure_ascii=False).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    return receipt


def verify_stage_one(receipt: dict) -> None:
    path = Path(receipt["audit_path"])
    if not path.exists():
        raise AuditChainBroken("audit.json is missing")
    if _sha256_file(path) != receipt["audit_sha256"]:
        raise AuditChainBroken("audit.json bytes changed after stage one")
    if path.stat().st_size != int(receipt["audit_bytes"]):
        raise AuditChainBroken("audit.json size changed after stage one")


def write_stage_two(directory: os.PathLike[str] | str, receipt: dict,
                    released_path: Path, heartbeat_path: Path,
                    removal_done: bool, lock_state: str) -> dict:
    verify_stage_one(receipt)
    body = {
        "run_id": receipt["run_id"],
        "audit_path": receipt["audit_path"],
        "audit_bytes": receipt["audit_bytes"],
        "audit_sha256": receipt["audit_sha256"],
        "released_path": str(released_path),
        "released_bytes": released_path.stat().st_size,
        "released_sha256": _sha256_file(released_path),
        "heartbeat_path": str(heartbeat_path),
        "heartbeat_bytes": heartbeat_path.stat().st_size,
        "heartbeat_sha256": _sha256_file(heartbeat_path),
        "heartbeat_semantics": "last_captured_at_archive",
        "removal_done": bool(removal_done),
        "lock_state": lock_state,
    }
    body["lock_content_sha256"] = body["released_sha256"]
    target = Path(directory) / "lock-release.json"
    with open(target, "xb") as handle:
        handle.write(json.dumps(body, sort_keys=True, indent=2,
                                ensure_ascii=False).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    return body


def reconcile_release_state(root: os.PathLike[str] | str,
                            run_id: str) -> str:
    """Derive the release state from disk, never from call progress."""
    base = Path(root)
    lock_present = (base / LOCK_NAME).exists()
    released = any(base.glob(f"{LOCK_NAME}.released.*.{run_id}"))
    heartbeat = (base / f"{HEARTBEAT_PREFIX}{run_id}").exists()
    heartbeat_archived = any(
        base.glob(f"{HEARTBEAT_PREFIX}released.*.{run_id}")
    )
    if lock_present:
        return LOCK_STILL_HELD
    if released and not heartbeat_archived:
        return LOCK_ARCHIVED_HEARTBEAT_PENDING
    if released and heartbeat_archived:
        return LOCK_AND_HEARTBEAT_ARCHIVED_RECEIPT_PENDING
    if not lock_present and not released:
        return LOCK_STILL_HELD if heartbeat else LOCK_LOST_STATE
    return LOCK_ARCHIVED_HEARTBEAT_PENDING


LOCK_LOST_STATE = "LOCK_LOST"
