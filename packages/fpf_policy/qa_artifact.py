"""Verify provenance of external FPF QA artifacts from a distinct GitHub actor.

Only GitHub Actions runs dispatched from a commit already in protected main,
by the same independently authenticated reviewer, may supply the artifact.
The artifact's manifest and all required EVID files are checked on disk.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
import zipfile
from typing import List

from packages.fpf_coordinator.coordinator import verify_evidence_directory

FORBIDDEN_DEV_QA_PATHS = (
    "qa-artifact",
    ".fpf-evidence",
    "qa-manifest.json",
    "qa-artifact.zip",
)


def verify_artifact_sha256(data: bytes, expected_digest: str) -> None:
    """Cryptographically verify that artifact payload matches claimed digest."""
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", expected_digest):
        raise ValueError("GitHub artifact digest missing or invalid; refusing unbound bytes")
    computed = hashlib.sha256(data).hexdigest()
    if computed != expected_digest[7:].lower():
        raise ValueError(
            f"GitHub-provided artifact digest does not match ZIP! Expected {expected_digest[7:].lower()}, computed {computed}"
        )


def check_dev_branch_decoupling(repository_dir: Path) -> List[str]:
    """Verify that candidate DEV PR workspace contains zero smuggled or inlined QA artifacts."""
    violations = []
    for pattern in FORBIDDEN_DEV_QA_PATHS:
        target = repository_dir / pattern
        if target.exists():
            violations.append(f"Inlined QA evidence found in candidate workspace: {pattern}")
    return violations


def api_json(repo: str, endpoint: str, token: str) -> dict:
    if not token:
        raise ValueError("Missing GitHub token for independent QA proof")
    url = f"https://api.github.com/repos/{repo}/{endpoint}"
    request = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
    })
    with urlopen(request, timeout=30) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("Unexpected GitHub API response")
    return value


class _NoAuthRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req:
            new_req.headers = {k: v for k, v in new_req.headers.items() if k.lower() != "authorization"}
            new_req.unredirected_hdrs = {k: v for k, v in new_req.unredirected_hdrs.items() if k.lower() != "authorization"}
        return new_req


def download_zip(repo: str, artifact_id: int, token: str) -> bytes:
    opener = build_opener(_NoAuthRedirectHandler)
    request = Request(
        f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip",
        headers={"Authorization": "Bearer " + token},
    )
    with opener.open(request, timeout=60) as response:
        content = response.read(25 * 1024 * 1024 + 1)
    if len(content) > 25 * 1024 * 1024:
        raise ValueError("QA artifact archive exceeds size limit")
    return content


def ancestor(commit: str, base_ref: str, cwd: Path) -> bool:
    if not re.fullmatch(r"[a-fA-F0-9]{40}", commit):
        return False
    for ref in (base_ref, f"origin/{base_ref}", f"refs/remotes/origin/{base_ref}"):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, ref],
            cwd=cwd, capture_output=True, timeout=30,
        ).returncode == 0:
            return True
    return False


@contextmanager
def independent_qa_evidence(*, repo: str, qa: dict, reviewer: str,
                             tested_sha: str, task_id: str, token: str,
                             repository_dir: Path):
    """Yield verified physical files from a GitHub artifact, never DEV checkout."""
    decoupling_errors = check_dev_branch_decoupling(repository_dir)
    if decoupling_errors:
        raise ValueError("QA decoupling violation: " + "; ".join(decoupling_errors))

    try:
        run_id = int(qa["qa_run_id"])
        artifact_id = int(qa["qa_artifact_id"])
    except (ValueError, TypeError, KeyError):
        raise ValueError("QA_RESULT must include numeric qa_run_id and qa_artifact_id")
    if run_id <= 0 or artifact_id <= 0:
        raise ValueError("QA run / artifact IDs must be positive")
    run = api_json(repo, f"actions/runs/{run_id}", token)
    if run.get("conclusion") != "success" or run.get("status") != "completed":
        raise ValueError("Independent QA Actions run did not succeed")
    if run.get("event") != "workflow_dispatch":
        raise ValueError("Independent QA must use an explicitly dispatched workflow")
    if str((run.get("actor") or {}).get("login", "")).casefold() != reviewer.casefold():
        raise ValueError("QA run actor differs from authenticated PR reviewer")
    if str((run.get("triggering_actor") or {}).get("login", reviewer)).casefold() != reviewer.casefold():
        raise ValueError("QA run was re-run by another identity")
    workflow_path = str(run.get("path") or "")
    if not (workflow_path == ".github/workflows/fpf-independent-qa.yml" or
            workflow_path.endswith("/.github/workflows/fpf-independent-qa.yml")):
        raise ValueError("QA run did not come from a designated independent QA workflow")
    if not ancestor(str(run.get("head_sha") or ""), "main", repository_dir):
        raise ValueError("QA workflow commit is not on trusted main")
    artifact = api_json(repo, f"actions/artifacts/{artifact_id}", token)
    expected_name = "fpf-qa-" + tested_sha.lower()
    if (artifact.get("expired") is not False or
        artifact.get("name") != expected_name or
        int((artifact.get("workflow_run") or {}).get("id") or -1) != run_id):
        raise ValueError("Artifact identity, lifetime or SHA-specific name mismatch")
    data = download_zip(repo, artifact_id, token)
    digest = str(artifact.get("digest") or "")
    verify_artifact_sha256(data, digest)
    with tempfile.TemporaryDirectory(prefix="fpf-independent-qa-") as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            members = archive.infolist()
            if len(members) > 60:
                raise ValueError("Too many QA evidence files")
            total = 0
            for item in members:
                name = item.filename
                if (item.is_dir() or "/" in name or "\\" in name or name in (".", "..")
                        or item.file_size > 10 * 1024 * 1024):
                    raise ValueError("Invalid QA artifact ZIP member")
                total += item.file_size
                if total > 30 * 1024 * 1024:
                    raise ValueError("Expanded QA artifact is too large")
                with archive.open(item) as member:
                    payload = member.read(10 * 1024 * 1024 + 1)
                if len(payload) > 10 * 1024 * 1024 or len(payload) != item.file_size:
                    raise ValueError("QA artifact ZIP member expanded beyond allowed size")
                (root / name).write_bytes(payload)
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError("QA ZIP missing manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest.get("task_id") != task_id or
                manifest.get("tested_sha") != tested_sha):
            raise ValueError("QA manifest is not bound to the actual task and PR head")
        claimed = str(qa.get("evidence_manifest_sha256") or "").lower()
        errors = verify_evidence_directory(root, claimed,
                                            profile=qa.get("profile"))
        if errors:
            raise ValueError("Rejected independent QA manifest: " + "; ".join(errors))
        yield root
