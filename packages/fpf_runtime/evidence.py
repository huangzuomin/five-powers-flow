"""Provisional local QA evidence; this does not authenticate an independent QA principal."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def write_qa_evidence(root: Path, task: str, sha: str,
                      reviewer_output: str, command: list[str],
                      check_exit: int, check_output: str) -> tuple[str, str]:
    target = (root / task / sha).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Evidence directory escape")
    target.mkdir(parents=True, exist_ok=True)
    items = []
    for name, payload in {
        "review.txt": reviewer_output.encode("utf-8"),
        "check.log": check_output.encode("utf-8"),
    }.items():
        (target / name).write_bytes(payload)
        items.append({"path": name, "sha256": _digest(payload)})
    manifest = {
        "kind": "FPF_LOCAL_QA_EVIDENCE",
        "authority": "local provisional, NOT GitHub CI-attested",
        "task_id": task, "tested_sha": sha,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "qa_check_command": command, "qa_check_exit_code": check_exit,
        "items": items,
    }
    raw = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    path = target / "manifest.json"
    path.write_bytes(raw)
    return str(path), _digest(raw)

def verify_qa_evidence(path: str, claimed: str, sha: str) -> bool:
    try:
        p = Path(path).resolve()
        raw = p.read_bytes()
        if _digest(raw) != claimed:
            return False
        manifest = json.loads(raw)
        if (manifest["kind"] != "FPF_LOCAL_QA_EVIDENCE" or
                manifest["tested_sha"] != sha or
                manifest["qa_check_exit_code"] != 0):
            return False
        items = manifest["items"]
        if len(items) < 2:
            return False
        for item in items:
            f = (p.parent / item["path"]).resolve()
            if not f.is_relative_to(p.parent) or not f.is_file():
                return False
            if _digest(f.read_bytes()) != item["sha256"]:
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False
