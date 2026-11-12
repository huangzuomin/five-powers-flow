# -*- coding: utf-8 -*-
"""Contract #31 and #36: remote-tracking truth and the squash-merge fact."""
from __future__ import annotations

import subprocess

from _h2_support import add_worktree, git, init_repo, write_marker

from packages.fpf_coordinator.worktree import conditions, policy


def _evaluate(repo, path, api=None):
    return conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=policy.load(repo), api=api, grace_days=0)


def _clone(origin, tmp_path):
    other = tmp_path / "other"
    subprocess.run(["git", "clone", str(origin), str(other)], check=True,
                   capture_output=True)
    git(other, "config", "user.email", "other@example.invalid")
    git(other, "config", "user.name", "Other DEV")
    return other


def test_remote_ref_refreshed_per_branch(tmp_path):
    repo, origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-refresh", "fpf/refresh")
    write_marker(path, branch="refs/heads/fpf/refresh")
    stale = git(repo, "rev-parse", "refs/remotes/origin/fpf/refresh").strip()
    other = _clone(origin, tmp_path)
    git(other, "checkout", "fpf/refresh")
    (other / "remote.txt").write_text("remote work\n", encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-m", "remote-side commit")
    git(other, "push", "origin", "fpf/refresh")
    advanced = git(other, "rev-parse", "HEAD").strip()
    assert advanced != stale
    verdict = _evaluate(repo, path)
    refresh = verdict.conditions["C2"]["branch_refresh"]
    assert refresh["refspec"] == "+refs/heads/fpf/refresh:refs/remotes/origin/fpf/refresh"
    assert refresh["proven"] is True
    assert refresh["before"] == stale
    assert refresh["after"] == advanced
    assert verdict.conditions["C2"]["unpushed"] == 0


def test_refresh_failure_unprovable(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-broken", "fpf/broken")
    write_marker(path, branch="refs/heads/fpf/broken")
    git(repo, "remote", "set-url", "origin", str(tmp_path / "does-not-exist.git"))
    verdict = _evaluate(repo, path)
    assert verdict.decision == conditions.HOLD
    codes = set(verdict.reason_codes)
    assert codes & {conditions.REMOTE_REF_REFRESH_FAILED, conditions.FETCH_FAILED}
    assert conditions.UNPUSHED not in codes


def test_stale_remote_ref_never_proves_no_unpushed(tmp_path):
    repo, origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-rewritten", "fpf/rewritten")
    (path / "local.txt").write_text("local work\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "local work")
    git(repo, "push", "origin", "fpf/rewritten")
    head = git(path, "rev-parse", "HEAD").strip()
    write_marker(path, branch="refs/heads/fpf/rewritten")
    assert git(repo, "rev-parse", "refs/remotes/origin/fpf/rewritten").strip() == head
    other = _clone(origin, tmp_path)
    git(other, "checkout", "-B", "fpf/rewritten", "origin/main")
    (other / "rewritten.txt").write_text("different history\n", encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-m", "rewritten history")
    git(other, "push", "--force", "origin", "fpf/rewritten")
    verdict = _evaluate(repo, path)
    assert conditions.UNPUSHED in verdict.reason_codes
    assert verdict.conditions["C2"]["branch_refresh"]["after"] != head


def test_squash_merge_via_api_fact(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-squash", "fpf/squash")
    (path / "feature.txt").write_text("squashed feature\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "feature")
    git(repo, "push", "origin", "fpf/squash")
    head = git(path, "rev-parse", "HEAD").strip()
    (repo / "feature.txt").write_text("squashed feature\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "squash feature")
    git(repo, "push", "origin", "main")
    squash_sha = git(repo, "rev-parse", "HEAD").strip()
    assert git(repo, "merge-base", "--is-ancestor", head, "main", check=False) == ""
    merge_fact = {"pr_number": 7, "merge_commit_sha": squash_sha,
                  "merged_at": "2026-01-01T00:00:00Z", "event_id": "e" * 64}
    write_marker(path, state="ACTIVE", branch="refs/heads/fpf/squash",
                 created_at="2026-01-01T00:00:00Z", merge_fact=merge_fact)
    responses = []

    def api(pr_number):
        responses.append(pr_number)
        return {"state": "merged", "head": {"sha": head},
                "merge_commit_sha": squash_sha}

    verdict = _evaluate(repo, path, api=api)
    assert responses == [7]
    assert verdict.conditions["C3"]["basis"] == "api_merge_fact"
    assert conditions.NOT_MERGED not in verdict.reason_codes


def test_squash_merge_unverifiable_without_api(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-squash2", "fpf/squash2")
    (path / "feature.txt").write_text("squashed feature\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "feature")
    git(repo, "push", "origin", "fpf/squash2")
    (repo / "feature.txt").write_text("squashed feature\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "squash feature")
    git(repo, "push", "origin", "main")
    squash_sha = git(repo, "rev-parse", "HEAD").strip()
    write_marker(path, state="ACTIVE", branch="refs/heads/fpf/squash2",
                 created_at="2026-01-01T00:00:00Z",
                 merge_fact={"pr_number": 8, "merge_commit_sha": squash_sha,
                             "merged_at": "2026-01-01T00:00:00Z",
                             "event_id": "e" * 64})
    verdict = _evaluate(repo, path, api=None)
    assert conditions.NOT_MERGED in verdict.reason_codes


def test_squash_merge_api_unavailable_is_unverifiable(tmp_path):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, "wt-squash3", "fpf/squash3")
    (path / "feature.txt").write_text("squashed feature\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "feature")
    git(repo, "push", "origin", "fpf/squash3")
    (repo / "feature.txt").write_text("squashed feature\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "squash feature")
    git(repo, "push", "origin", "main")
    squash_sha = git(repo, "rev-parse", "HEAD").strip()
    write_marker(path, state="ACTIVE", branch="refs/heads/fpf/squash3",
                 created_at="2026-01-01T00:00:00Z",
                 merge_fact={"pr_number": 9, "merge_commit_sha": squash_sha,
                             "merged_at": "2026-01-01T00:00:00Z",
                             "event_id": "e" * 64})

    def broken(_pr_number):
        raise TimeoutError("github unreachable")

    verdict = _evaluate(repo, path, api=broken)
    assert conditions.MERGE_FACT_UNVERIFIABLE in verdict.reason_codes
