# -*- coding: utf-8 -*-
"""Shared fixtures for the H2 contract tests.

Every test builds a real repository with a real (bare) remote.  The three
conditions are then answered by git itself, not by a mock that agrees with the
implementation.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.fpf_coordinator.worktree import marker as marker_mod  # noqa: E402


def git(repo, *args, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *[str(arg) for arg in args]],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and completed.returncode != 0:
        raise AssertionError(
            f"git {' '.join(str(a) for a in args)} failed: {completed.stderr}")
    return completed.stdout


def init_repo(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)],
                   check=True, capture_output=True)
    git(repo, "config", "user.email", "dev@example.invalid")
    git(repo, "config", "user.name", "FPF DEV")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".fpf-runtime/\n.fpf-worktree.json\n",
                                     encoding="utf-8")
    git(repo, "add", "README.md", ".gitignore")
    git(repo, "commit", "-m", "seed")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-u", "origin", "main")
    return repo, origin


def base_sha(repo) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def add_worktree(repo, tmp_path: Path, name: str, branch: str,
                 *, push: bool = True) -> Path:
    root = Path(repo) / "_worktrees"
    root.mkdir(exist_ok=True)
    path = root / name
    git(repo, "worktree", "add", "-b", branch, str(path), "main")
    git(path, "config", "user.email", "dev@example.invalid")
    git(path, "config", "user.name", "FPF DEV")
    if push:
        git(repo, "push", "-u", "origin", branch)
    return path


def merge_branch(repo, branch: str) -> None:
    git(repo, "merge", "--no-ff", "-m", f"merge {branch}", branch)
    git(repo, "push", "origin", "main")


def write_marker(path, *, task_id="FPF2-H2-TEST", state="ACTIVE",
                 branch=None, base=None, ttl_days=14, created_at=None,
                 reclaimable_at=None, merge_fact=None, owner=None) -> dict:
    repo = Path(path)
    if branch is None:
        branch = git(repo, "symbolic-ref", "-q", "HEAD", check=False).strip() or None
    elif branch and not branch.startswith("refs/heads/"):
        branch = "refs/heads/" + branch
    marker = marker_mod.create(
        task_id=task_id,
        base_sha=base or base_sha(repo),
        owner=owner or {"login": "huangzuomin", "station": "ST-DEV-AUTHOR-01"},
        work_order_id="WO-H2-TEST",
        branch=branch if branch else None,
        detached_head_sha=None if branch else git(repo, "rev-parse", "HEAD").strip(),
        ttl_days=ttl_days,
        created_at=created_at,
    )
    if state != "ACTIVE":
        marker = marker_mod.append_history(marker, state, "test", at=created_at)
    if reclaimable_at:
        marker = dict(marker)
        marker["reclaimable_at"] = reclaimable_at
        marker["digest"] = marker_mod.compute_digest(marker)
    if merge_fact:
        marker = dict(marker)
        marker["merge_fact"] = merge_fact
        marker["digest"] = marker_mod.compute_digest(marker)
    marker_mod.write(repo, marker)
    return marker


def make_reclaimable(repo, path, branch, *, task_id="FPF2-H2-TEST") -> dict:
    (Path(path) / "work.txt").write_text(
        f"branch work {branch} {task_id}\n", encoding="utf-8")
    git(path, "add", "work.txt")
    git(path, "commit", "-m", f"work for {branch}")
    git(repo, "push", "origin", branch)
    merge_branch(repo, branch)
    head = git(path, "rev-parse", "HEAD").strip()
    fact = {
        "pr_number": 123,
        "merge_commit_sha": git(repo, "rev-parse", "HEAD").strip(),
        "merged_at": "2026-01-01T00:00:00Z",
        "event_id": "e" * 64,
    }
    marker = write_marker(path, task_id=task_id, state="ACTIVE", branch=branch,
                          created_at="2026-01-01T00:00:00Z")
    marker = marker_mod.promote(marker, fact, at="2026-01-01T00:00:00Z")
    marker_mod.write(path, marker)
    return marker
