# -*- coding: utf-8 -*-
"""Contract #23-#25, #28-#29, #34-#35, #37, #39: reclaim execution surface."""
from __future__ import annotations

import hashlib
import json

import pytest

from _h2_support import (add_worktree, git, init_repo, make_reclaimable,
                         write_marker)

from packages.fpf_coordinator.worktree import (conditions, gitops, policy,
                                               reclaim)
from packages.fpf_runtime import worktree_lifecycle


def _policy(repo):
    return policy.load(repo)


def _plan_for(repo, path, *, grace_days=0):
    verdict = conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=_policy(repo), grace_days=grace_days)
    return reclaim.build_plan([verdict], _policy(repo)), verdict


def _prepared(tmp_path, name="wt-reclaim", branch="fpf/reclaim"):
    repo, _origin = init_repo(tmp_path)
    path = add_worktree(repo, tmp_path, name, branch)
    (path / ".fpf-runtime" / "evidence").mkdir(parents=True)
    (path / ".fpf-runtime" / "evidence" / "note.txt").write_text(
        "archived evidence\n", encoding="utf-8")
    make_reclaimable(repo, path, branch)
    return repo, path, branch


def test_audit_record_has_required_fields(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, verdict = _plan_for(repo, path)
    assert verdict.decision == conditions.RECLAIMABLE, verdict.reason_codes
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-a", apply=True,
        confirm=plan["plan_digest"])
    assert outcome["results"][0]["decision"] == reclaim.RECLAIMED
    audit_path = tmp_path / "archive" / "worktree-lifecycle" / "run-a" / "audit.json"
    document = json.loads(audit_path.read_text(encoding="utf-8"))
    assert document["audit_version"] == "fpf.worktree-audit/v1"
    assert document["run_id"] == "run-a"
    assert set(document["operator"]) >= {"login", "host", "tool_version"}
    entry = document["entries"][0]
    for key in ("name", "path", "branch", "head_sha", "task_id", "decision",
                "reason_codes", "conditions", "ignored_manifest", "archive",
                "git_ops"):
        assert key in entry, key
    assert "disk" in document


def test_disk_report_before_after(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-d", apply=True,
        confirm=plan["plan_digest"])
    disk = outcome["disk"]
    assert disk["root_bytes_before"] > disk["root_bytes_after"]
    assert disk["freed_bytes"] > 0


def test_archive_digest_recorded_before_remove(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-c", apply=True,
        confirm=plan["plan_digest"])
    archive = outcome["results"][0]["archive"]
    assert archive is not None
    stored = open(archive["path"], "rb").read()
    assert hashlib.sha256(stored).hexdigest() == archive["sha256"]
    assert archive["bytes"] == len(stored)
    assert archive["files"] >= 1


def test_plan_digest_mismatch_rejected(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-x", apply=True,
        confirm="0" * 64)
    assert outcome["decision"] == "REFUSED"
    assert outcome["reason"] == reclaim.PLAN_STALE
    assert path.exists()


def test_live_reverify_overrides_stale_plan(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, verdict = _plan_for(repo, path)
    assert verdict.decision == conditions.RECLAIMABLE
    (path / "README.md").write_text("changed after the plan\n", encoding="utf-8")
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-y", apply=True,
        confirm=plan["plan_digest"])
    assert outcome["results"][0]["decision"] == reclaim.HELD
    assert conditions.DIRTY_TRACKED in outcome["results"][0]["reason_codes"]
    assert path.exists()


def test_ignored_files_are_enumerated(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    verdict = conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=_policy(repo), grace_days=0)
    relpaths = {item["relpath"] for item in verdict.ignored_manifest}
    assert ".fpf-runtime/evidence/note.txt" in relpaths
    item = next(i for i in verdict.ignored_manifest
                if i["relpath"] == ".fpf-runtime/evidence/note.txt")
    assert item["bytes"] == (path / ".fpf-runtime/evidence/note.txt").stat().st_size
    assert len(item["sha256"]) == 64


def test_ignored_unarchived_blocks(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    (path / ".gitignore").write_text(
        (path / ".gitignore").read_text(encoding="utf-8") + ".cache/\n",
        encoding="utf-8")
    git(path, "commit", "-am", "ignore cache")
    git(repo, "push", "origin", branch)
    git(repo, "merge", "--no-ff", "-m", "merge ignore", branch)
    git(repo, "push", "origin", "main")
    (path / ".cache").mkdir()
    (path / ".cache" / "blob.bin").write_bytes(b"x" * 8)
    verdict = conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=_policy(repo), grace_days=0)
    assert conditions.IGNORED_UNARCHIVED in verdict.reason_codes


