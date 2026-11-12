# -*- coding: utf-8 -*-
"""H2 lifecycle protocol: arbitration, identity revalidation, audit chain.
These are the executable forms of the contract accepted at R11.  Each test
asserts an externally observable fact (who won, whether a removal was issued,
which bytes changed), not an internal call order.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
from pathlib import Path

try:  # the `validate` job's unittest discovery has no pytest; H2 runs via EVID-37
    import pytest
except ModuleNotFoundError:  # pragma: no cover
    import unittest

    raise unittest.SkipTest("pytest not installed; H2 contracts execute via QA EVID-37")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.fpf_coordinator.worktree import arbiter, audit, identity  # noqa: E402
from packages.fpf_coordinator.worktree.noreplace import (  # noqa: E402
    DestinationExists,
    rename_noreplace,
)


def _record(decision: str, run_id: str, ino: int = 4242) -> dict:
    return arbiter.build_record(decision, run_id, 1, ino, 999,
                                "2026-01-01T00:00:00Z")


def _write_lock(root, run_id: str):
    body = {"lock_version": "fpf.lifecycle-lock/v2", "run_id": run_id}
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body["content_sha256"] = hashlib.sha256(payload).hexdigest()
    (root / identity.LOCK_NAME).write_text(json.dumps(body), encoding="utf-8")
    return identity.read_lock(root)[1]


def test_rename_noreplace_never_overwrites(tmp_path):
    src, dst = tmp_path / "a", tmp_path / "b"
    src.write_bytes(b"new")
    dst.write_bytes(b"old")
    with pytest.raises(DestinationExists):
        rename_noreplace(src, dst)
    assert dst.read_bytes() == b"old"
    assert src.read_bytes() == b"new"


def test_arbiter_claim_and_revoke_scenario_a_arbiter_held(tmp_path):
    assert arbiter.acquire(tmp_path, _record(arbiter.REVOKE, "run-b")).won
    outcome = arbiter.acquire(tmp_path, _record(arbiter.CLAIM, "run-a"))
    assert outcome.won is False
    assert outcome.decision_seen == arbiter.REVOKE
    assert outcome.reason == "held_by_other"


def test_arbiter_claim_late_after_arbiter_released(tmp_path):
    expected = _write_lock(tmp_path, "run-a")
    revoke = _record(arbiter.REVOKE, "run-a")
    assert arbiter.acquire(tmp_path, revoke).won
    rename_noreplace(tmp_path / identity.LOCK_NAME,
                     tmp_path / "lifecycle.lock.revoked.20260101T000000Z.run-a")
    arbiter.release(tmp_path, revoke, "revoked")

    outcome = arbiter.acquire(tmp_path, _record(arbiter.CLAIM, "run-a"))
    assert outcome.won is True
    assert identity.verify(tmp_path, expected) == identity.LOCK_LOST
    removals = []
    if identity.verify(tmp_path, expected) == identity.AUTHORIZED:
        removals.append("removed")
    assert removals == []


def test_arbiter_claim_late_after_new_lock_exists(tmp_path):
    expected = _write_lock(tmp_path, "run-a")
    (tmp_path / identity.LOCK_NAME).unlink()
    _write_lock(tmp_path, "run-new")
    assert arbiter.acquire(tmp_path, _record(arbiter.CLAIM, "run-a")).won is True
    assert identity.verify(tmp_path, expected) == identity.LOCK_LOST


def test_arbiter_concurrent_acquire_exactly_one_winner(tmp_path):
    barrier = threading.Barrier(2)
    results: list[bool] = []
    guard = threading.Lock()

    def worker(decision: str, run_id: str):
        record = _record(decision, run_id)
        barrier.wait()
        outcome = arbiter.acquire(tmp_path, record)
        with guard:
            results.append(outcome.won)

    threads = [
        threading.Thread(target=worker, args=(arbiter.CLAIM, "run-a")),
        threading.Thread(target=worker, args=(arbiter.REVOKE, "run-b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [False, True]


def test_arbiter_candidate_is_complete_when_visible(tmp_path):
    assert arbiter.acquire(tmp_path, _record(arbiter.CLAIM, "run-a")).won
    holder = arbiter.read_arbiter(tmp_path)
    assert holder["run_id"] == "run-a"
    assert holder["decision"] == arbiter.CLAIM
    assert holder["content_sha256"]


def test_arbiter_unreadable_record_fails_closed(tmp_path):
    (tmp_path / arbiter.ARBITER_NAME).write_bytes(b"{not json")
    outcome = arbiter.acquire(tmp_path, _record(arbiter.CLAIM, "run-a"))
    assert outcome.won is False
    assert outcome.reason == "ARBITER_UNREADABLE"


def test_audit_chain_binds_exact_stage_one_file(tmp_path):
    receipt = audit.write_stage_one(tmp_path, {"run_id": "run-a"}, "run-a")
    released = tmp_path / "lock.released"
    heartbeat = tmp_path / "hb.released"
    released.write_bytes(b"lock-bytes")
    heartbeat.write_bytes(b"hb-bytes")
    body = audit.write_stage_two(
        tmp_path, receipt, released, heartbeat, removal_done=True,
        lock_state=audit.LOCK_AND_HEARTBEAT_ARCHIVED_RECEIPT_PENDING)
    assert body["audit_sha256"] == receipt["audit_sha256"]
    assert body["lock_content_sha256"] == body["released_sha256"]
    assert body["heartbeat_sha256"] != body["released_sha256"]
    assert body["removal_done"] is True


def test_audit_chain_detects_mutated_stage_one(tmp_path):
    receipt = audit.write_stage_one(tmp_path, {"run_id": "run-a"}, "run-a")
    path = tmp_path / "audit.json"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(audit.AuditChainBroken):
        audit.verify_stage_one(receipt)


def test_release_state_is_derived_from_disk(tmp_path):
    (tmp_path / identity.LOCK_NAME).write_text("{}", encoding="utf-8")
    assert audit.reconcile_release_state(tmp_path, "run-a") == audit.LOCK_STILL_HELD
    (tmp_path / identity.LOCK_NAME).rename(
        tmp_path / "lifecycle.lock.released.20260101T000000Z.run-a")
    (tmp_path / "lifecycle.lock.hb.run-a").write_text("{}", encoding="utf-8")
    assert (audit.reconcile_release_state(tmp_path, "run-a")
            == audit.LOCK_ARCHIVED_HEARTBEAT_PENDING)
    (tmp_path / "lifecycle.lock.hb.run-a").rename(
        tmp_path / "lifecycle.lock.hb.released.20260101T000000Z.run-a")
    assert (audit.reconcile_release_state(tmp_path, "run-a")
            == audit.LOCK_AND_HEARTBEAT_ARCHIVED_RECEIPT_PENDING)
