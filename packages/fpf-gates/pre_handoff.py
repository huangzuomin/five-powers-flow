#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Pre-Handoff Quality Gate.

RFC-001 v1.2 Reference Implementation of the 4 mechanical pre-handoff gates:
1. Clean Working Tree (No uncommitted or untracked dirty files)
2. Valid Cryptographic HEAD Commit Object (Must be type 'commit')
3. Fail-Closed Anti-Tamper Fence (Mechanical block if DEV branch touched protected governance files)
4. Sensitive Credential & Dirty Artifact Audit
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

HEX_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

PROTECTED_EXACT_FILES = {
    "project-map.md",
    "docs/project-map.md",
    "docs/coordination/project-map.md",
    "lessons.md",
    "docs/lessons.md",
    "docs/coordination/lessons.md",
}

SENSITIVE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),               # AWS Access Key
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),            # Generic API Secret
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),            # GitHub Personal Token
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), # Private Keys
]


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def gate_1_clean_working_tree() -> bool:
    """Gate 1: Ensure zero uncommitted or untracked files."""
    code, out, _ = run_cmd(["git", "status", "--porcelain"])
    if out:
        print("[FAIL Gate 1] Dirty working tree detected! Uncommitted or untracked changes:")
        for line in out.splitlines():
            print(f"  {line}")
        return False
    print("[PASS Gate 1] Working tree is completely clean.")
    return True


def gate_2_valid_head_commit() -> bool:
    """Gate 2: Ensure current HEAD is a valid 40-digit SHA AND is a 'commit' object."""
    code, out, _ = run_cmd(["git", "rev-parse", "HEAD"])
    if code != 0 or not HEX_SHA_RE.match(out):
        print(f"[FAIL Gate 2] Cannot resolve valid 40-digit HEAD SHA (got: '{out}')")
        return False
    type_code, type_out, _ = run_cmd(["git", "cat-file", "-t", out])
    if type_code != 0 or type_out != "commit":
        print(f"[FAIL Gate 2] HEAD SHA '{out}' is of type '{type_out}', expected 'commit'!")
        return False
    print(f"[PASS Gate 2] Valid HEAD commit object: {out}")
    return True


def gate_3_project_map_anti_tamper(base_branch: str = "main") -> bool:
    """Gate 3: Fail-Closed Anti-Tamper Fence for PROJECT-MAP.md and LESSONS.md."""
    check_code, _, check_err = run_cmd(["git", "rev-parse", "--verify", base_branch])
    if check_code != 0:
        print(f"[CRITICAL FAIL Gate 3] Fail-Closed: Cannot resolve base branch '{base_branch}': {check_err}")
        return False

    code, out, err = run_cmd(["git", "diff", "--name-only", f"{base_branch}...HEAD"])
    if code != 0:
        print(f"[CRITICAL FAIL Gate 3] Fail-Closed: 'git diff {base_branch}...HEAD' returned non-zero exit code: {err}")
        return False

    if out:
        changed_files = [f.strip() for f in out.splitlines() if f.strip()]
        for f in changed_files:
            norm_path = os.path.normpath(f).replace("\\", "/").lower()
            if norm_path in PROTECTED_EXACT_FILES:
                print(f"[CRITICAL FAIL Gate 3] Anti-Tamper Block: DEV branch modified protected file '{f}'!")
                print("  -> Under Five-Powers-Flow RFC-001, PROJECT-MAP.md and LESSONS.md are exclusively maintained by Scribe.")
                print("  -> Self-marking results in DEV PR is strictly forbidden.")
                return False

    print("[PASS Gate 3] Anti-Tamper check passed (protected governance files were not touched).")
    return True


def gate_4_sensitive_artifact_audit() -> bool:
    """Gate 4: Scan uncommitted or newly added files for obvious secret leaks."""
    code, out, _ = run_cmd(["git", "diff", "--name-only", "HEAD~1...HEAD"])
    files_to_scan = [f.strip() for f in out.splitlines() if f.strip()] if (code == 0 and out) else []

    leaks_found = []
    for filepath in files_to_scan:
        p = Path(filepath)
        if not p.is_file():
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            for pattern in SENSITIVE_PATTERNS:
                if pattern.search(content):
                    leaks_found.append((filepath, pattern.pattern))
        except Exception:
            pass

    if leaks_found:
        print("[FAIL Gate 4] Sensitive credential patterns detected in modified files:")
        for f, pat in leaks_found:
            print(f"  - File '{f}' matched secret pattern: {pat}")
        return False

    print("[PASS Gate 4] Sensitive credential audit passed (zero obvious secrets detected).")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="FPF Pre-Handoff Quality Gate Runner v1.2")
    parser.add_argument("--base", default="main", help="Base branch to compare diff against (default: main)")
    parser.add_argument("--skip-clean-check", action="store_true", help="Skip clean tree check (for testing only)")
    args = parser.parse_args()

    print("=== [FPF Pre-Handoff Quality Gates v1.2] ===\n")
    success = True

    if not args.skip_clean_check:
        if not gate_1_clean_working_tree():
            success = False
    else:
        print("[SKIP Gate 1] Working tree clean check skipped by flag.")

    if not gate_2_valid_head_commit():
        success = False

    if not gate_3_project_map_anti_tamper(base_branch=args.base):
        success = False

    if not gate_4_sensitive_artifact_audit():
        success = False

    print("\n" + "="*40)
    if success:
        print("[PASS] All 4 pre-handoff quality gates passed successfully. Ready for QA submission.")
        return 0
    else:
        print("[FAIL] Pre-handoff gates failed. Fix issues before requesting QA admission.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
