# -*- coding: utf-8 -*-
"""Contract #17-#22, #26-#30, #32-#33: C0 scope and the three conditions."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from _h2_support import (add_worktree, base_sha, git, init_repo,
                         make_reclaimable, write_marker)

from packages.fpf_coordinator.worktree import conditions, gitops, policy

NOW = datetime(2026, 11, 12, 1, 0, 0, tzinfo=timezone.utc)


def _evaluate(repo, path, **kwargs):
    return conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees",
        main_worktree=repo, policy=policy.load(repo), now=NOW,
        grace_days=0, **kwargs)


def test_reclaim_rejected_when_dirty(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-dirty", "fpf/dirty")
    make_reclaimable(repo, path, "fpf/dirty")
    (path / "README.md").write_text("changed\n", encoding="utf-8")
    verdict = _evaluate(repo, path)
    assert verdict.decision == conditions.HOLD
    assert conditions.DIRTY_TRACKED in verdict.reason_codes


def test_reclaim_rejected_when_untracked(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-untracked", "fpf/untracked")
    make_reclaimable(repo, path, "fpf/untracked")
    (path / "notes.txt").write_text("scratch\n", encoding="utf-8")
    verdict = _evaluate(repo, path)
    assert conditions.DIRTY_UNTRACKED in verdict.reason_codes


def test_reclaim_rejected_when_unpushed(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-unpushed", "fpf/unpushed")
    make_reclaimable(repo, path, "fpf/unpushed")
    (path / "local.txt").write_text("only here\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "unpushed")
    verdict = _evaluate(repo, path)
    assert conditions.UNPUSHED in verdict.reason_codes


def test_reclaim_rejected_when_not_merged(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-unmerged", "fpf/unmerged")
    (path / "feature.txt").write_text("work\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "unmerged work")
    git(repo, "push", "origin", "fpf/unmerged")
    write_marker(path, state="RECLAIMABLE", branch="refs/heads/fpf/unmerged",
                 created_at="2026-01-01T00:00:00Z")
    verdict = _evaluate(repo, path)
    assert conditions.NOT_MERGED in verdict.reason_codes


def test_reclaim_rejected_when_no_remote_ref(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-noremote", "fpf/noremote",
                        push=False)
    write_marker(path, state="RECLAIMABLE", branch="refs/heads/fpf/noremote",
                 created_at="2026-01-01T00:00:00Z")
    verdict = _evaluate(repo, path)
    assert conditions.UNPROVABLE_NO_REMOTE_REF in verdict.reason_codes
    assert conditions.UNPUSHED not in verdict.reason_codes


def test_reclaim_rejected_when_in_progress_op(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-merge", "fpf/merging")
    make_reclaimable(repo, path, "fpf/merging")
    (gitops.gitdir(path) / "MERGE_HEAD").write_text("0" * 40, encoding="utf-8")
    verdict = _evaluate(repo, path)
    assert "IN_PROGRESS_MERGE" in verdict.reason_codes
    assert verdict.decision == conditions.HOLD


def test_ttl_expired_warns_only(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-ttl", "fpf/ttl")
    make_reclaimable(repo, path, "fpf/ttl")
    marker = write_marker(path, state="ACTIVE", branch="refs/heads/fpf/ttl",
                          created_at="2020-01-01T00:00:00Z", ttl_days=1)
    merge_sha = git(repo, "rev-parse", "main").strip()
    marker = dict(marker)
    marker["merge_fact"] = {"pr_number": 123, "merge_commit_sha": merge_sha,
                            "merged_at": "2026-01-01T00:00:00Z",
                            "event_id": "e" * 64}
    from packages.fpf_coordinator.worktree import marker as marker_mod
    marker = marker_mod.promote(marker, marker["merge_fact"], at="2020-01-02T00:00:00Z")
    marker_mod.write(path, marker)
    verdict = _evaluate(repo, path)
    assert verdict.ttl_expired is True
    assert conditions.TTL_EXPIRED in verdict.reason_codes
    assert verdict.decision == conditions.RECLAIMABLE


def test_ttl_expired_dirty_not_deleted(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-ttl-dirty", "fpf/ttl-dirty")
    make_reclaimable(repo, path, "fpf/ttl-dirty")
    (path / "README.md").write_text("dirty\n", encoding="utf-8")
    write_marker(path, state="RECLAIMABLE", branch="refs/heads/fpf/ttl-dirty",
                 created_at="2020-01-01T00:00:00Z", ttl_days=1)
    verdict = _evaluate(repo, path)
    assert verdict.decision == conditions.HOLD
    assert path.exists()


def test_ttl_expired_unmerged_not_deleted(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-ttl-unmerged", "fpf/ttl-unmerged")
    (path / "feature.txt").write_text("work\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "unmerged work")
    git(repo, "push", "origin", "fpf/ttl-unmerged")
    write_marker(path, state="RECLAIMABLE", branch="refs/heads/fpf/ttl-unmerged",
                 created_at="2020-01-01T00:00:00Z", ttl_days=1)
    verdict = _evaluate(repo, path)
    assert verdict.decision == conditions.HOLD
    assert conditions.NOT_MERGED in verdict.reason_codes
    assert path.exists()


def test_main_worktree_never_reclaimable(tmp_path):
    repo, _origin = init_repo(tmp_path)
    verdict = _evaluate(repo, repo)
    assert verdict.decision == conditions.POLICY_VIOLATION
    assert verdict.reason_codes == [conditions.MAIN_WORKTREE]


def test_path_outside_root_rejected(tmp_path):
    repo, _origin = init_repo(tmp_path)
    outside = tmp_path / "outside-wt"
    git(repo, "worktree", "add", "-b", "fpf/outside", str(outside), "main")
    write_marker(outside, branch="refs/heads/fpf/outside")
    verdict = _evaluate(repo, outside)
    assert verdict.decision == conditions.POLICY_VIOLATION
    assert conditions.OUTSIDE_ROOT in verdict.reason_codes


def test_orphaned_directory_never_auto_reclaimed(tmp_path):
    repo, _origin = init_repo(tmp_path)
    orphan = repo / "_worktrees" / "orphan"
    orphan.mkdir(parents=True)
    (orphan / "payload.bin").write_bytes(b"x" * 32)
    verdict = _evaluate(repo, orphan)
    assert verdict.decision == conditions.SKIPPED
    assert verdict.reason_codes == [conditions.ORPHANED_DIRECTORY]
    assert orphan.exists()


def test_prunable_flag_ignored_when_directory_exists(tmp_path, monkeypatch):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-prunable", "fpf/prunable")
    make_reclaimable(repo, path, "fpf/prunable")
    real = gitops.worktree_blocks
    head = git(path, "rev-parse", "HEAD").strip()

    def fake(repo_path):
        return [{"worktree": str(path), "HEAD": head,
                 "branch": "refs/heads/fpf/prunable", "prunable": "gone"}]

    monkeypatch.setattr(gitops, "worktree_blocks", fake)
    try:
        verdict = _evaluate(repo, path)
    finally:
        monkeypatch.setattr(gitops, "worktree_blocks", real)
    assert verdict.conditions.get("prunable_ignored") is True
    assert verdict.decision != conditions.SKIPPED


def test_git_dir_work_tree_form_used_not_dash_c(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-form", "fpf/form")
    command = gitops.status(path).command
    assert "--git-dir=" in command
    assert "--work-tree=" in command
    assert " -C " not in command
