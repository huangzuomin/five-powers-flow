# -*- coding: utf-8 -*-
"""Contract #40-#44: finalization lock, revocation, receipts, orphans.

Group tags in each docstring map back to the contract rows in M1-CONTRACT-44.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

try:  # the `validate` job's unittest discovery has no pytest; H2 runs via EVID-37
    import pytest
except ModuleNotFoundError:  # pragma: no cover
    import unittest

    raise unittest.SkipTest("pytest not installed; H2 contracts execute via QA EVID-37")

from _h2_support import add_worktree, git, init_repo, make_reclaimable

from packages.fpf_coordinator.worktree import (conditions, gitops, lock as lock_mod,
                                               policy, reclaim)
from packages.fpf_coordinator.worktree.noreplace import DestinationExists


def _lock(common, run_id="run-a", start="2026-01-01T00:00:00Z"):
    return lock_mod.acquire(common, run_id, pid=os.getpid(),
                            process_start_time=start)


def test_second_acquire_refused(tmp_path):
    """R07-D: one repository, one finalization lock."""
    common = tmp_path / "common"
    _lock(common, "run-a")
    with pytest.raises(lock_mod.LockError) as excinfo:
        _lock(common, "run-b")
    assert excinfo.value.reason == lock_mod.LOCK_HELD


def test_lock_unreadable_fails_closed(tmp_path):
    """R07-D: a lock that cannot be parsed is never treated as free."""
    common = tmp_path / "common"
    common.mkdir()
    (common / lock_mod.LOCK_NAME).write_text("{half", encoding="utf-8")
    with pytest.raises(lock_mod.LockError) as excinfo:
        _lock(common, "run-b")
    assert excinfo.value.reason == lock_mod.LOCK_UNREADABLE


def test_half_lock_fails_closed(tmp_path):
    """R07-E: truncated JSON is LOCK_UNREADABLE, not LOCK_HELD-LOST."""
    common = tmp_path / "common"
    common.mkdir()
    (common / lock_mod.LOCK_NAME).write_bytes(b'{"run_id": "run-a"')
    with pytest.raises(lock_mod.LockError) as excinfo:
        lock_mod.read_lock(common)
    assert excinfo.value.reason == lock_mod.LOCK_UNREADABLE


def test_reverify_detects_missing_lock(tmp_path):
    """R07-D: a vanished lock is LOCK_LOST."""
    common = tmp_path / "common"
    held = _lock(common)
    held.path.unlink()
    assert lock_mod.reverify(held) == lock_mod.LOCK_LOST


def test_reverify_detects_run_id_change(tmp_path):
    """R07-D: someone else owns the file now."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    payload = json.loads(held.path.read_text(encoding="utf-8"))
    payload["run_id"] = "run-b"
    held.path.write_text(json.dumps(payload), encoding="utf-8")
    assert lock_mod.reverify(held) == lock_mod.LOCK_OWNERSHIP_REVOKED


def test_reverify_detects_inode_replacement(tmp_path):
    """R07-D: same name, different object."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    payload = held.path.read_text(encoding="utf-8")
    held.path.unlink()
    held.path.write_text(payload, encoding="utf-8")
    assert lock_mod.reverify(held) == lock_mod.LOCK_OWNERSHIP_REVOKED


def test_reverify_detects_content_change_same_inode(tmp_path):
    """R07-E: inode equality is not enough; the bytes are immutable."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    payload = json.loads(held.path.read_text(encoding="utf-8"))
    payload["pid"] = 1
    with open(held.path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload))
    assert lock_mod.reverify(held) == lock_mod.LOCK_OWNERSHIP_REVOKED


def test_release_renames_not_deletes(tmp_path):
    """R07-D: release archives the lock; the bytes stay readable."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    original = held.path.read_bytes()
    receipt = lock_mod.release(held, audit={"audit_sha256": "a" * 64})
    released = Path(receipt["released_path"])
    assert released.is_file()
    assert released.read_bytes() == original
    assert not held.path.exists()


def test_release_receipt_matches_archived_bytes(tmp_path):
    """R07-D/R07-E: the receipt quotes the actual archived bytes."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    receipt = lock_mod.release(held, audit={"audit_sha256": "a" * 64})
    archived = Path(receipt["released_path"]).read_bytes()
    assert receipt["released_bytes"] == len(archived)
    assert receipt["released_sha256"] == hashlib.sha256(archived).hexdigest()
    assert receipt["lock_content_sha256"] == receipt["released_sha256"]


