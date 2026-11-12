# -*- coding: utf-8 -*-
"""Scope (C0) and the three reclamation conditions (C3, C1, C2).

Order matters and is frozen: C0 -> C3 -> C1 -> C2.  C3 is cheapest and rules
out the majority; running it first keeps a dirty, unmerged worktree from being
reported as "only dirty".  Every failing condition is still evaluated so one
pass shows all blockers instead of one at a time.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import gitops, marker as marker_mod, policy as policy_mod

RECLAIMABLE = "RECLAIMABLE"
HOLD = "HOLD"
POLICY_VIOLATION = "POLICY_VIOLATION"
SKIPPED = "SKIPPED"

MAIN_WORKTREE = "MAIN_WORKTREE"
OUTSIDE_ROOT = "OUTSIDE_ROOT"
REPARSE_POINT = "REPARSE_POINT"
MISSING_MARKER = "MISSING_MARKER"
MARKER_TAMPERED = "MARKER_TAMPERED"
MARKER_INVALID = "MARKER_INVALID"
LOCKED = "LOCKED"
ORPHANED_DIRECTORY = "ORPHANED_DIRECTORY"

FETCH_FAILED = "FETCH_FAILED"
ORIGIN_MAIN_STALE = "ORIGIN_MAIN_STALE"
NOT_MERGED = "NOT_MERGED"
MERGE_FACT_UNVERIFIABLE = "MERGE_FACT_UNVERIFIABLE"
DIRTY_TRACKED = "DIRTY_TRACKED"
DIRTY_UNTRACKED = "DIRTY_UNTRACKED"
IGNORED_UNARCHIVED = "IGNORED_UNARCHIVED"
UNMERGED_ENTRIES = "UNMERGED_ENTRIES"
SUBMODULE_DIRTY = "SUBMODULE_DIRTY"
REMOTE_REF_REFRESH_FAILED = "REMOTE_REF_REFRESH_FAILED"
UNPROVABLE_NO_REMOTE_REF = "UNPROVABLE_NO_REMOTE_REF"
UNPUSHED = "UNPUSHED"
TTL_EXPIRED = "TTL_EXPIRED"
NOT_PROMOTED = "NOT_PROMOTED"
IN_GRACE = "IN_GRACE"
GRACE_UNKNOWN = "GRACE_UNKNOWN"

CONFLICT_CODES = frozenset({
    "DD", "AU", "UD", "UA", "DU", "AA", "UU",
})


@dataclass
class Verdict:
    name: str
    path: str
    decision: str
    reason_codes: list[str] = field(default_factory=list)
    conditions: dict = field(default_factory=dict)
    ignored_manifest: list = field(default_factory=list)
    head_sha: str | None = None
    branch: str | None = None
    marker_state: str | None = None
    ttl_expired: bool = False
    bytes: int = 0

    @property
    def ok(self) -> bool:
        return self.decision == RECLAIMABLE

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "conditions": self.conditions,
            "ignored_manifest": list(self.ignored_manifest),
            "head_sha": self.head_sha,
            "branch": self.branch,
            "marker_state": self.marker_state,
            "ttl_expired": self.ttl_expired,
            "bytes": self.bytes,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(path: Path, rel: str | None = None) -> list[dict]:
    base = Path(path)
    items = []
    for root, _dirs, files in os.walk(base):
        for name in sorted(files):
            full = Path(root) / name
            relpath = full.relative_to(base).as_posix()
            items.append({
                "relpath": (rel + relpath) if rel else relpath,
                "bytes": full.stat().st_size,
                "sha256": _sha256_file(full),
            })
    items.sort(key=lambda item: item["relpath"])
    return items


def dir_bytes(path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _under(root: str, path: str) -> bool:
    root_n = os.path.normcase(os.path.realpath(root)).rstrip(os.sep)
    path_n = os.path.normcase(os.path.realpath(path))
    return path_n == root_n or path_n.startswith(root_n + os.sep)


def _is_reparse(path) -> bool:
    p = Path(path)
    if p.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(p))


def _blocked_blocks(repo) -> dict:
    out = {}
    for block in gitops.worktree_blocks(repo):
        out[os.path.normcase(os.path.realpath(block["worktree"]))] = block
    return out


def _check_c1(path, policy) -> tuple[list[str], dict, list[dict]]:
    reasons: list[str] = []
    manifest: list[dict] = []
    result = gitops.status(path)
    detail = {"status": result.as_evidence()}
    if result.exit != 0:
        return ["STATUS_FAILED"], detail, manifest
    untracked, ignored = [], []
    for line in result.output.splitlines():
        if not line.strip():
            continue
        code, _, name = line[:2], line[2:3], line[3:]
        name = name.strip().strip('"')
        if code == "??":
            untracked.append(name)
        elif code == "!!":
            ignored.append(name)
        elif code in CONFLICT_CODES:
            reasons.append(UNMERGED_ENTRIES)
        else:
            reasons.append(DIRTY_TRACKED)

    for name in untracked:
        if not policy_mod.allowed(name, policy):
            reasons.append(DIRTY_UNTRACKED)
    for name in ignored:
        if not policy_mod.allowed(name, policy):
            reasons.append(IGNORED_UNARCHIVED)
            continue
        full = Path(path) / name.rstrip("/")
        if full.is_dir():
            manifest.extend(_manifest(full, rel=name if name.endswith("/") else name + "/"))
        elif full.exists():
            manifest.append({
                "relpath": name,
                "bytes": full.stat().st_size,
                "sha256": _sha256_file(full),
            })

    for op in gitops.in_progress(path):
        reasons.append(f"IN_PROGRESS_{op}")
    if gitops.dirty_submodules(path):
        reasons.append(SUBMODULE_DIRTY)

    detail["untracked"] = untracked
    detail["ignored"] = ignored
    detail["ignored_manifest_count"] = len(manifest)
    detail["ignored_manifest_bytes"] = sum(item["bytes"] for item in manifest)
    return sorted(set(reasons)), detail, manifest


def _check_c3(repo, head: str | None, marker: dict, api) -> tuple[list[str], dict, bool]:
    reasons: list[str] = []
    evidence = {}
    if not head:
        return ["HEAD_UNREADABLE"], evidence, False
    refresh = gitops.fetch(repo, "+refs/heads/main:refs/remotes/origin/main")
    evidence["origin_main_refresh"] = refresh
    if not refresh["proven"]:
        reasons.append(FETCH_FAILED if refresh["exit"] != 0 else ORIGIN_MAIN_STALE)
        return reasons, evidence, False
    ancestor = gitops.is_ancestor(repo, head, "refs/remotes/origin/main")
    evidence["ancestry"] = ancestor
    evidence["basis"] = "ancestry"
    if ancestor is True:
        return reasons, evidence, True
    if ancestor is None:
        return [FETCH_FAILED], evidence, False

    fact = marker.get("merge_fact") if isinstance(marker, dict) else None
    if not fact or api is None:
        return [NOT_MERGED], evidence, False
    try:
        response = api(fact.get("pr_number"))
    except Exception as exc:  # noqa: BLE001 - any API failure is unverifiable
        evidence["api_error"] = str(exc)
        return [MERGE_FACT_UNVERIFIABLE], evidence, False
    if not isinstance(response, dict):
        return [MERGE_FACT_UNVERIFIABLE], evidence, False
    evidence["api"] = {
        "state": response.get("state"),
        "head_sha": ((response.get("head") or {}).get("sha")),
        "merge_commit_sha": response.get("merge_commit_sha"),
        "response_sha256": hashlib.sha256(
            repr(sorted(response.items())).encode("utf-8", "replace")).hexdigest(),
    }
    if response.get("state") != "merged":
        return [NOT_MERGED], evidence, False
    if ((response.get("head") or {}).get("sha")) != head:
        return [MERGE_FACT_UNVERIFIABLE], evidence, False
    merge_commit = response.get("merge_commit_sha")
    if not merge_commit or gitops.is_ancestor(
            repo, merge_commit, "refs/remotes/origin/main") is not True:
        return [MERGE_FACT_UNVERIFIABLE], evidence, False
    evidence["basis"] = "api_merge_fact"
    return reasons, evidence, True


def _check_c2(repo, branch_ref: str | None, merged: bool,
              head: str | None) -> tuple[list[str], dict, bool]:
    evidence = {}
    if not branch_ref:
        # Detached HEAD: ancestry alone proves there is nothing unpushed.  It is
        # never "unprovable": there is no branch to have a remote counterpart.
        evidence["basis"] = "ancestry"
        return ([] if merged else []), evidence, merged
    short = branch_ref.replace("refs/heads/", "")
    refresh = gitops.fetch(repo, f"+refs/heads/{short}:refs/remotes/origin/{short}")
    evidence["branch_refresh"] = refresh
    if not refresh["proven"]:
        if gitops.remote_branch_exists(repo, short) is False:
            return [UNPROVABLE_NO_REMOTE_REF], evidence, False
        return [REMOTE_REF_REFRESH_FAILED], evidence, False
    if refresh["after"] is None:
        return [UNPROVABLE_NO_REMOTE_REF], evidence, False
    # ``HEAD`` here would be the *main* worktree's HEAD because git -C runs in
    # the repository, so the branch tip has to be named explicitly.
    count = gitops.rev_list_count(repo, f"refs/remotes/origin/{short}..{head}")
    evidence["unpushed"] = count
    if count is None:
        return [REMOTE_REF_REFRESH_FAILED], evidence, False
    if count != 0:
        return [UNPUSHED], evidence, False
    return [], evidence, True


def _parse(value: str) -> datetime:
    moment = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return moment.replace(tzinfo=timezone.utc)


def evaluate(path, *, repo, root, main_worktree, policy=None, api=None,
             now: datetime | None = None, grace_days: int | None = None) -> Verdict:
    policy = policy or policy_mod.load(repo)
    target = Path(path)
    name = target.name
    verdict = Verdict(name=name, path=str(target), decision=HOLD)

    if not target.exists():
        verdict.decision = SKIPPED
        verdict.reason_codes = ["MISSING_PATH"]
        return verdict
    if not (target / ".git").exists():
        verdict.decision = SKIPPED
        verdict.reason_codes = [ORPHANED_DIRECTORY]
        verdict.bytes = dir_bytes(target)
        return verdict

    # C0 -- scope
    if os.path.normcase(os.path.realpath(target)) == \
            os.path.normcase(os.path.realpath(main_worktree)):
        verdict.decision = POLICY_VIOLATION
        verdict.reason_codes = [MAIN_WORKTREE]
        return verdict
    if not _under(root, target):
        verdict.decision = POLICY_VIOLATION
        verdict.reason_codes = [OUTSIDE_ROOT]
        return verdict
    if _is_reparse(target):
        verdict.decision = POLICY_VIOLATION
        verdict.reason_codes = [REPARSE_POINT]
        return verdict

    blocks = _blocked_blocks(repo)
    block = blocks.get(os.path.normcase(os.path.realpath(target)), {})
    if "locked" in block:
        verdict.reason_codes = [LOCKED]
        verdict.bytes = dir_bytes(target)
        return verdict
    # A stale "prunable" line is not evidence of absence: the directory is here.
    if "prunable" in block and target.exists():
        verdict.conditions["prunable_ignored"] = True

    try:
        marker = marker_mod.read(target)
    except FileNotFoundError:
        verdict.reason_codes = [MISSING_MARKER]
        verdict.bytes = dir_bytes(target)
        return verdict
    except marker_mod.MarkerTampered:
        verdict.reason_codes = [MARKER_TAMPERED]
        verdict.bytes = dir_bytes(target)
        return verdict
    except marker_mod.MarkerError:
        verdict.reason_codes = [MARKER_INVALID]
        verdict.bytes = dir_bytes(target)
        return verdict

    verdict.marker_state = marker["state"]
    head = gitops.head_sha(target) or marker.get("detached_head_sha")
    branch = gitops.branch_ref(target) or marker.get("branch")
    verdict.head_sha = head
    verdict.branch = branch
    verdict.bytes = dir_bytes(target)

    reasons: list[str] = []
    c3_reasons, c3, merged = _check_c3(repo, head, marker, api)
    reasons.extend(c3_reasons)
    c2_reasons, c2, pushed = _check_c2(repo, branch, merged, head)
    reasons.extend(c2_reasons)
    c1_reasons, c1, manifest = _check_c1(target, policy)
    reasons.extend(c1_reasons)
    verdict.conditions.update({"C1": c1, "C2": c2, "C3": c3})
    verdict.ignored_manifest = manifest

    if marker_mod.is_expired(marker, now=now.strftime("%Y-%m-%dT%H:%M:%SZ")
                              if now else None):
        verdict.ttl_expired = True
        reasons.append(TTL_EXPIRED)

    blocking = [code for code in reasons if code != TTL_EXPIRED]
    if blocking:
        verdict.reason_codes = sorted(set(reasons))
        return verdict
    if marker["state"] != marker_mod.RECLAIMABLE:
        verdict.reason_codes = [NOT_PROMOTED]
        return verdict

    grace = policy.reclaim_grace_days if grace_days is None else grace_days
    stamp = marker.get("reclaimable_at")
    if not stamp:
        verdict.reason_codes = [GRACE_UNKNOWN]
        return verdict
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    elapsed = (moment - _parse(stamp)).total_seconds() / 86400.0
    if elapsed < grace:
        verdict.reason_codes = [IN_GRACE]
        return verdict
    if verdict.ttl_expired:
        verdict.reason_codes = [TTL_EXPIRED]
    verdict.decision = RECLAIMABLE
    return verdict
