# -*- coding: utf-8 -*-
"""Thin git boundary.

Every worktree question is asked in the D1 form
``git --git-dir=<worktree gitdir> --work-tree=<abs path>``.  ``-C`` is not
used: for a linked worktree it is ambiguous about which gitdir answered, and
that ambiguity is exactly how a dirty worktree gets reported as clean.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cmd:
    argv: list[str]
    exit: int
    output: str
    stderr: str = ""

    @property
    def command(self) -> str:
        return " ".join(self.argv)

    @property
    def output_sha256(self) -> str:
        return hashlib.sha256(self.output.encode("utf-8", "replace")).hexdigest()

    def as_evidence(self) -> dict:
        return {
            "command": self.command,
            "exit": self.exit,
            "output_sha256": self.output_sha256,
            "output_head": "\n".join(self.output.splitlines()[:20]),
        }


def run(argv, cwd=None, timeout: int = 180) -> Cmd:
    try:
        completed = subprocess.run(
            [str(part) for part in argv], cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return Cmd([str(part) for part in argv], 124, "", "timeout")
    return Cmd([str(part) for part in argv], completed.returncode,
               completed.stdout or "", completed.stderr or "")


def gitdir(path) -> Path:
    base = Path(path)
    dotgit = base / ".git"
    if dotgit.is_file():
        text = dotgit.read_text(encoding="utf-8", errors="replace").strip()
        if text.lower().startswith("gitdir:"):
            raw = text.split(":", 1)[1].strip()
            candidate = Path(raw)
            return candidate if candidate.is_absolute() else (base / candidate).resolve()
    if dotgit.is_dir():
        return dotgit
    raise FileNotFoundError(f"no gitdir for {base}")


def worktree_blocks(repo) -> list[dict]:
    result = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    if result.exit != 0:
        raise RuntimeError(result.stderr.strip() or "git worktree list failed")
    blocks, current = [], {}
    for line in result.output.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        blocks.append(current)
    return blocks


def _wt(path) -> list[str]:
    return ["git", f"--git-dir={gitdir(path)}", f"--work-tree={Path(path)}"]


def status(path) -> Cmd:
    return run(_wt(path) + [
        "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching",
    ])


def head_sha(path) -> str | None:
    result = run(_wt(path) + ["rev-parse", "HEAD"])
    return result.output.strip() if result.exit == 0 else None


def branch_ref(path) -> str | None:
    result = run(_wt(path) + ["symbolic-ref", "-q", "HEAD"])
    return result.output.strip() if result.exit == 0 else None


def in_progress(path) -> list[str]:
    base = gitdir(path)
    checks = {
        "REBASE_MERGE": base / "rebase-merge",
        "REBASE_APPLY": base / "rebase-apply",
        "MERGE": base / "MERGE_HEAD",
        "CHERRY_PICK": base / "CHERRY_PICK_HEAD",
        "REVERT": base / "REVERT_HEAD",
        "BISECT": base / "BISECT_LOG",
        "INDEX_LOCK": base / "index.lock",
    }
    return [name for name, probe in checks.items() if probe.exists()]


def submodules(path) -> Cmd:
    return run(_wt(path) + ["submodule", "status", "--recursive"])


def dirty_submodules(path) -> list[str]:
    result = submodules(path)
    if result.exit != 0:
        return []
    return [line for line in result.output.splitlines()
            if line[:1] in ("+", "-", "U")]


def rev_parse(repo, ref) -> str | None:
    result = run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref])
    return result.output.strip() if result.exit == 0 and result.output.strip() else None


def is_ancestor(repo, sha: str, ref: str) -> bool | None:
    if not sha:
        return None
    result = run(["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, ref])
    if result.exit == 0:
        return True
    if result.exit == 1:
        return False
    return None


def rev_list_count(repo, spec: str) -> int | None:
    result = run(["git", "-C", str(repo), "rev-list", "--count", spec])
    if result.exit != 0:
        return None
    try:
        return int(result.output.strip())
    except ValueError:
        return None


def fetch(repo, refspec: str) -> dict:
    """Refresh one remote-tracking ref explicitly and prove the new value."""
    target = refspec.split(":", 1)[1] if ":" in refspec else refspec
    before = rev_parse(repo, target)
    result = run(["git", "-C", str(repo), "fetch", "origin", refspec])
    after = rev_parse(repo, target)
    return {
        "refspec": refspec,
        "before": before,
        "exit": result.exit,
        "after": after,
        "command": result.command,
        "stderr": result.stderr.strip(),
        "proven": result.exit == 0 and after is not None,
    }


def remote_branch_exists(repo, branch: str) -> bool | None:
    """``None`` means the remote itself could not be asked."""
    result = run(["git", "-C", str(repo), "ls-remote", "--exit-code",
                  "--heads", "origin", branch])
    if result.exit == 0:
        return True
    if result.exit == 2:
        return False
    return None


def remove_worktree(repo, path) -> Cmd:
    return run(["git", "-C", str(repo), "worktree", "remove", str(path)])


def delete_branch(repo, branch: str) -> Cmd:
    return run(["git", "-C", str(repo), "branch", "-d", branch])


def prune_path(repo, path) -> Cmd:
    return run(["git", "-C", str(repo), "worktree", "prune", str(path)])


def real_path(path) -> str:
    return os.path.normcase(os.path.realpath(str(path)))
