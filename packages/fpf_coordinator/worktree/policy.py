# -*- coding: utf-8 -*-
"""Worktree reclamation policy.

The policy is a data file (``.fpf/worktree-policy.yaml`` -- protected path) so
that changing what may be deleted is itself a governed change.  Missing file
does not mean "no policy": the defaults below are the frozen v8 values, and a
scan reports which source it used.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

POLICY_PATH = ".fpf/worktree-policy.yaml"
DEFAULT_ALLOWLIST = (".fpf-worktree.json", ".fpf-runtime/")


@dataclass(frozen=True)
class Policy:
    worktree_root: str = "_worktrees"
    archive_root: str = "_reclaim-archive"
    allowlist: tuple[str, ...] = DEFAULT_ALLOWLIST
    reclaim_grace_days: int = 3
    ledger_freshness_hours: int = 24
    ttl_default_days: int = 14
    source: str = "defaults"
    path: str | None = None

    def sha256(self) -> str:
        body = {
            "worktree_root": self.worktree_root,
            "archive_root": self.archive_root,
            "allowlist": list(self.allowlist),
            "reclaim_grace_days": self.reclaim_grace_days,
            "ledger_freshness_hours": self.ledger_freshness_hours,
            "ttl_default_days": self.ttl_default_days,
        }
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def allowed(relpath: str, policy: Policy) -> bool:
    rel = relpath.replace("\\", "/")
    for entry in policy.allowlist:
        if rel == entry or rel.startswith(entry):
            return True
    return False


def load(repo) -> Policy:
    path = Path(repo) / POLICY_PATH
    if not path.is_file():
        return Policy()
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover - PyYAML is present in this image
        return Policy(source="defaults-yaml-unavailable", path=str(path))
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Policy(
        worktree_root=str(data.get("worktree_root", Policy.worktree_root)),
        archive_root=str(data.get("archive_root", Policy.archive_root)),
        allowlist=tuple(data.get("allowlist", DEFAULT_ALLOWLIST)),
        reclaim_grace_days=int(data.get("reclaim_grace_days", 3)),
        ledger_freshness_hours=int(data.get("ledger_freshness_hours", 24)),
        ttl_default_days=int(data.get("ttl_default_days", 14)),
        source="file",
        path=str(path),
    )