def test_second_release_same_run_collides(tmp_path, monkeypatch):
    """R07-D: the same run cannot archive its lock twice."""
    monkeypatch.setattr(lock_mod, "_stamp", lambda: "20260101T000000Z")
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    lock_mod.release(held, audit={})
    with pytest.raises(lock_mod.LockError) as excinfo:
        lock_mod.release(held, audit={})
    assert excinfo.value.reason in (
        lock_mod.LOCK_LOST, lock_mod.LOCK_RELEASE_NAME_COLLISION)


def test_release_refuses_after_revocation(tmp_path):
    """R07-D: a revoked owner must not archive someone else's lock."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    lock_mod.break_lock(
        common, expected_dev=held.dev, expected_ino=held.ino, by="ops",
        reason="test", liveness=lambda pid, start: "DEAD")
    with pytest.raises(lock_mod.LockError) as excinfo:
        lock_mod.release(held, audit={})
    assert excinfo.value.reason == lock_mod.LOCK_LOST


def test_consuming_marker_records_identity(tmp_path):
    """R07-D: the "removal in flight" marker names the exact lock object."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    marker = lock_mod.begin_consuming(held)
    body = json.loads(marker.read_text(encoding="utf-8"))
    assert body["run_id"] == "run-a"
    assert body["lock_dev"] == held.dev
    assert body["lock_ino"] == held.ino


def test_consuming_marker_is_exclusive(tmp_path):
    """R07-D: a second claim on the same run is an orphan claim, not a grant."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    lock_mod.begin_consuming(held)
    with pytest.raises(lock_mod.LockError) as excinfo:
        lock_mod.begin_consuming(held)
    assert excinfo.value.reason == lock_mod.ORPHAN_CLAIM


def test_release_does_not_delete_successor_lock(tmp_path):
    """v6: releasing run-a must not touch the lock run-b now owns."""
    common = tmp_path / "common"
    first = _lock(common, "run-a")
    lock_mod.break_lock(
        common, expected_dev=first.dev, expected_ino=first.ino, by="ops",
        reason="stale", liveness=lambda pid, start: "DEAD")
    second = _lock(common, "run-b")
    with pytest.raises(lock_mod.LockError):
        lock_mod.release(first, audit={})
    assert second.path.is_file()
    assert lock_mod.reverify(second) == lock_mod.LOCK_OK


def test_archive_names_are_unique(tmp_path):
    """v6: archiving never overwrites an existing record."""
    from packages.fpf_coordinator.worktree.noreplace import archive_unique
    base = tmp_path / "common"
    base.mkdir()
    (base / "a").write_text("one", encoding="utf-8")
    archive_unique(base, "a", "x")
    (base / "a").write_text("two", encoding="utf-8")
    with pytest.raises(DestinationExists):
        archive_unique(base, "a", "x")


def test_receipt_hash_bound_to_audit_bytes(tmp_path):
    """v6: the receipt is tied to one specific audit file."""
    from packages.fpf_coordinator.worktree import audit
    receipt = audit.write_stage_one(tmp_path, {"run_id": "run-a"}, "run-a")
    assert receipt["audit_sha256"] == hashlib.sha256(
        (tmp_path / "audit.json").read_bytes()).hexdigest()
    (tmp_path / "audit.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(audit.AuditChainBroken):
        audit.verify_stage_one(receipt)


def test_revoked_old_heartbeat_does_not_affect_new_lock(tmp_path):
    """v6: an old run's heartbeat can never resurrect its ownership."""
    common = tmp_path / "common"
    first = _lock(common, "run-a")
    lock_mod.break_lock(
        common, expected_dev=first.dev, expected_ino=first.ino, by="ops",
        reason="stale", liveness=lambda pid, start: "DEAD")
    second = _lock(common, "run-b")
    lock_mod.heartbeat(first, seq=99)
    assert lock_mod.reverify(second) == lock_mod.LOCK_OK
    assert lock_mod.read_lock(common)["run_id"] == "run-b"


