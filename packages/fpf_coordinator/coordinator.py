#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Neutral Coordinator & Trusted Evaluator.

RFC-001 v1.1 Implementation:
1. Cryptographic Git Commit Verification (git cat-file -t == 'commit')
2. Two-Way Handshake Enforcement (DEV.tested_code_sha == QA.tested_sha)
3. Computed Verdict (Never blindly trust claimed PASS; evaluate real checks & p0 findings)
4. Local Manifest SHA-256 Recalculation (Anti-tamper evidence auditing)
5. Strict Fail-Closed Boundaries
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

import yaml

HEX_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
HEX_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 15) -> Tuple[int, str, str]:
    """Execute subprocess safely returning (exit_code, stdout, stderr)."""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd or Path.cwd()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


def git_is_commit_object(sha: str, repo_path: Optional[Path] = None) -> bool:
    """Verify that a 40-digit SHA physically exists AND is strictly a 'commit' object."""
    if not HEX_SHA_RE.match(sha):
        return False
    # P0-04 Fix: Must check object TYPE, not just existence (-e allows blob/tree)
    code, stdout, _ = run_cmd(["git", "cat-file", "-t", sha], cwd=repo_path)
    return code == 0 and stdout == "commit"


def recalculate_manifest_sha256(manifest_path: Path) -> Tuple[bool, str]:
    """Physically read evidence manifest and recompute its SHA-256 hash."""
    if not manifest_path.is_file():
        return False, f"Manifest file does not exist at {manifest_path}"
    try:
        hasher = hashlib.sha256()
        with open(manifest_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return True, hasher.hexdigest().lower()
    except Exception as exc:
        return False, str(exc)


def validate_dev_handoff(data: Dict[str, Any], repo_path: Optional[Path] = None) -> List[str]:
    """Cryptographically and structurally validate DEV_HANDOFF card."""
    errors = []
    required_scalars = ["handoff_version", "kind", "task_id", "baseline_sha", "tested_code_sha", "pr_url", "state"]
    for field in required_scalars:
        val = data.get(field)
        if val is None or val == "":
            errors.append(f"DEV card missing required scalar field: '{field}'")

    baseline_sha = str(data.get("baseline_sha", "")).strip()
    if not HEX_SHA_RE.match(baseline_sha):
        errors.append(f"baseline_sha must be a 40-digit hex SHA, got: '{baseline_sha}'")

    tested_sha = str(data.get("tested_code_sha", "")).strip()
    if not HEX_SHA_RE.match(tested_sha):
        errors.append(f"tested_code_sha must be a 40-digit hex SHA, got: '{tested_sha}'")
    elif repo_path and not git_is_commit_object(tested_sha, repo_path):
        errors.append(f"tested_code_sha '{tested_sha}' is NOT a valid commit object in git repository!")

    changed_files = data.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        errors.append("changed_files must be a non-empty list of file paths")

    not_run = data.get("not_run")
    if not isinstance(not_run, list):
        errors.append("not_run must be explicitly declared as a list")
    elif len(not_run) == 0 and not data.get("full_coverage_certified"):
        errors.append("not_run cannot be an empty list without explicit 'full_coverage_certified: true'")

    dev_checks = data.get("dev_checks")
    if not isinstance(dev_checks, list) or not dev_checks:
        errors.append("dev_checks must contain at least one verifiable execution check")

    return errors


def validate_qa_result(
    qa_data: Dict[str, Any],
    dev_data: Optional[Dict[str, Any]] = None,
    repo_path: Optional[Path] = None,
    evidence_manifest_path: Optional[Path] = None,
) -> List[str]:
    """Cryptographically validate QA_RESULT card and enforce verification against DEV."""
    errors = []
    required_scalars = [
        "result_version",
        "kind",
        "task_id",
        "tested_sha",
        "runner_sha",
        "environment",
        "verdict",
        "checks",
        "evidence_manifest_sha256",
    ]
    for field in required_scalars:
        val = qa_data.get(field)
        if val is None or val == "":
            errors.append(f"QA card missing required field: '{field}'")

    tested_sha = str(qa_data.get("tested_sha", "")).strip()
    if not HEX_SHA_RE.match(tested_sha):
        errors.append(f"QA tested_sha must be 40-digit hex SHA, got: '{tested_sha}'")
    elif repo_path and not git_is_commit_object(tested_sha, repo_path):
        errors.append(f"QA tested_sha '{tested_sha}' is NOT a valid commit object in git repository!")

    # P0-03 & P0-04 Fix: 强制两两对齐，绝不允许凭空接受 QA 卡
    if dev_data:
        dev_tested_sha = str(dev_data.get("tested_code_sha", "")).strip()
        if tested_sha != dev_tested_sha:
            errors.append(f"CRITICAL DISCREPANCY: QA tested_sha ('{tested_sha}') != DEV tested_code_sha ('{dev_tested_sha}')!")
    else:
        errors.append("CRITICAL: QA_RESULT cannot be validated in isolation without matching DEV_HANDOFF!")

    # P0-04 Fix: 真实读取物理文件并重新计算 SHA-256，而不是光看字符串
    claimed_manifest_sha = str(qa_data.get("evidence_manifest_sha256", "")).strip().lower()
    if not HEX_SHA256_RE.match(claimed_manifest_sha):
        errors.append(f"evidence_manifest_sha256 must be a 64-digit hex string, got: '{claimed_manifest_sha}'")
    elif evidence_manifest_path:
        ok, recomputed_sha = recalculate_manifest_sha256(evidence_manifest_path)
        if not ok:
            errors.append(f"Failed to read evidence manifest for hash verification: {recomputed_sha}")
        elif recomputed_sha != claimed_manifest_sha:
            errors.append(
                f"MANIFEST HASH MISMATCH! Claimed: '{claimed_manifest_sha}', Recomputed from disk: '{recomputed_sha}'"
            )

    # P0-03 Fix: 检查 checks 实际执行项
    checks = qa_data.get("checks")
    if not isinstance(checks, list) or len(checks) == 0:
        errors.append("QA card must include at least one executed check item in 'checks'")

    # P0-03 Fix: 检查是否有未解决的 P0 级严重缺陷，有则严禁标 PASS
    findings = qa_data.get("findings", {})
    if isinstance(findings, dict):
        p0_findings = findings.get("p0", [])
        if isinstance(p0_findings, list) and len(p0_findings) > 0 and qa_data.get("verdict") == "PASS":
            errors.append(f"CRITICAL REJECTION: QA card claims PASS but contains unresolved P0 findings: {p0_findings}")

    verdict = qa_data.get("verdict")
    if verdict not in ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "INVALID_TEST"):
        errors.append(f"Invalid QA verdict value: '{verdict}'")

    return errors