def test_archive_verify_detects_mismatch(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    actual = (path / ".fpf-runtime/evidence/note.txt").stat().st_size
    manifest = [{"relpath": ".fpf-runtime/evidence/note.txt",
                 "bytes": actual, "sha256": "0" * 64}]
    bundle = reclaim.archive(tmp_path / "archive", "wt", path, manifest,
                             path / ".fpf-worktree.json")
    ok, problems = reclaim.verify_archive(bundle["path"], manifest)
    assert ok is False
    assert any(problem.startswith("DIGEST:") for problem in problems)


def test_archive_verify_detects_missing(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    payload = (path / ".fpf-runtime/evidence/note.txt").read_bytes()
    manifest = [{"relpath": ".fpf-runtime/evidence/note.txt",
                 "bytes": len(payload),
                 "sha256": hashlib.sha256(payload).hexdigest()}]
    bundle = reclaim.archive(tmp_path / "archive", "wt", path, manifest,
                             path / ".fpf-worktree.json")
    extra = manifest + [{"relpath": ".fpf-runtime/evidence/absent.txt",
                         "bytes": 1, "sha256": "0" * 64}]
    ok, problems = reclaim.verify_archive(bundle["path"], extra)
    assert ok is False
    assert any(problem.startswith("MISSING:") for problem in problems)


def test_cleanup_recheck_after_delete(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    verdict = conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=_policy(repo), grace_days=0)
    reclaim.cleanup(path, verdict.ignored_manifest,
                    path / ".fpf-worktree.json")
    assert reclaim._leftovers(path, _policy(repo)) == []
    assert not (path / ".fpf-runtime").exists()


def test_cleanup_incomplete_preserves_site(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)

    def stray():
        (path / "stray.txt").write_text("appeared mid-flight\n", encoding="utf-8")

    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-z", apply=True,
        confirm=plan["plan_digest"], hooks={"after_archive": stray})
    assert outcome["results"][0]["decision"] == reclaim.HELD
    assert reclaim.CLEANUP_INCOMPLETE in outcome["results"][0]["reason_codes"]
    assert path.exists()


def test_detached_never_deletes_branch(tmp_path):
    repo, _origin = init_repo(tmp_path)
    base = git(repo, "rev-parse", "main").strip()
    path = repo / "_worktrees" / "wt-detached"
    git(repo, "worktree", "add", "--detach", str(path), base)
    write_marker(path, state="ACTIVE", branch=None,
                 created_at="2026-01-01T00:00:00Z")
    from packages.fpf_coordinator.worktree import marker as marker_mod
    marker = marker_mod.read(path)
    marker = marker_mod.promote(marker, {
        "pr_number": 1, "merge_commit_sha": base,
        "merged_at": "2026-01-01T00:00:00Z", "event_id": "e" * 64},
        at="2026-01-01T00:00:00Z")
    marker_mod.write(path, marker)
    plan, verdict = _plan_for(repo, path)
    assert verdict.decision == conditions.RECLAIMABLE, verdict.reason_codes
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-det", apply=True,
        confirm=plan["plan_digest"])
    result = outcome["results"][0]
    assert result["decision"] == reclaim.RECLAIMED
    assert reclaim.DETACHED_NO_BRANCH in result["reason_codes"]
    assert "branch_delete_exit" not in result["entry"]["git_ops"]


def test_branch_in_use_skips_delete(tmp_path, monkeypatch):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)
    monkeypatch.setattr(reclaim, "_branch_in_use", lambda *a, **k: True)
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-inuse", apply=True,
        confirm=plan["plan_digest"])
    result = outcome["results"][0]
    assert reclaim.BRANCH_IN_USE in result["reason_codes"]
    assert git(repo, "rev-parse", "--verify", branch, check=False).strip()


def test_branch_delete_refused_recorded(tmp_path, monkeypatch):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)
    monkeypatch.setattr(
        gitops, "delete_branch",
        lambda repo_path, name: gitops.Cmd(["git", "branch", "-d", name], 1, "", "no"))
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-refused", apply=True,
        confirm=plan["plan_digest"])
    result = outcome["results"][0]
    assert result["decision"] == reclaim.RECLAIMED
    assert reclaim.BRANCH_DELETE_REFUSED in result["reason_codes"]
    assert result["entry"]["git_ops"]["branch_delete_exit"] == 1