def test_heartbeat_keeps_lock_inode(tmp_path):
    """v7: heartbeats live in their own file and never rewrite the lock."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    before = held.path.stat()
    lock_mod.heartbeat(held, seq=5)
    after = held.path.stat()
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
    assert lock_mod.reverify(held) == lock_mod.LOCK_OK


def test_concurrent_acquire_exactly_one_winner(tmp_path):
    """v7: the lock is decided by the filesystem, not by a read-then-write."""
    common = tmp_path / "common"
    common.mkdir()
    barrier = threading.Barrier(2)
    results = []
    guard = threading.Lock()

    def worker(run_id):
        barrier.wait()
        try:
            lock = lock_mod.acquire(common, run_id, pid=os.getpid(),
                                    process_start_time="t")
            outcome = lock_mod.LOCK_OK
        except lock_mod.LockError as exc:
            outcome = exc.reason
        with guard:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(f"run-{i}",)) for i in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [lock_mod.LOCK_HELD, lock_mod.LOCK_OK]


def test_release_and_break_do_not_overwrite_archives(tmp_path, monkeypatch):
    """v7: both archive paths use no-replace renames."""
    monkeypatch.setattr(lock_mod, "_stamp", lambda: "20260101T000000Z")
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    (common / f"{lock_mod.LOCK_NAME}.break.20260101T000000Z.run-a").write_text(
        "occupied", encoding="utf-8")
    with pytest.raises(lock_mod.LockError) as excinfo:
        lock_mod.break_lock(
            common, expected_dev=held.dev, expected_ino=held.ino, by="ops",
            reason="stale", liveness=lambda pid, start: "DEAD")
    assert excinfo.value.reason == lock_mod.LOCK_RELEASE_NAME_COLLISION


def test_break_lock_refuses_live_holder(tmp_path):
    """v8: a live holder is not "stale"; the heartbeat only asks the question."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    with pytest.raises(lock_mod.LockError) as excinfo:
        lock_mod.break_lock(
            common, expected_dev=held.dev, expected_ino=held.ino, by="ops",
            reason="looks stale", liveness=lambda pid, start: "ALIVE")
    assert excinfo.value.reason == lock_mod.BREAK_LOCK_HOLDER_ALIVE
    assert held.path.is_file()


def test_break_lock_allows_after_termination(tmp_path):
    """v8: proof of termination is the only thing that authorizes a break."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    proof = lock_mod.break_lock(
        common, expected_dev=held.dev, expected_ino=held.ino, by="ops",
        reason="process gone", liveness=lambda pid, start: "DEAD")
    assert proof["liveness"] == "DEAD"
    assert (common / proof["revoked_as"]).is_file()
    assert not held.path.exists()


def test_break_lock_detects_pid_reuse():
    """v8: a PID that exists with a different start time is a reused PID."""
    assert lock_mod.pid_liveness(4242, "start-a", probe=lambda pid: "start-b") == "DEAD"
    assert lock_mod.pid_liveness(4242, "start-a", probe=lambda pid: "start-a") == "ALIVE"
    assert lock_mod.pid_liveness(4242, "start-a", probe=lambda pid: None) == "DEAD"


def test_consuming_marker_blocks_break_lock(tmp_path):
    """v8: "removal in flight" must not be revocable by a break-lock."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    lock_mod.begin_consuming(held)
    with pytest.raises(lock_mod.LockError) as excinfo:
        lock_mod.break_lock(
            common, expected_dev=held.dev, expected_ino=held.ino, by="ops",
            reason="stale", liveness=lambda pid, start: "DEAD")
    assert excinfo.value.reason == lock_mod.BREAK_LOCK_REMOVE_IN_FLIGHT


def test_break_lock_identity_mismatch(tmp_path):
    """R07-E: breaking a lock that is not the one you inspected is refused."""
    common = tmp_path / "common"
    held = _lock(common, "run-a")
    with pytest.raises(lock_mod.LockError) as excinfo:
        lock_mod.break_lock(
            common, expected_dev=held.dev + 1, expected_ino=held.ino, by="ops",
            reason="stale", liveness=lambda pid, start: "DEAD")
    assert excinfo.value.reason == lock_mod.BREAK_LOCK_IDENTITY_MISMATCH


def test_orphan_heartbeat_detected(tmp_path):
    """v8: a heartbeat without a lock is an orphan, not an owner."""
    common = tmp_path / "common"
    common.mkdir()
    (common / f"{lock_mod.HEARTBEAT_PREFIX}run-ghost").write_text(
        json.dumps({"run_id": "run-ghost", "seq": 1,
                    "last": "2026-01-01T00:00:00Z"}), encoding="utf-8")
    assert lock_mod.orphan_heartbeats(common) == ["run-ghost"]


def _reclaimable(tmp_path, name="wt-lock", branch="fpf/lock"):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, name, branch)
    (path / ".fpf-runtime").mkdir()
    (path / ".fpf-runtime" / "note.txt").write_text("evidence\n", encoding="utf-8")
    make_reclaimable(repo, path, branch)
    pol = policy.load(repo)
    verdict = conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=pol, grace_days=0)
    return repo, path, pol, reclaim.build_plan([verdict], pol)


