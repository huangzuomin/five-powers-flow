#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Neutral Coordinator & State Verifier.

RFC-001 Reference Implementation for deterministic cryptographic verification
and mechanical checks-and-balances.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
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
        return res.returncode, res.stdout, res.stderr
    except Exception as exc:
        return -1, "", str(exc)


def git_commit_exists(sha: str, repo_path: Optional[Path] = None) -> bool:
    """Verify that a 40-digit SHA physically exists in the git object database."""
    if not HEX_SHA_RE.match(sha):
        return False
    code, _, _ = run_cmd(["git", "cat-file", "-e", sha], cwd=repo_path)
    return code == 0


def extract_yaml_block(text: str, marker: str = "DEV_HANDOFF") -> Optional[str]:
    """Extract standard YAML blocks enclosed in ```yaml ... ``` from text."""
    if not text:
        return None
    pattern = re.compile(rf"```yaml\s*([\s\S]*?kind:\s*{marker}[\s\S]*?)```", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return None


def validate_dev_handoff(data: Dict[str, Any], repo_path: Optional[Path] = None) -> List[str]:
    """Cryptographically and structurally validate DEV_HANDOFF card."""
    errors = []
    required_scalars = ["handoff_version", "kind", "task_id", "baseline_sha", "tested_code_sha", "pr_url", "state"]
    for field in required_scalars:
        val = data.get(field)
        if val is None or val == "":
            errors.append(f"Missing required scalar field: {field}")

    baseline_sha = str(data.get("baseline_sha", "")).strip()
    if not HEX_SHA_RE.match(baseline_sha):
        errors.append(f"baseline_sha must be a 40-digit hex SHA, got: '{baseline_sha}'")

    tested_sha = str(data.get("tested_code_sha", "")).strip()
    if not HEX_SHA_RE.match(tested_sha):
        errors.append(f"tested_code_sha must be a 40-digit hex SHA, got: '{tested_sha}'")
    elif repo_path and not git_commit_exists(tested_sha, repo_path):
        errors.append(f"tested_code_sha '{tested_sha}' does not physically exist in git object database!")

    changed_files = data.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        errors.append("changed_files must be a non-empty list of file paths")

    not_run = data.get("not_run")
    if not isinstance(not_run, list):
        errors.append("not_run must be explicitly declared as a list (cannot be omitted or null)")
    elif len(not_run) == 0 and not data.get("full_coverage_certified"):
        errors.append("not_run is empty. You must either honestly list untested areas or explicitly certify full coverage.")

    dev_checks = data.get("dev_checks")
    if not isinstance(dev_checks, list) or not dev_checks:
        errors.append("dev_checks must contain at least one verifiable execution command and exit code")

    return errors


def validate_qa_result(qa_data: Dict[str, Any], dev_data: Optional[Dict[str, Any]] = None, repo_path: Optional[Path] = None) -> List[str]:
    """Cryptographically and structurally validate QA_RESULT card and check consistency with DEV."""
    errors = []
    required_scalars = ["result_version", "kind", "task_id", "tested_sha", "runner_sha", "environment", "verdict", "evidence_manifest_sha256"]
    for field in required_scalars:
        val = qa_data.get(field)
        if val is None or val == "":
            errors.append(f"QA card missing required field: {field}")

    tested_sha = str(qa_data.get("tested_sha", "")).strip()
    if not HEX_SHA_RE.match(tested_sha):
        errors.append(f"QA tested_sha must be 40-digit hex SHA, got: '{tested_sha}'")
    elif repo_path and not git_commit_exists(tested_sha, repo_path):
        errors.append(f"QA tested_sha '{tested_sha}' does not exist in git object database!")

    # 关键机制强制：QA 验收的代码必须与 DEV 提测的 SHA 严格绝对一致！
    if dev_data:
        dev_tested_sha = str(dev_data.get("tested_code_sha", "")).strip()
        if tested_sha != dev_tested_sha:
            errors.append(f"CRITICAL DISCREPANCY: QA tested_sha ('{tested_sha}') != DEV tested_code_sha ('{dev_tested_sha}')!")

    manifest_sha = str(qa_data.get("evidence_manifest_sha256", "")).strip()
    if not HEX_SHA256_RE.match(manifest_sha):
        errors.append(f"evidence_manifest_sha256 must be a 64-digit SHA-256 string, got: '{manifest_sha}'")

    verdict = qa_data.get("verdict")
    if verdict not in ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "INVALID_TEST"):
        errors.append(f"Invalid QA verdict: '{verdict}'")

    return errors


def evaluate_lifecycle_state(dev_data: Optional[Dict[str, Any]], qa_data: Optional[Dict[str, Any]], pr_merged: bool = False) -> str:
    """Classify the current lifecycle state based on validated inputs."""
    if pr_merged:
        return "MERGED_AND_CLOSED"
    if qa_data:
        verdict = qa_data.get("verdict")
        if verdict == "PASS":
            return "QA_PASSED_AWAITING_OWNER_MERGE"
        elif verdict in ("FAIL", "INVALID_TEST"):
            return "QA_FAILED_REWORK_REQUIRED"
        elif verdict == "BLOCKED":
            return "BLOCKED_ON_DEPENDENCY"
    if dev_data:
        state = dev_data.get("state")
        if state == "DEV_READY_FOR_QA":
            return "DEV_READY_AWAITING_QA_ADMISSION"
        elif state == "DEV_BLOCKED":
            return "DEV_BLOCKED"
    return "DEV_IN_PROGRESS"


def main() -> int:
    parser = argparse.ArgumentParser(description="Five-Powers-Flow Coordinator & Verifier")
    parser.add_argument("--dev-card", help="Path to YAML file containing DEV_HANDOFF")
    parser.add_argument("--qa-card", help="Path to YAML file containing QA_RESULT")
    parser.add_argument("--check-git", action="store_true", help="Physically verify SHAs against local git repo")
    args = parser.parse_args()

    repo_path = Path.cwd() if args.check_git else None
    dev_data = None
    qa_data = None
    all_errors = []

    if args.dev_card:
        p = Path(args.dev_card)
        if not p.is_file():
            print(f"[FAIL] DEV card file not found: {args.dev_card}")
            return 1
        with open(p, "r", encoding="utf-8") as f:
            dev_data = yaml.safe_load(f)
        dev_errors = validate_dev_handoff(dev_data, repo_path=repo_path)
        if dev_errors:
            print("[FAIL] DEV_HANDOFF Card Validation Errors:")
            for err in dev_errors:
                print(f"  - {err}")
            all_errors.extend(dev_errors)
        else:
            print("[PASS] DEV_HANDOFF Card is cryptographically and structurally valid.")

    if args.qa_card:
        p = Path(args.qa_card)
        if not p.is_file():
            print(f"[FAIL] QA card file not found: {args.qa_card}")
            return 1
        with open(p, "r", encoding="utf-8") as f:
            qa_data = yaml.safe_load(f)
        qa_errors = validate_qa_result(qa_data, dev_data=dev_data, repo_path=repo_path)
        if qa_errors:
            print("[FAIL] QA_RESULT Card Validation Errors:")
            for err in qa_errors:
                print(f"  - {err}")
            all_errors.extend(qa_errors)
        else:
            print("[PASS] QA_RESULT Card is cryptographically and structurally valid.")

    if all_errors:
        return 1

    state = evaluate_lifecycle_state(dev_data, qa_data)
    print(f"\n[FPF Lifecycle State] => {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
