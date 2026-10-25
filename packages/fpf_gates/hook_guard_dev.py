#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Claude Code PreToolUse Guard for DEV Workspaces.

Mechanically enforces the Five-Powers-Flow cardinal rule:
DEV agents are strictly forbidden from modifying PROJECT-MAP.md or LESSONS.md
via file editing tools (Edit, Write, NotebookEdit) or mutation commands in Bash.

Exit Code Protocol:
- 0: Tool invocation permitted.
- 2: Tool invocation BLOCKED (Claude Code PreToolUse specification error return).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys

try:
    from packages.fpf_policy.protected import is_protected_tool_path
except ModuleNotFoundError:
    # Direct script execution (python packages/fpf_gates/*.py) must work
    # without the caller manually setting PYTHONPATH.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from packages.fpf_policy.protected import is_protected_tool_path

# Block common write operations targeting protected paths. This is advisory:
# service-side PR gates remain mandatory because shell syntax is unbounded.
BASH_MUTATION_PATTERNS = [
    r"(?:>|>>|tee|sed\s+-i|cp\s+|mv\s+|dd\s+|git\s+(?:checkout|restore|show)\s+)[^|;&\n]{0,200}(?:agents\.md|project[-_]?map\.md|lessons\.md|handoff-protocol\.md|\.github/|\.fpf/|schemas/)",
    r"(?:echo|printf|python|node|powershell|pwsh|cat)\b.*(?:>|>>)\s*.*(?:agents\.md|\.github/|\.fpf/|schemas/)",
]



def normalize_path(p: str) -> str:
    """Normalize Windows/POSIX path separators and casing."""
    return os.path.normpath(p).replace("\\", "/").lower()


def main() -> int:
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            return 0
        payload = json.loads(raw_input)
    except Exception as exc:
        sys.stderr.write(f"[FPF HOOK WARNING] Failed to parse PreToolUse payload: {exc}\n")
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # 1. Intercept structured file editing tools
    if tool_name in ("Edit", "Write", "NotebookEdit"):
        norm = normalize_path(file_path)
        base_name = os.path.basename(norm)
        if is_protected_tool_path(file_path):
            sys.stderr.write(
                "\n======================================================================\n"
                f"[FPF CRITICAL BLOCK] DEV Agent is forbidden from modifying {base_name}!\n"
                "Under Five-Powers-Flow RFC-001, PROJECT-MAP.md and LESSONS.md are exclusively\n"
                "maintained by Truth Scribe based on independent QA PASS evidence.\n"
                "Modifying governance ledgers in DEV workspace is strictly prohibited.\n"
                "======================================================================\n\n"
            )
            return 2

    # 2. Intercept command-line mutation attempts in Bash
    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        for pattern in BASH_MUTATION_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                sys.stderr.write(
                    "\n======================================================================\n"
                    "[FPF CRITICAL BLOCK] Bash command attempts to overwrite protected governance file!\n"
                    f"Command: {command}\n"
                    "Under Five-Powers-Flow RFC-001, PROJECT-MAP.md and LESSONS.md cannot be mutated by DEV.\n"
                    "======================================================================\n\n"
                )
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