def test_lock_prevents_second_reclaimer(tmp_path):
    """R07-D: a second reclaimer stops before touching the target."""
    repo, path, pol, plan = _reclaimable(tmp_path)
    _lock(repo / ".git", "other-run")
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=pol, archive_root=tmp_path / "archive",
        run_id="mine", apply=True, confirm=plan["plan_digest"])
    assert outcome["results"][0]["reason_codes"] == [lock_mod.LOCK_HELD]
    assert path.exists()


def test_step_11_revocation_never_deletes(tmp_path):
    """v8: revocation inside the removal window stops the delete."""
    repo, path, pol, plan = _reclaimable(tmp_path)

    def revoke():
        (repo / ".git" / lock_mod.LOCK_NAME).unlink()

    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=pol, archive_root=tmp_path / "archive",
        run_id="run-revoke", apply=True, confirm=plan["plan_digest"],
        hooks={"before_remove": revoke})
    result = outcome["results"][0]
    assert result["decision"] == reclaim.HELD
    assert result["reason_codes"] == [lock_mod.LOCK_OWNERSHIP_REVOKED]
    assert path.exists()


def test_final_c1_interception(tmp_path):
    """R07-E: a change after the final revalidation is still caught."""
    repo, path, pol, plan = _reclaimable(tmp_path)

    def dirty():
        (path / "late.txt").write_text("appeared\n", encoding="utf-8")

    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=pol, archive_root=tmp_path / "archive",
        run_id="run-c1", apply=True, confirm=plan["plan_digest"],
        hooks={"before_final_c1": dirty})
    assert outcome["results"][0]["reason_codes"] == [reclaim.FINAL_C1_DIRTY]
    assert path.exists()


def test_audit_receipt_binds_audit_bytes(tmp_path):
    """v8: the receipt is verifiable against the audit it names."""
    repo, path, pol, plan = _reclaimable(tmp_path)
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=pol, archive_root=tmp_path / "archive",
        run_id="run-audit", apply=True, confirm=plan["plan_digest"])
    assert outcome["results"][0]["decision"] == reclaim.RECLAIMED
    base = tmp_path / "archive" / "worktree-lifecycle" / "run-audit"
    receipt = json.loads((base / "audit.receipt.json").read_text(encoding="utf-8"))
    audit_bytes = (base / "audit.json").read_bytes()
    assert receipt["audit_bytes"] == len(audit_bytes)
    assert receipt["audit_sha256"] == hashlib.sha256(audit_bytes).hexdigest()
    release = json.loads(
        (repo / ".git" / lock_mod.RECEIPT_NAME).read_text(encoding="utf-8"))
    assert release["audit_sha256"] == receipt["audit_sha256"]
    assert release["released_sha256"] == hashlib.sha256(
        Path(release["released_path"]).read_bytes()).hexdigest()


def test_final_revalidation_refreshes_origin_main(tmp_path, monkeypatch):
    """v7: every evaluation refreshes main explicitly, never trusts a cache."""
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-fetch", "fpf/fetch")
    from _h2_support import write_marker
    write_marker(path, branch="refs/heads/fpf/fetch")
    seen = []
    real = gitops.fetch

    def spy(repo_path, refspec):
        seen.append(refspec)
        return real(repo_path, refspec)

    monkeypatch.setattr(gitops, "fetch", spy)
    conditions.evaluate(path, repo=repo, root=repo / "_worktrees",
                        main_worktree=repo, policy=policy.load(repo),
                        grace_days=0)
    assert "+refs/heads/main:refs/remotes/origin/main" in seen
    assert "+refs/heads/fpf/fetch:refs/remotes/origin/fpf/fetch" in seen


def test_stale_origin_main_never_proves_merged(tmp_path):
    """v6: a stale tracking ref cannot turn "not merged" into "merged"."""
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-stale", "fpf/stale")
    (path / "feature.txt").write_text("work\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "unmerged feature")
    git(repo, "push", "origin", "fpf/stale")
    head = git(path, "rev-parse", "HEAD").strip()
    git(repo, "update-ref", "refs/remotes/origin/main", head)
    from _h2_support import write_marker
    write_marker(path, branch="refs/heads/fpf/stale")
    verdict = conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=policy.load(repo), grace_days=0)
    assert conditions.NOT_MERGED in verdict.reason_codes
