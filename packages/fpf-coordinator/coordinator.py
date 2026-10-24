#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Neutral Coordinator & State Engine.

Monitors VCS events (GitHub/GitLab), parses standardized hand-off cards,
validates cryptographic SHAs and isolation gates, and dispatches the next
authorized actor without retaining arbitrary decision power.
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


def extract_yaml_block(text: str, marker: str = "DEV_HANDOFF") -> Optional[str]:
    """Extract standard YAML blocks enclosed in ```yaml ... ``` from issue/PR bodies."""
    if not text:
        return None
    pattern = re.compile(rf"```yaml\s*([\s\S]*?kind:\s*{marker}[\s\S]*?)```", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return None


def validate_handoff_dict(data: Dict[str, Any]) -> List[str]:
    """Validate core fields of DEV_HANDOFF."""
    errors = []
    required_scalars = ["handoff_version", "kind", "task_id", "baseline_sha", "tested_code_sha", "pr_url", "state"]
    for field in required_scalars:
        val = data.get(field)
        if val is None or val == "":
            errors.append(f"Missing required scalar field: {field}")

    tested_sha = str(data.get("tested_code_sha", "")).strip()
    if tested_sha and not HEX_SHA_RE.match(tested_sha):
        errors.append(f"tested_code_sha must be a full 40-character SHA, got: {tested_sha}")

    if not isinstance(data.get("changed_files"), list) or not data.get("changed_files"):
        errors.append("changed_files must be a non-empty list of paths")

    if not isinstance(data.get("not_run"), list):
        errors.append("not_run must be explicitly provided as a list (cannot be omitted)")

    return errors


def classify_stage(pr_state: str, handoff_data: Optional[Dict[str, Any]], qa_result_data: Optional[Dict[str, Any]]) -> str:
    """Classify the current lifecycle stage based on verifiable state."""
    if pr_state == "MERGED":
        return "MERGED_AND_CLOSED"
    if qa_result_data:
        verdict = qa_result_data.get("verdict")
        if verdict == "PASS":
            return "QA_PASSED_AWAITING_OWNER"
        elif verdict in ("FAIL", "INVALID_TEST"):
            return "QA_FAILED_REWORK_REQUIRED"
        elif verdict == "BLOCKED":
            return "BLOCKED_ON_DEPENDENCY"
    if handoff_data:
        if handoff_data.get("state") == "DEV_READY_FOR_QA":
            return "DEV_READY_AWAITING_QA_ADMISSION"
        elif handoff_data.get("state") == "DEV_BLOCKED":
            return "DEV_BLOCKED"
    return "DEV_IN_PROGRESS"


def main() -> int:
    parser = argparse.ArgumentParser(description="Five-Powers-Flow Coordinator CLI")
    parser.add_argument("--repo", required=True, help="GitHub repository (owner/name)")
    parser.add_argument("--pr", type=int, help="Target PR number to evaluate")
    args = parser.parse_args()

    print(f"[FPF Coordinator] Polling repository: {args.repo}")
    if args.pr:
        print(f"[FPF Coordinator] Inspecting PR #{args.pr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
