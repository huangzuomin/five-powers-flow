# -*- coding: utf-8 -*-
"""Reclamation: plan, verify, archive, remove, audit.

A plan only selects *candidates*.  Every deletion re-derives the facts on the
spot, archives before it deletes, and writes an audit that can restore what
was removed.  Nothing in here deletes a worktree because a plan said so.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import conditions, gitops, lock as lock_mod, marker as marker_mod, policy as policy_mod

TOOL_VERSION = "fpf-worktree/v1"

RECLAIMED = "RECLAIMED"
HELD = "HELD"
DRY_RUN = "DRY_RUN"

PLAN_STALE = "PLAN_STALE"
STASH_UNACKNOWLEDGED = "STASH_UNACKNOWLEDGED"
ARCHIVE_FAILED = "ARCHIVE_FAILED"
ARCHIVE_VERIFY_FAILED = "ARCHIVE_VERIFY_FAILED"
CLEANUP_INCOMPLETE = "CLEANUP_INCOMPLETE"
FINAL_C1_DIRTY = "FINAL_C1_DIRTY"
FINAL_REVALIDATION_FAILED = "FINAL_REVALIDATION_FAILED"
TARGET_IDENTITY_CHANGED = "TARGET_IDENTITY_CHANGED"
REMOVE_REFUSED = "REMOVE_REFUSED"
BRANCH_IN_USE = "BRANCH_IN_USE"
BRANCH_DELETE_REFUSED = "BRANCH_DELETE_REFUSED"
DETACHED_NO_BRANCH = "DETACHED_NO_BRANCH"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_digest(names, *, policy_sha: str, tool_version: str = TOOL_VERSION) -> str:
    body = {
        "candidates": sorted(names),
        "policy_sha256": policy_sha,
        "tool_version": tool_version,
    }
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_plan(verdicts, policy) -> dict:
    candidates = [v for v in verdicts if v.decision == conditions.RECLAIMABLE]
    names = [v.name for v in candidates]
    return {
        "plan_version": "fpf.worktree-plan/v1",
        "generated_at": _now(),
        "tool_version": TOOL_VERSION,
        "policy_sha256": policy.sha256(),
        "policy_source": policy.source,
        "candidates": [v.to_dict() for v in candidates],
        "held": [v.to_dict() for v in verdicts if v.decision != conditions.RECLAIMABLE],
        "plan_digest": plan_digest(names, policy_sha=policy.sha256()),
    }


def repo_stash(repo) -> dict:
    result = gitops.run(["git", "-C", str(repo), "stash", "list", "--format=%H"])
    entries = [line for line in result.output.splitlines() if line.strip()]
    return {"present": bool(entries), "entries": len(entries),
            "sha": entries[0] if entries else None}


def archive(root, name: str, worktree, manifest, marker_path) -> dict:
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{name}-{_stamp()}.tar.gz"
    with tarfile.open(target, "w:gz") as bundle:
        if marker_path and Path(marker_path).exists():
            bundle.add(marker_path, arcname=marker_mod.MARKER_NAME)
        for item in manifest:
            full = Path(worktree) / item["relpath"]
            if full.exists():
                bundle.add(full, arcname=item["relpath"])
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": _sha256_file(target),
        "files": len(manifest) + (1 if marker_path else 0),
        "manifest": manifest,
    }


def verify_archive(archive_path, expected_manifest) -> tuple[bool, list[str]]:
    problems: list[str] = []
    expected = {item["relpath"]: item for item in expected_manifest
                if item["relpath"] != marker_mod.MARKER_NAME}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with tarfile.open(archive_path, "r:gz") as bundle:
                bundle.extractall(tmp)
        except (tarfile.TarError, OSError) as exc:
            return False, [f"ARCHIVE_UNREADABLE: {exc}"]
        seen = set()
        for root, _dirs, files in os.walk(tmp):
            for name in files:
                full = Path(root) / name
                rel = full.relative_to(tmp).as_posix()
                if rel == marker_mod.MARKER_NAME:
                    continue
                seen.add(rel)
                if rel not in expected:
                    problems.append(f"UNEXPECTED: {rel}")
                    continue
                if full.stat().st_size != expected[rel]["bytes"]:
                    problems.append(f"SIZE: {rel}")
                elif _sha256_file(full) != expected[rel]["sha256"]:
                    problems.append(f"DIGEST: {rel}")
    for rel in sorted(set(expected) - seen):
        problems.append(f"MISSING: {rel}")
    return (not problems), problems


def cleanup(worktree, manifest, marker_path) -> list[str]:
    """Delete exactly what was archived, nothing discovered on the fly."""
    removed = []
    for item in manifest:
        if item["relpath"] == marker_mod.MARKER_NAME:
            continue
        full = Path(worktree) / item["relpath"]
        if full.is_file():
            full.unlink()
            removed.append(item["relpath"])
    for top in {item["relpath"].split("/")[0] for item in manifest
                if "/" in item["relpath"]}:
        directory = Path(worktree) / top
        if directory.is_dir():
            shutil.rmtree(directory, ignore_errors=True)
            removed.append(top)
    if marker_path and Path(marker_path).exists():
        Path(marker_path).unlink()
        removed.append(marker_mod.MARKER_NAME)
    return removed


def _leftovers(worktree, policy) -> list[str]:
    result = gitops.status(worktree)
    out = []
    for line in result.output.splitlines():
        if not line.strip():
            continue
        code, name = line[:2], line[3:].strip().strip('"')
        if code in ("??", "!!") and policy_mod.allowed(name, policy):
            continue
        out.append(line)
    return out


def _branch_in_use(repo, branch: str, exclude: Path) -> bool:
    for block in gitops.worktree_blocks(repo):
        if os.path.normcase(os.path.realpath(block["worktree"])) == \
                os.path.normcase(os.path.realpath(exclude)):
            continue
        if block.get("branch") == branch:
            return True
    return False


@dataclass
class ReclaimResult:
    name: str
    decision: str
    reason_codes: list[str] = field(default_factory=list)
    archive: dict | None = None
    entry: dict = field(default_factory=dict)
    removed: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "archive": self.archive,
            "removed": self.removed,
            "entry": self.entry,
        }


def reclaim_one(verdict, *, repo, policy, archive_root, run_id: str,
                apply: bool, ack_stash: bool = False, api=None,
                hooks: dict | None = None, now: datetime | None = None,
                grace_days: int | None = None) -> ReclaimResult:
    hooks = hooks or {}
    target = Path(verdict.path)
    result = ReclaimResult(verdict.name, HELD)

    def hold(*codes) -> ReclaimResult:
        result.reason_codes = list(dict.fromkeys(codes))
        result.decision = HELD
        return result

    stash = repo_stash(repo)
    if stash["present"] and not ack_stash:
        return hold(STASH_UNACKNOWLEDGED)

    live = conditions.evaluate(
        target, repo=repo, root=Path(repo) / policy.worktree_root,
        main_worktree=repo, policy=policy, api=api, now=now,
        grace_days=grace_days)
    if not live.ok:
        return hold(*(live.reason_codes or ["NOT_RECLAIMABLE"]))
    head_at_plan = live.head_sha

    result.entry = {
        "name": verdict.name,
        "path": str(target),
        "branch": live.branch,
        "head_sha": live.head_sha,
        "task_id": None,
        "decision": DRY_RUN if not apply else RECLAIMED,
        "reason_codes": [],
        "conditions": live.conditions,
        "ignored_manifest": live.ignored_manifest,
        "stash": stash,
    }
    try:
        marker = marker_mod.read(target)
        result.entry["task_id"] = marker["task_id"]
    except (FileNotFoundError, marker_mod.MarkerError):
        marker = None

    if not apply:
        result.decision = DRY_RUN
        return result

    root_dir = Path(repo) / policy.worktree_root
    root_before = _dir_bytes(root_dir)
    marker_path = target / marker_mod.MARKER_NAME
    try:
        archived = archive(archive_root, verdict.name, target,
                           live.ignored_manifest, marker_path)
    except (OSError, tarfile.TarError) as exc:
        result.entry["archive_error"] = str(exc)
        return hold(ARCHIVE_FAILED)
    result.archive = {
        "path": archived["path"], "bytes": archived["bytes"],
        "sha256": archived["sha256"], "files": archived["files"],
    }
    ok, problems = verify_archive(archived["path"], live.ignored_manifest)
    result.entry["archive"] = dict(result.archive, verify="PASS" if ok else "FAIL",
                                   verified_files=len(live.ignored_manifest))
    if not ok:
        result.entry["archive_problems"] = problems
        return hold(ARCHIVE_VERIFY_FAILED)

    hook = hooks.get("after_archive")
    if hook:
        hook()

    # The marker stays in place until the worktree is actually removed: the
    # post-archive re-evaluation still has to be able to read it.
    cleanup(target, live.ignored_manifest, None)
    if _leftovers(target, policy):
        return hold(CLEANUP_INCOMPLETE)
    post = conditions.evaluate(
        target, repo=repo, root=Path(repo) / policy.worktree_root,
        main_worktree=repo, policy=policy, api=api, now=now,
        grace_days=grace_days)
    if not post.ok and post.reason_codes not in (
            [conditions.NOT_PROMOTED], [conditions.IN_GRACE]):
        return hold(*(post.reason_codes or [FINAL_C1_DIRTY]))

    hook = hooks.get("before_final")
    if hook:
        hook()

    lock = None
    try:
        lock = lock_mod.acquire(
            Path(repo) / ".git", f"{run_id}-{verdict.name}",
            pid=os.getpid(), process_start_time=_now())
    except lock_mod.LockError as exc:
        return hold(exc.reason)

    try:
        final = conditions.evaluate(
            target, repo=repo, root=Path(repo) / policy.worktree_root,
            main_worktree=repo, policy=policy, api=api, now=now,
            grace_days=grace_days)
        if final.head_sha != head_at_plan:
            return hold(TARGET_IDENTITY_CHANGED)
        if not final.ok and final.reason_codes not in (
                [conditions.NOT_PROMOTED], [conditions.IN_GRACE]):
            return hold(FINAL_REVALIDATION_FAILED, *final.reason_codes)
        hook = hooks.get("before_final_c1")
        if hook:
            hook()
        if _leftovers(target, policy):
            return hold(FINAL_C1_DIRTY)
        if lock_mod.reverify(lock) != lock_mod.LOCK_OK:
            return hold(lock_mod.LOCK_OWNERSHIP_REVOKED)
        if (lock.path.stat().st_dev, lock.path.stat().st_ino) != (lock.dev, lock.ino):
            return hold(TARGET_IDENTITY_CHANGED)
        try:
            lock_mod.begin_consuming(lock)
        except lock_mod.LockError as exc:
            return hold(exc.reason)

        hook = hooks.get("before_remove")
        if hook:
            hook()
        if lock_mod.reverify(lock) != lock_mod.LOCK_OK:
            return hold(lock_mod.LOCK_OWNERSHIP_REVOKED)

        removal = gitops.remove_worktree(repo, target)
        result.entry["git_ops"] = {"worktree_remove_exit": removal.exit}
        if removal.exit != 0:
            return hold(REMOVE_REFUSED)
        result.removed = True

        result.reason_codes = _dispose_branch(repo, live.branch, result.entry)
        prune = gitops.prune_path(repo, target)
        result.entry["git_ops"]["prune_exit"] = prune.exit
        root_after = _dir_bytes(root_dir)
        result.entry["disk"] = {
            "root_bytes_before": root_before,
            "root_bytes_after": root_after,
            "freed_bytes": max(root_before - root_after, 0),
        }

        stage_one = _write_audit(archive_root, run_id, result.entry)
        result.entry["receipt"] = stage_one
        try:
            lock_mod.release(lock, audit=stage_one)
        except lock_mod.LockError as exc:
            result.entry["lock_release_error"] = exc.reason
        result.decision = RECLAIMED
        return result
    finally:
        if lock is not None and result.decision != RECLAIMED:
            try:
                lock_mod.release(lock, audit={})
            except lock_mod.LockError:
                pass


def _dispose_branch(repo, branch: str | None, entry: dict) -> list[str]:
    codes: list[str] = []
    ops: dict = entry.setdefault("git_ops", {})
    if not branch:
        ops["branch_decision"] = DETACHED_NO_BRANCH
        return [DETACHED_NO_BRANCH]
    if _branch_in_use(repo, branch, Path(entry["path"])):
        ops["branch_decision"] = BRANCH_IN_USE
        return [BRANCH_IN_USE]
    result = gitops.delete_branch(repo, branch.replace("refs/heads/", ""))
    ops["branch_decision"] = "DELETE"
    ops["branch_delete_exit"] = result.exit
    if result.exit != 0:
        codes.append(BRANCH_DELETE_REFUSED)
    return codes


def _write_audit(archive_root, run_id: str, entry: dict) -> dict:
    base = Path(archive_root) / "worktree-lifecycle" / run_id
    base.mkdir(parents=True, exist_ok=True)
    audit_path = base / "audit.json"
    document = {
        "audit_version": "fpf.worktree-audit/v1",
        "run_id": run_id,
        "operator": {
            "login": os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
            "host": os.environ.get("COMPUTERNAME") or "unknown",
            "tool_version": TOOL_VERSION,
        },
        "entries": [entry],
        "disk": entry.get("disk", {}),
    }
    data = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False).encode()
    with open(audit_path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    receipt = {
        "run_id": run_id,
        "audit_path": str(audit_path),
        "audit_bytes": len(data),
        "audit_sha256": hashlib.sha256(data).hexdigest(),
    }
    (base / "audit.receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2), encoding="utf-8")
    (base / "audit.md").write_text(
        "# worktree reclaim audit " + run_id + "\n\n"
        "- entry: " + str(entry.get("name")) + "\n"
        "- head: " + str(entry.get("head_sha")) + "\n"
        "- archive sha256: " + str((entry.get("archive") or {}).get("sha256")) + "\n"
        "- removed: yes\n",
        encoding="utf-8")
    return receipt


def _verdict_from_plan(item: dict, decision: str) -> conditions.Verdict:
    return conditions.Verdict(
        name=item["name"], path=item["path"], decision=decision,
        reason_codes=list(item.get("reason_codes") or []),
        head_sha=item.get("head_sha"), branch=item.get("branch"),
        marker_state=item.get("marker_state"),
        ignored_manifest=list(item.get("ignored_manifest") or []),
    )


def reclaim_batch(plan, *, repo, policy, archive_root, run_id, apply,
                  confirm: str | None = None, only: str | None = None,
                  ack_stash: bool = False, api=None, hooks: dict | None = None,
                  now=None, grace_days=None) -> dict:
    if apply and plan.get("plan_digest") != confirm:
        return {"decision": "REFUSED", "reason": PLAN_STALE, "results": []}
    root = Path(repo) / policy.worktree_root
    results: list[ReclaimResult] = []
    before = _dir_bytes(root)
    stopped = False
    for item in plan.get("candidates") or []:
        if only and item["name"] != only:
            continue
        verdict = _verdict_from_plan(item, conditions.RECLAIMABLE)
        outcome = reclaim_one(
            verdict, repo=repo, policy=policy, archive_root=archive_root,
            run_id=run_id, apply=apply, ack_stash=ack_stash, api=api,
            hooks=hooks, now=now, grace_days=grace_days)
        results.append(outcome)
        if apply and outcome.decision != RECLAIMED:
            stopped = True
            break
    after = _dir_bytes(root)
    return {
        "decision": "STOPPED" if stopped else "DONE",
        "reason": "BATCH_STOPPED_ON_FAILURE" if stopped else None,
        "results": [item.to_dict() for item in results],
        "disk": {
            "root_bytes_before": before,
            "root_bytes_after": after,
            "freed_bytes": max(before - after, 0),
        },
    }


def _dir_bytes(path) -> int:
    return conditions.dir_bytes(path) if Path(path).exists() else 0


def scan(repo, *, policy=None, api=None, now=None, grace_days=None,
         root=None) -> list:
    policy = policy or policy_mod.load(repo)
    base = Path(root) if root else Path(repo) / policy.worktree_root
    verdicts = []
    if not base.exists():
        return verdicts
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        verdicts.append(conditions.evaluate(
            child, repo=repo, root=base, main_worktree=repo, policy=policy,
            api=api, now=now, grace_days=grace_days))
    return verdicts