def test_stash_is_repo_level(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    (repo / "README.md").write_text("stashed\n", encoding="utf-8")
    git(repo, "stash", "push", "-m", "shared stash")
    state = reclaim.repo_stash(repo)
    assert state["present"] is True
    assert state["entries"] == 1
    verdict = conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=_policy(repo), grace_days=0)
    assert not hasattr(verdict, "stash")


def test_stash_requires_ack(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    (repo / "README.md").write_text("stashed\n", encoding="utf-8")
    git(repo, "stash", "push", "-m", "shared stash")
    plan, _verdict = _plan_for(repo, path)
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-stash", apply=True,
        confirm=plan["plan_digest"])
    assert outcome["results"][0]["reason_codes"] == [reclaim.STASH_UNACKNOWLEDGED]
    assert path.exists()


def test_repair_not_in_reclaim_cli():
    parser = worktree_lifecycle.build_parser()
    actions = [action for action in parser._actions
               if action.__class__.__name__ == "_SubParsersAction"]
    assert "repair" not in actions[0].choices
    with pytest.raises(SystemExit):
        parser.parse_args(["repair"])


def test_remote_advanced_blocks_final(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)

    def new_work():
        (path / "late.txt").write_text("late\n", encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-m", "late work")

    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-late", apply=True,
        confirm=plan["plan_digest"], hooks={"before_final": new_work})
    result = outcome["results"][0]
    assert result["decision"] == reclaim.HELD
    assert result["reason_codes"][0] in (
        reclaim.TARGET_IDENTITY_CHANGED, reclaim.FINAL_REVALIDATION_FAILED)
    assert path.exists()


def test_merge_state_changed_blocks(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    before_merge = git(repo, "rev-parse", "main~1").strip()
    plan, _verdict = _plan_for(repo, path)

    def rewind_main():
        git(repo, "reset", "--hard", before_merge)
        git(repo, "push", "--force", "origin", "main")

    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-rewind", apply=True,
        confirm=plan["plan_digest"], hooks={"before_final": rewind_main})
    result = outcome["results"][0]
    assert result["decision"] == reclaim.HELD
    assert any(code in result["reason_codes"] for code in (
        conditions.NOT_MERGED, reclaim.FINAL_REVALIDATION_FAILED))
    assert path.exists()


def test_head_changed_blocks(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)

    def move_head():
        (path / "moved.txt").write_text("moved\n", encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-m", "moved head")

    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-head", apply=True,
        confirm=plan["plan_digest"], hooks={"before_final": move_head})
    result = outcome["results"][0]
    assert reclaim.TARGET_IDENTITY_CHANGED in result["reason_codes"]
    assert path.exists()


def test_final_revalidation_failure_preserves(tmp_path):
    repo, path, branch = _prepared(tmp_path)
    plan, _verdict = _plan_for(repo, path)

    def dirty_it():
        (path / "README.md").write_text("dirty late\n", encoding="utf-8")

    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-final", apply=True,
        confirm=plan["plan_digest"], hooks={"before_final": dirty_it})
    result = outcome["results"][0]
    assert result["decision"] == reclaim.HELD
    assert path.exists()
    assert (path / "README.md").exists()


def test_batch_stops_after_failure(tmp_path):
    repo, _origin = init_repo(tmp_path)
    paths = []
    for index in (1, 2):
        branch = f"fpf/batch-{index}"
        path = add_worktree(repo, tmp_path, f"wt-batch-{index}", branch)
        make_reclaimable(repo, path, branch)
        paths.append((path, branch))
    verdicts = [conditions.evaluate(
        path, repo=repo, root=repo / "_worktrees", main_worktree=repo,
        policy=_policy(repo), grace_days=0) for path, _branch in paths]
    plan = reclaim.build_plan(verdicts, _policy(repo))
    assert len(plan["candidates"]) == 2
    calls = {"n": 0}

    def fail_first():
        calls["n"] += 1
        (paths[0][0] / "README.md").write_text("late change\n", encoding="utf-8")

    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=_policy(repo),
        archive_root=tmp_path / "archive", run_id="run-batch", apply=True,
        confirm=plan["plan_digest"], hooks={"before_final": fail_first})
    assert outcome["decision"] == "STOPPED"
    assert len(outcome["results"]) == 1
    assert calls["n"] == 1