def compute_lifecycle_state(
    dev_data: Optional[Dict[str, Any]],
    qa_data: Optional[Dict[str, Any]],
    dev_errors: List[str],
    qa_errors: List[str],
    pr_merged: bool = False,
) -> Tuple[str, str]:
    """Compute (not blindly trust) the authoritative lifecycle state."""
    if pr_merged:
        return "MERGED_AND_CLOSED", "PR is confirmed merged in repository."

    if dev_errors:
        return "DEV_REJECTED", f"DEV_HANDOFF failed validation with {len(dev_errors)} error(s)."

    if qa_data:
        if qa_errors:
            return "QA_REJECTED", f"QA_RESULT failed verification with {len(qa_errors)} error(s). Marked INVALID_TEST."
        verdict = qa_data.get("verdict")
        if verdict == "PASS":
            return "QA_PASSED_AWAITING_OWNER_MERGE", "QA verified and passed. Awaiting human sovereign merge decision."
        elif verdict in ("FAIL", "INVALID_TEST"):
            return "QA_FAILED_REWORK_REQUIRED", f"QA reported {verdict}. Rework required by DEV."
        elif verdict == "BLOCKED":
            return "BLOCKED_ON_DEPENDENCY", "QA reported testing is blocked on external dependencies."

    if dev_data:
        state = dev_data.get("state")
        if state == "DEV_READY_FOR_QA":
            return "DEV_READY_AWAITING_QA_ADMISSION", "DEV hand-off is valid. Ready for QA admission review."
        elif state == "DEV_BLOCKED":
            return "DEV_BLOCKED", "DEV reported work is blocked."

    return "DEV_IN_PROGRESS", "Development in progress."


def main() -> int:
    parser = argparse.ArgumentParser(description="Five-Powers-Flow Trusted Evaluator & Coordinator")
    parser.add_argument("--dev-card", help="Path to YAML file containing DEV_HANDOFF")
    parser.add_argument("--qa-card", help="Path to YAML file containing QA_RESULT")
    parser.add_argument("--manifest", help="Path to physical evidence manifest.json to verify SHA-256")
    parser.add_argument("--check-git", action="store_true", help="Physically verify commit objects in local git tree")
    args = parser.parse_args()

    repo_path = Path.cwd() if args.check_git else None
    dev_data = None
    qa_data = None
    dev_errors = []
    qa_errors = []

    print("=== [FPF Trusted Evaluator Engine v1.1] ===\n")

    if args.dev_card:
        p = Path(args.dev_card)
        if not p.is_file():
            print(f"[FAIL] DEV card file not found: {args.dev_card}")
            return 1
        with open(p, "r", encoding="utf-8") as f:
            dev_data = yaml.safe_load(f)
        dev_errors = validate_dev_handoff(dev_data, repo_path=repo_path)
        if dev_errors:
            print("[FAIL] DEV_HANDOFF Validation Failures:")
            for e in dev_errors:
                print(f"  - {e}")
        else:
            print("[PASS] DEV_HANDOFF is cryptographically and structurally valid.")

    if args.qa_card:
        p = Path(args.qa_card)
        if not p.is_file():
            print(f"[FAIL] QA card file not found: {args.qa_card}")
            return 1
        with open(p, "r", encoding="utf-8") as f:
            qa_data = yaml.safe_load(f)
        manifest_p = Path(args.manifest) if args.manifest else None
        qa_errors = validate_qa_result(
            qa_data,
            dev_data=dev_data,
            repo_path=repo_path,
            evidence_manifest_path=manifest_p,
        )
        if qa_errors:
            print("[FAIL] QA_RESULT Verification Failures:")
            for e in qa_errors:
                print(f"  - {e}")
        else:
            print("[PASS] QA_RESULT is cryptographically and structurally valid.")

    state, reason = compute_lifecycle_state(dev_data, qa_data, dev_errors, qa_errors)
    print(f"\n[Computed Lifecycle State] => {state}")
    print(f"[Reason]                   => {reason}\n")

    if dev_errors or qa_errors:
        print("[FAIL] Lifecycle evaluation blocked on integrity errors.")
        return 1

    print("[SUCCESS] All evaluated checkpoints satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
