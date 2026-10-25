"""Canonical protected-path policy for FPF DEV code operations.

BOOTSTRAP_PR and explicitly authorized governance changes use a distinct
review path. DEV_CODE PRs and runtime Codex edits must not touch these paths.
"""
from __future__ import annotations
from pathlib import PurePosixPath

EXACT = frozenset({
    "agents.md", "project-map.md", "lessons.md",
    "docs/project-map.md", "docs/lessons.md",
    "docs/coordination/project-map.md",
    "docs/coordination/lessons.md",
    "docs/coordination/handoff-protocol.md",
    "handoff-protocol.md", ".claude/settings.json",
})
PREFIXES = (".github/", ".fpf/", "schemas/",
            "packages/fpf_policy/", "packages/fpf_coordinator/",
            "packages/fpf_gates/", "packages/fpf_bootstrap/",
            "packages/fpf_runtime/")

def normalize_repo_path(path: str) -> str:
    path = str(path).replace("\\", "/").strip().lower()
    # Git paths are relative; absolute paths are not allowed to silently escape.
    if not path or path.startswith("/") or ":" in path.split("/")[0] or "\x00" in path:
        raise ValueError("Not a repository-relative path: " + repr(path))
    parts = path.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError("Invalid repository path: " + repr(path))
    return "/".join(parts)

def is_protected(path: str) -> bool:
    normalized = normalize_repo_path(path)
    return normalized in EXACT or any(normalized.startswith(p) for p in PREFIXES)

def is_protected_tool_path(path: str) -> bool:
    """Paths supplied by CLI tools may be absolute; check known sensitive suffixes."""
    raw = str(path).replace("\\", "/").lower().strip()
    if not raw or "\x00" in raw or "/../" in raw:
        return True
    trimmed = raw.lstrip("./")
    if raw.startswith("/") or ":" in raw.split("/")[0]:
        if any(raw.endswith("/" + p) for p in EXACT):
            return True
        if any("/" + p in raw for p in PREFIXES):
            return True
        return False
    try:
        return is_protected(trimmed)
    except ValueError:
        return True
