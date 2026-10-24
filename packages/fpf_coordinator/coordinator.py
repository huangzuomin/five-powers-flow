#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Neutral Coordinator & Trusted Evaluator.

RFC-001 v1.2.1 Hardened Reference Implementation:
- Cryptographic Git Commit Verification (git cat-file -t == 'commit')
- Strict Ancestor Check (baseline_sha is ancestor of tested_code_sha)
- Accurate Change Scope Audit (changed_files contains all actual diff files)
- Two-Way Handshake Enforcement (DEV.tested_code_sha == QA.tested_sha)
- Two-Way QA Toolchain Verification (runner_sha & qa_contract_sha must be valid commits)
- Anti-Cheat not_run / Exemption Matrix Enforcement
- Evidence Profile Enforcement (Profile-specific mandatory evidence verification)
- Checks Exit Code Verification (PASS requires exit_code == 0 on all executed checks)
- Disk-backed Manifest & Item SHA-256 Recalculation (Mandatory for verdict: PASS)
- Fail-Closed State Machine & Cryptographic Merge Ancestry Verification
- Automated Extraction from PR/Issue bodies (extract_yaml_block active)
"""
from __future__ import annotations

import argparse
import hashlib
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

REQUIRED_PROFILE_EVIDENCES: Dict[str, List[str]] = {
    "Library": ["EVID-01", "EVID-04", "EVID-09"],
    "API-DB": ["EVID-01", "EVID-02", "EVID-04", "EVID-05", "EVID-09"],
    "Full-Stack": ["EVID-01", "EVID-02", "EVID-03", "EVID-04", "EVID-09"],
    "Rework": ["EVID-01", "EVID-04", "EVID-09", "EVID-25"],
}


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


def verify_github_pr_merge(pr_identifier: str, repo_path: Optional[Path] = None) -> Tuple[bool, str, str]:
    """Query GitHub API/CLI to verify that PR was legitimately merged on server."""
    code, stdout, stderr = run_cmd(["gh", "pr", "view", str(pr_identifier), "--json", "state,mergedAt,mergeCommit"], cwd=repo_path)
    if code != 0:
        return False, "", f"Failed to query GitHub CLI for PR '{pr_identifier}': {stderr}"
    try:
        data = json.loads(stdout)
        state = str(data.get("state", "")).upper()
        if state != "MERGED":
            return False, "", f"GitHub reports PR '{pr_identifier}' state is '{state}', expected 'MERGED'."
        merge_commit = data.get("mergeCommit", {})
        merge_sha = merge_commit.get("oid") if isinstance(merge_commit, dict) else ""
        return True, str(merge_sha or ""), f"Confirmed merged at {data.get('mergedAt')}"
    except Exception as exc:
        return False, "", f"Failed to parse GitHub CLI response: {exc}"


def git_is_commit_object(sha: str, repo_path: Optional[Path] = None) -> bool:
    """Verify that a 40-digit SHA physically exists AND is strictly a 'commit' object."""
    if not HEX_SHA_RE.match(sha):
        return False
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


def verify_evidence_directory(
    evidence_dir: Path,
    claimed_manifest_sha: str,
    profile: Optional[str] = "Library",
) -> List[str]:
    """Verify manifest file SHA-256, all individual EVID items, and profile coverage."""
    errors = []
    manifest_p = evidence_dir / "manifest.json"
    if not manifest_p.is_file():
        return [f"Evidence manifest missing: {manifest_p}"]

    ok, actual_sha = recalculate_manifest_sha256(manifest_p)
    if not ok:
        return [f"Cannot read manifest file: {actual_sha}"]
    if actual_sha != claimed_manifest_sha.lower():
        errors.append(
            f"MANIFEST HASH MISMATCH! Claimed: '{claimed_manifest_sha}', Recomputed: '{actual_sha}'"
        )
        return errors

    try:
        manifest_data = json.loads(manifest_p.read_text(encoding="utf-8"))
        items = manifest_data.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            errors.append("Evidence manifest.json 'items' list cannot be empty! Zero evidence items cannot substantiate QA.")
            return errors

        # Validate manifest.json against schemas/manifest.schema.json if available
        schema_path = Path(__file__).resolve().parent.parent.parent / "schemas" / "manifest.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema
                schema_doc = json.loads(schema_path.read_text(encoding="utf-8"))
                jsonschema.Draft7Validator(schema_doc).validate(manifest_data)
            except Exception as s_exc:
                errors.append(f"manifest.json violates schemas/manifest.schema.json: {s_exc}")

        target_profile = str(profile or "Library").strip()
        if target_profile not in REQUIRED_PROFILE_EVIDENCES:
            target_profile = "Library"

        required_evids = REQUIRED_PROFILE_EVIDENCES[target_profile]
        declared_evid_ids = set()

        for item in items:
            evid_id = str(item.get("id", "UNKNOWN")).strip()
            declared_evid_ids.add(evid_id)
            status = str(item.get("status", "PASS")).upper()
            if status == "NOT_APPLICABLE":
                reason = str(item.get("reason", "")).strip()
                if len(reason) < 10:
                    errors.append(f"{evid_id}: NOT_APPLICABLE status requires architectural justification in 'reason' (min 10 chars)")
                continue

            rel_path = item.get("path")
            expected_sha = item.get("sha256")
            if not rel_path or not expected_sha:
                errors.append(f"{evid_id}: Manifest item missing 'path' or 'sha256'")
                continue
            item_file = evidence_dir / rel_path
            if not item_file.is_file():
                errors.append(f"{evid_id}: Missing physical evidence file '{rel_path}'")
                continue
            item_hash = hashlib.sha256(item_file.read_bytes()).hexdigest().lower()
            if item_hash != str(expected_sha).lower():
                errors.append(
                    f"{evid_id}: Evidence SHA-256 mismatch for '{rel_path}'. Declared: {expected_sha}, Actual: {item_hash}"
                )

        missing_profile_evids = set(required_evids) - declared_evid_ids
        if missing_profile_evids:
            errors.append(
                f"Evidence manifest for profile '{target_profile}' omitted mandatory evidence items: {sorted(missing_profile_evids)}"
            )
    except Exception as exc:
        errors.append(f"Failed to parse or verify manifest.json: {exc}")

    return errors


def extract_yaml_block(text: str, marker: str = "DEV_HANDOFF") -> str:
    """Extract standard YAML blocks enclosed in ```yaml ... ``` from text."""
    if not text:
        return ""
    pattern = re.compile(rf"```ya?ml\s*([\s\S]*?kind:\s*{marker}[\s\S]*?)```", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return ""


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
    elif repo_path and not git_is_commit_object(baseline_sha, repo_path):
        errors.append(f"baseline_sha '{baseline_sha}' is NOT a valid commit object in git repository!")

    tested_sha = str(data.get("tested_code_sha", "")).strip()
    if not HEX_SHA_RE.match(tested_sha):
        errors.append(f"tested_code_sha must be a 40-digit hex SHA, got: '{tested_sha}'")
    elif repo_path and not git_is_commit_object(tested_sha, repo_path):
        errors.append(f"tested_code_sha '{tested_sha}' is NOT a valid commit object in git repository!")

    if repo_path and HEX_SHA_RE.match(baseline_sha) and HEX_SHA_RE.match(tested_sha):
        if git_is_commit_object(baseline_sha, repo_path) and git_is_commit_object(tested_sha, repo_path):
            code, _, _ = run_cmd(["git", "merge-base", "--is-ancestor", baseline_sha, tested_sha], cwd=repo_path)
            if code != 0:
                errors.append(f"baseline_sha ({baseline_sha}) is NOT an ancestor of tested_code_sha ({tested_sha})!")

            diff_code, diff_out, _ = run_cmd(["git", "diff", "--name-only", f"{baseline_sha}..{tested_sha}"], cwd=repo_path)
            if diff_code == 0:
                actual_diff_files = set(f.strip() for f in diff_out.splitlines() if f.strip())
                declared_files = set(str(f).strip() for f in data.get("changed_files", []))
                missing_files = actual_diff_files - declared_files
                if missing_files:
                    errors.append(f"changed_files omitted {len(missing_files)} actual diff file(s): {sorted(missing_files)[:5]}")

    changed_files = data.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        errors.append("changed_files must be a non-empty list of file paths")

    # P2-1 Fix: not_run 必须为列表；若为空，则必须提供详细的 not_run_exemption_justification
    not_run = data.get("not_run")
    not_run_exemption = str(data.get("not_run_exemption_justification", "")).strip()
    if not isinstance(not_run, list):
        errors.append("not_run must be explicitly declared as a list of untested areas/boundaries")
    elif len(not_run) == 0:
        if len(not_run_exemption) < 15:
            errors.append(
                "not_run is empty. Under FPF anti-deception rules, if claiming 100% boundary testing with zero untested areas, "
                "you must provide an explicit 'not_run_exemption_justification' (minimum 15 characters) citing test matrix / scope evidence."
            )

    dev_checks = data.get("dev_checks")
    if not isinstance(dev_checks, list) or not dev_checks:
        errors.append("dev_checks must contain at least one verifiable execution check")

    return errors


def validate_qa_result(
    qa_data: Dict[str, Any],
    dev_data: Optional[Dict[str, Any]] = None,
    repo_path: Optional[Path] = None,
    evidence_dir: Optional[Path] = None,
) -> List[str]:
    """Cryptographically validate QA_RESULT card and enforce verification against DEV."""
    errors = []
    required_scalars = [
        "result_version",
        "kind",
        "task_id",
        "tested_sha",
        "runner_sha",
        "qa_contract_sha",
        "environment",
        "verdict",
        "checks",
        "evidence_manifest_sha256",
    ]
    for field in required_scalars:
        val = qa_data.get(field)
        if val is None or str(val).strip() == "":
            errors.append(f"QA card missing required field: '{field}'")

    tested_sha = str(qa_data.get("tested_sha", "")).strip()
    if not HEX_SHA_RE.match(tested_sha):
        errors.append(f"QA tested_sha must be 40-digit hex SHA, got: '{tested_sha}'")
    elif repo_path and not git_is_commit_object(tested_sha, repo_path):
        errors.append(f"QA tested_sha '{tested_sha}' is NOT a valid commit object in git repository!")

    runner_sha = str(qa_data.get("runner_sha", "")).strip()
    if not HEX_SHA_RE.match(runner_sha):
        errors.append(f"runner_sha must be a 40-digit hex SHA, got: '{runner_sha}'")
    elif repo_path and not git_is_commit_object(runner_sha, repo_path):
        errors.append(f"runner_sha '{runner_sha}' does not exist as a commit in git repository!")

    qa_contract_sha = str(qa_data.get("qa_contract_sha", "")).strip()
    if not HEX_SHA_RE.match(qa_contract_sha):
        errors.append(f"qa_contract_sha must be a 40-digit hex SHA, got: '{qa_contract_sha}'")
    elif repo_path and not git_is_commit_object(qa_contract_sha, repo_path):
        errors.append(f"qa_contract_sha '{qa_contract_sha}' does not exist as a commit in git repository!")

    if dev_data:
        dev_tested_sha = str(dev_data.get("tested_code_sha", "")).strip()
        if tested_sha != dev_tested_sha:
            errors.append(f"CRITICAL DISCREPANCY: QA tested_sha ('{tested_sha}') != DEV tested_code_sha ('{dev_tested_sha}')!")

        # Separation of Powers: DEV author cannot be QA author
        dev_author = str(dev_data.get("author") or dev_data.get("signer") or dev_data.get("dev_author") or "").strip().lower()
        qa_author = str(qa_data.get("author") or qa_data.get("signer") or qa_data.get("qa_author") or "").strip().lower()
        if dev_author and qa_author and dev_author == qa_author:
            errors.append(
                f"CRITICAL SEPARATION OF POWERS VIOLATION: DEV author ('{dev_author}') cannot sign as QA auditor! Independent identity required."
            )
    else:
        errors.append("CRITICAL: QA_RESULT cannot be validated in isolation without matching DEV_HANDOFF!")

    verdict = str(qa_data.get("verdict", "")).strip()
    if verdict not in ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "INVALID_TEST"):
        errors.append(f"Invalid QA verdict value: '{verdict}'")

    # P0-03 Fix 1: PASS 裁决必须提供物理证据目录，严禁纯字符串口头通过
    if verdict == "PASS" and not evidence_dir:
        errors.append("CRITICAL: QA verdict 'PASS' strictly requires physical evidence directory (--evidence-dir). String-only PASS verification is prohibited.")

    claimed_manifest_sha = str(qa_data.get("evidence_manifest_sha256", "")).strip().lower()
    if not HEX_SHA256_RE.match(claimed_manifest_sha):
        errors.append(f"evidence_manifest_sha256 must be a 64-digit hex string, got: '{claimed_manifest_sha}'")
    elif evidence_dir:
        profile = qa_data.get("profile", "Library")
        evidence_errors = verify_evidence_directory(evidence_dir, claimed_manifest_sha, profile=profile)
        errors.extend(evidence_errors)

    # P0-03 Fix 2: 校验 checks 实际执行项与退出码，非零退出码严禁标 PASS
    checks = qa_data.get("checks")
    if not isinstance(checks, list) or len(checks) == 0:
        errors.append("QA card must include at least one executed check item in 'checks'")
    else:
        for chk in checks:
            chk_name = chk.get("name") or chk.get("command") or "unnamed_check"
            code = chk.get("exit_code")
            if code is None:
                errors.append(f"QA check item '{chk_name}' missing exit_code field")
            elif code != 0 and verdict == "PASS":
                errors.append(f"CRITICAL REJECTION: QA check '{chk_name}' failed with exit_code {code}. Verdict cannot be PASS!")

    findings = qa_data.get("findings", {})
    if isinstance(findings, dict):
        p0_findings = findings.get("p0", [])
        if isinstance(p0_findings, list) and len(p0_findings) > 0 and verdict == "PASS":
            errors.append(f"CRITICAL REJECTION: QA card claims PASS but contains unresolved P0 findings: {p0_findings}")

    return errors


def compute_lifecycle_state(
    dev_data: Optional[Dict[str, Any]],
    qa_data: Optional[Dict[str, Any]],
    dev_errors: List[str],
    qa_errors: List[str],
    pr_merged: bool = False,
    repo_path: Optional[Path] = None,
) -> Tuple[str, str]:
    """Compute (not blindly trust) the authoritative lifecycle state."""
    # P0-04 Fix: 任何错误优先 Fail-Closed，绝不被任何外部标记跳过
    if dev_errors:
        return "DEV_REJECTED", f"DEV_HANDOFF failed validation with {len(dev_errors)} error(s)."

    if qa_errors:
        return "QA_REJECTED", f"QA_RESULT failed verification with {len(qa_errors)} error(s). Marked INVALID_TEST."

    # P0-04 Fix: 终态流转需要前序验证全绿，且在传入仓库时检验 tested_sha 真正汇入主干
    if pr_merged:
        if not qa_data or qa_data.get("verdict") != "PASS":
            return "QA_REJECTED", "Cannot mark MERGED_AND_CLOSED without an authenticated, passing QA_RESULT."
        tested_sha = str(qa_data.get("tested_sha", "")).strip()
        if repo_path and tested_sha:
            base_ref = "origin/main"
            if run_cmd(["git", "rev-parse", "--verify", base_ref], cwd=repo_path)[0] != 0:
                base_ref = "main"
            anc_code, _, _ = run_cmd(["git", "merge-base", "--is-ancestor", tested_sha, base_ref], cwd=repo_path)
            if anc_code != 0:
                return "MERGE_UNVERIFIED", f"PR merge asserted, but tested_sha '{tested_sha}' is NOT an ancestor of branch '{base_ref}'!"
        return "MERGED_AND_CLOSED", "PR is verified merged into main branch with cryptographic ancestry."

    if qa_data:
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


def load_card_input(file_arg: Optional[str], text_arg: Optional[str], marker: str) -> Optional[Dict[str, Any]]:
    """Load and parse YAML card from either file path or raw body text using extract_yaml_block."""
    if file_arg and text_arg:
        sys.exit(f"[FAIL] Cannot specify both --{marker.lower().replace('_', '-')}-card and --{marker.lower().replace('_', '-')}-text")
    if file_arg:
        p = Path(file_arg)
        if not p.is_file():
            sys.exit(f"[FAIL] Card file not found: {file_arg}")
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    if text_arg:
        block = extract_yaml_block(text_arg, marker=marker)
        if not block:
            sys.exit(f"[FAIL] No ```yaml ... kind: {marker} ... ``` block found in provided text.")
        return yaml.safe_load(block)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Five-Powers-Flow Trusted Evaluator & Coordinator v1.2.1")
    parser.add_argument("--dev-card", help="Path to YAML file containing DEV_HANDOFF")
    parser.add_argument("--dev-text", help="Raw text (PR body) containing a DEV_HANDOFF code block")
    parser.add_argument("--qa-card", help="Path to YAML file containing QA_RESULT")
    parser.add_argument("--qa-text", help="Raw text (Issue comment) containing a QA_RESULT code block")
    parser.add_argument("--evidence-dir", help="Path to evidence directory containing manifest.json")
    parser.add_argument("--manifest", help="Direct path to manifest.json file (resolves containing evidence directory)")
    parser.add_argument("--check-git", action="store_true", help="Physically verify commit objects in local git tree")
    parser.add_argument("--verify-pr-merge", help="PR number or URL to physically verify merge state via GitHub API/CLI")
    parser.add_argument("--pr-merged", action="store_true", help="Assert PR is merged into main branch (verified via git)")
    args = parser.parse_args()

    if args.manifest and not args.evidence_dir:
        m_p = Path(args.manifest)
        if m_p.is_file():
            args.evidence_dir = str(m_p.parent)
        elif m_p.is_dir():
            args.evidence_dir = str(m_p)
        else:
            args.evidence_dir = str(m_p.parent)

    repo_path = Path.cwd() if args.check_git else None
    dev_errors = []
    qa_errors = []

    print("=== [FPF Trusted Evaluator Engine v1.2.1] ===\n")

    if args.verify_pr_merge:
        is_merged, merge_sha, msg = verify_github_pr_merge(args.verify_pr_merge, repo_path=repo_path)
        if not is_merged:
            print(f"[FAIL] GitHub PR Merge Verification Failed: {msg}")
            qa_errors.append(f"PR merge verification failed: {msg}")
        else:
            print(f"[PASS] GitHub PR Merge Verified: {msg} (Commit: {merge_sha})")
            args.pr_merged = True

    dev_data = load_card_input(args.dev_card, args.dev_text, "DEV_HANDOFF")
    if dev_data:
        dev_errors = validate_dev_handoff(dev_data, repo_path=repo_path)
        if dev_errors:
            print("[FAIL] DEV_HANDOFF Validation Failures:")
            for e in dev_errors:
                print(f"  - {e}")
        else:
            print("[PASS] DEV_HANDOFF is cryptographically and structurally valid.")

    qa_data = load_card_input(args.qa_card, args.qa_text, "QA_RESULT")
    if qa_data:
        evidence_dir_p = Path(args.evidence_dir) if args.evidence_dir else None
        qa_errors = validate_qa_result(
            qa_data,
            dev_data=dev_data,
            repo_path=repo_path,
            evidence_dir=evidence_dir_p,
        )
        if qa_errors:
            print("[FAIL] QA_RESULT Verification Failures:")
            for e in qa_errors:
                print(f"  - {e}")
        else:
            print("[PASS] QA_RESULT is cryptographically and structurally valid.")

    state, reason = compute_lifecycle_state(
        dev_data,
        qa_data,
        dev_errors,
        qa_errors,
        pr_merged=args.pr_merged,
        repo_path=repo_path,
    )
    print(f"\n[Computed Lifecycle State] => {state}")
    print(f"[Reason]                   => {reason}\n")

    if dev_errors or qa_errors:
        print("[FAIL] Lifecycle evaluation blocked on integrity errors.")
        return 1

    print("[SUCCESS] All evaluated checkpoints satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
