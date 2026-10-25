"""Strict bridge from externally produced QA files to FPF evidence profile.

This adapter does NOT manufacture missing EVIDs, invent exit codes, or sign
QA_RESULT. It is useful only after an independently run QA job has physically
produced every required item. Source identity still needs server attestation.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
from packages.fpf_coordinator.coordinator import (
    REQUIRED_PROFILE_EVIDENCES, normalize_profile, verify_evidence_directory,
)

def export_fpf_manifest(outside_dev: Path, files_by_evid: dict[str, Path],
                        *, task_id: str, profile: str) -> tuple[str, str]:
    profile = normalize_profile(profile)
    root = outside_dev.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not task_id or "/" in task_id or "\\" in task_id:
        raise ValueError("Invalid task ID")
    mandatory = set(REQUIRED_PROFILE_EVIDENCES[profile])
    if not mandatory.issubset(files_by_evid):
        raise ValueError("QA runner did not produce required EVIDs: " +
                         str(sorted(mandatory - set(files_by_evid))))
    entries = []
    for evid_id, source in sorted(files_by_evid.items()):
        src = Path(source).resolve()
        if not src.is_file() or src.is_symlink():
            raise ValueError("Missing/non-regular QA source evidence: " + str(source))
        dest = root / (evid_id + src.suffix)
        if dest.exists():
            raise ValueError("Refusing to overwrite existing evidence: " + str(dest))
        # Real binary evidence, e.g. browser screenshots, is preserved byte for byte.
        shutil.copyfile(src, dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        entries.append({"id": evid_id, "path": dest.name,
                        "sha256": digest, "status": "PASS"})
    manifest = {"manifest_version": 1, "task_id": task_id,
                "profile": profile, "items": entries}
    path = root / "manifest.json"
    if path.exists():
        raise ValueError("Refusing to overwrite existing manifest")
    data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(data)
    claimed = hashlib.sha256(data).hexdigest()
    errors = verify_evidence_directory(root, claimed, profile)
    if errors:
        path.unlink(missing_ok=True)
        raise ValueError("Coordinator rejected exported evidence: " + "; ".join(errors))
    return str(path), claimed
