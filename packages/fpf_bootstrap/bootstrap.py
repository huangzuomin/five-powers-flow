"""Project bootstrap provisioning with isolated Git worktrees; never alters main."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from .artifacts import bundle, safe_id
from .discovery import absolute_repo, git, inventory

def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents

def layout(repo: Path, workspace_root: Path, project_id: str) -> dict[str, Path]:
    safe_id(project_id)
    root = workspace_root.resolve() / project_id
    if _inside(root, repo.resolve()) or _inside(repo.resolve(), root):
        raise ValueError("Workspace root must be outside the target Git repository")
    return {"root": root, "bootstrap": root / "bootstrap",
            "dev": root / "dev", "qa": root / "qa", "state": root / "bootstrap-state.json"}

def _common(path: Path) -> str:
    return str(Path(git(path, "rev-parse", "--path-format=absolute",
                        "--git-common-dir")).resolve())

def _ensure_worktree(repo: Path, directory: Path, branch: str | None, sha: str) -> str:
    if directory.exists():
        if not directory.is_dir() or _common(directory) != _common(repo):
            raise RuntimeError("Worktree path occupied by another repository: " + str(directory))
        actual = git(directory, "branch", "--show-current")
        if (branch is None and actual) or (branch is not None and actual != branch):
            raise RuntimeError("Worktree branch mismatch at " + str(directory))
        if git(directory, "rev-parse", "HEAD") != sha:
            raise RuntimeError("Existing worktree baseline SHA differs")
        return "reused"
    directory.parent.mkdir(parents=True, exist_ok=True)
    if branch:
        # Never take over an unrelated existing branch.
        exists = subprocess.run(["git", "show-ref", "--verify", "--quiet",
                                 "refs/heads/" + branch], cwd=repo, check=False)
        if exists.returncode == 0:
            raise RuntimeError("Branch exists without expected worktree: " + branch)
        git(repo, "worktree", "add", "-b", branch, str(directory), sha)
    else:
        git(repo, "worktree", "add", "--detach", str(directory), sha)
    if git(directory, "rev-parse", "HEAD") != sha:
        raise RuntimeError("Created worktree at wrong SHA")
    return "created"

def plan(repo: Path, workspace_root: Path, project_id: str,
         title: str, mode: str, base_ref: str = "HEAD",
         docs_dir: str = "docs",
         allow_existing_governance: bool = False) -> dict:
    if mode not in ("api", "manual"):
        raise ValueError("agent mode must be api or manual")
    safe_id(project_id)
    repo = absolute_repo(repo)
    discovered = inventory(repo, base_ref, docs_dir)
    paths = layout(repo, workspace_root, project_id)
    files = bundle(project_id, title or project_id, discovered, mode)
    # Never overwrite governance configuration present in the baseline.
    tracked = set(git(repo, "ls-tree", "-r", "--name-only", discovered["sha"]).splitlines())
    collision = sorted(tracked.intersection(files))
    if collision:
        if not allow_existing_governance:
            raise RuntimeError("Project already has governance files; refusing overwrite: " +
                               ", ".join(collision[:12]))
        for name in collision:
            del files[name]
    return {"project_id": project_id, "title": title or project_id, "mode": mode,
            "base_ref": base_ref, "docs_dir": docs_dir,
            "discovery": discovered, "paths": {k: str(v) for k, v in paths.items()},
            "files": files, "branches": {
                "bootstrap": "fpf/bootstrap-" + project_id,
                "dev": "fpf/dev-" + project_id},
            "status": "BOOTSTRAP_PLAN"}

def _atomic_json(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def apply(repo: Path, proposed: dict) -> dict:
    repo = absolute_repo(repo)
    d = proposed["discovery"]
    paths = {k: Path(v).resolve() for k, v in proposed["paths"].items()}
    sha = d["sha"]
    # Validation before all writes; branch refs still may be created incrementally.
    if git(repo, "cat-file", "-t", sha) != "commit":
        raise RuntimeError("Baseline commit no longer exists")
    previous = paths["state"]
    if previous.exists():
        state = json.loads(previous.read_text(encoding="utf-8"))
        if (state["project_id"] != proposed["project_id"] or
                state["baseline_sha"] != sha or state["repo"] != str(repo)):
            raise RuntimeError("Existing bootstrap state conflicts with proposal")
    paths["root"].mkdir(parents=True, exist_ok=True)
    if not previous.exists():
        # Write recoverable intent before the first non-atomic Git worktree action.
        _atomic_json(previous, {
            "project_id": proposed["project_id"], "repo": str(repo),
            "baseline_sha": sha, "bootstrap_state": "PENDING",
            "agent_status": "CONFIGURED_NOT_VERIFIED",
            "agent_mode": proposed["mode"],
            "title": proposed.get("title", proposed["project_id"]),
            "base_ref": proposed.get("base_ref", "HEAD"),
            "docs_dir": proposed.get("docs_dir", "docs"),
            "paths": proposed["paths"], "branches": proposed["branches"],
            "generated_files": sorted(proposed["files"]),
            "human_approval_required": True, "slice_authorized": False,
        })
    _ensure_worktree(repo, paths["bootstrap"], proposed["branches"]["bootstrap"], sha)
    _ensure_worktree(repo, paths["dev"], proposed["branches"]["dev"], sha)
    _ensure_worktree(repo, paths["qa"], None, sha)
    for name, content in proposed["files"].items():
        target = paths["bootstrap"] / name
        if not target.resolve().is_relative_to(paths["bootstrap"]):
            raise RuntimeError("Generated file escaped bootstrap worktree")
        if target.exists():
            # Idempotent only on identical content; preserve all user changes.
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                raise RuntimeError("Existing bootstrap file differs; will not overwrite: " + name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    state = {
        "project_id": proposed["project_id"], "repo": str(repo),
        "baseline_sha": sha, "bootstrap_state": "BOOTSTRAP_REVIEW",
        "agent_mode": proposed["mode"], "agent_status": "CONFIGURED_NOT_VERIFIED",
        "title": proposed.get("title", proposed["project_id"]),
        "base_ref": proposed.get("base_ref", "HEAD"),
        "docs_dir": proposed.get("docs_dir", "docs"),
        "paths": proposed["paths"], "branches": proposed["branches"],
        "generated_files": sorted(proposed["files"]), "human_approval_required": True,
        "slice_authorized": False,
    }
    paths["root"].mkdir(parents=True, exist_ok=True)
    _atomic_json(previous, state)
    return state

def rollback(repo: Path, workspace_root: Path, project_id: str) -> dict:
    """Remove only pristine worktrees from an incomplete, recorded bootstrap."""
    repo = absolute_repo(repo)
    paths = layout(repo, workspace_root, project_id)
    if not paths["state"].is_file():
        raise RuntimeError("No recorded bootstrap to rollback")
    state = json.loads(paths["state"].read_text(encoding="utf-8"))
    if state.get("bootstrap_state") != "PENDING":
        raise RuntimeError("Rollback is only supported while bootstrap is PENDING")
    if state.get("project_id") != project_id or state.get("repo") != str(repo):
        raise RuntimeError("State does not belong to this project")
    sha = state["baseline_sha"]
    from .discovery import inventory
    title = state.get("title", project_id)
    base_ref = state.get("base_ref", "HEAD")
    docs_dir = state.get("docs_dir", "docs")
    candidate = bundle(project_id, title, inventory(repo, base_ref, docs_dir),
                       state.get("agent_mode", "api"))
    # Inspect all worktrees before deleting even one. No force unless the
    # *entire* dirty surface is an exact generated bootstrap file.
    for role in ("bootstrap", "dev", "qa"):
        path = paths[role]
        if not path.exists():
            continue
        if not path.is_dir() or _common(path) != _common(repo):
            raise RuntimeError("Foreign worktree; rollback refused: " + role)
        if git(path, "rev-parse", "HEAD") != sha:
            raise RuntimeError("Advanced worktree; rollback refused: " + role)
        if role in ("dev", "qa") and git(path, "status", "--porcelain"):
            raise RuntimeError("Dirty worktree; rollback refused: " + role)
        if role == "bootstrap":
            # Check the entire untracked directory tree, rather than relying
            # on git status which can abbreviate untracked directories.
            actual = {
                file.relative_to(path).as_posix()
                for file in path.rglob("*") if file.is_file()
                and ".git" not in file.relative_to(path).parts
            }
            expected = set(candidate) | {".git"}
            tracked = set(git(repo, "ls-tree", "-r", "--name-only", sha).splitlines())
            for name in actual:
                if name in tracked:
                    if git(path, "status", "--porcelain", "--", name):
                        raise RuntimeError("Modified tracked file; rollback refused: " + name)
                    continue
                if name not in expected:
                    raise RuntimeError("Unexpected user file; rollback refused: " + name)
                if (path / name).read_text(encoding="utf-8") != candidate[name]:
                    raise RuntimeError("Modified generated file; rollback refused: " + name)
    for role in ("qa", "dev", "bootstrap"):
        path = paths[role]
        if path.exists():
            git(repo, "worktree", "remove", "--force", str(path))
        branch = state["branches"].get(role)
        if branch:
            p = subprocess.run(["git", "show-ref", "--verify", "--quiet",
                                "refs/heads/" + branch], cwd=repo, check=False)
            if p.returncode == 0:
                if git(repo, "rev-parse", branch) != sha:
                    raise RuntimeError("Advanced branch; rollback refused: " + branch)
                git(repo, "branch", "-D", branch)
    paths["state"].unlink()
    return {"project_id": project_id, "rollback": "COMPLETE"}


def doctor(repo: Path, workspace_root: Path, project_id: str,
           require_ready: bool = True) -> dict:
    repo = absolute_repo(repo)
    paths = layout(repo, workspace_root, project_id)
    errors = []
    if not paths["state"].is_file():
        return {"project_id": project_id, "state": "UNINITIALIZED",
                "ok": False, "issues": ["Missing local bootstrap state"]}
    state = json.loads(paths["state"].read_text(encoding="utf-8"))
    sha = state["baseline_sha"]
    if state.get("repo") != str(repo):
        errors.append("Project repository mismatch")
    for role in ("bootstrap", "dev", "qa"):
        path = paths[role]
        try:
            if not path.is_dir() or _common(path) != _common(repo):
                errors.append(role + " is missing or not from this Git repository")
                continue
            if git(path, "rev-parse", "HEAD") != sha:
                errors.append(role + " baseline has changed since initialization")
            actual_branch = git(path, "branch", "--show-current")
            expected = state["branches"].get(role, "")
            if actual_branch != expected:
                errors.append(role + " branch/detached state mismatch")
        except (RuntimeError, OSError) as exc:
            errors.append(role + ": " + str(exc))
    for filename in state["generated_files"]:
        if not (paths["bootstrap"] / filename).is_file():
            errors.append("Missing project artifact: " + filename)
    if state.get("bootstrap_state") == "PENDING":
        errors.append("Bootstrap is PENDING; resume fpf init --apply or inspect before --rollback")
    if require_ready:
        # Do not take approval from an editable local JSON boolean. Only a
        # future server-authorized bootstrap review/commit can establish READY.
        if state.get("agent_status") != "VERIFIED":
            errors.append("Agent conversations are configured but have NOT been provisioned/verified")
        errors.append("Bootstrap map has not been approved and merged into the target main branch")
    return {"project_id": project_id,
            "state": ("BOOTSTRAP_PARTIAL" if errors else
                      ("BOOTSTRAP_REVIEW" if not require_ready else "PROJECT_READY")),
            "ok": not errors, "issues": errors, "paths": state.get("paths", {}),
            "baseline_sha": sha, "requires_approval": True}
