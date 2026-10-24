#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Claude Code PreToolUse Guard for DEV Workspaces.

Mechanically enforces the Five-Powers-Flow cardinal rule:
DEV agents are strictly forbidden from modifying PROJECT-MAP.md via Edit/Write tools.

Exit Code Protocol:
- 0: Tool invocation permitted.
- 2: Tool invocation BLOCKED (Claude Code PreToolUse specification error return).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


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
        # Fail-closed if payload is corrupted
        sys.stderr.write(f"[FPF HOOK ERROR] Failed to parse PreToolUse payload: {exc}\n")
        return 2

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Intercept file mutation tools
    if tool_name in ("Edit", "Write", "NotebookEdit"):
        norm = normalize_path(file_path)
        if "project-map.md" in norm:
            sys.stderr.write(
                "\n======================================================================\n"
                "[FPF CRITICAL BLOCK] DEV Agent is forbidden from modifying PROJECT-MAP.md!\n"
                "Under Five-Powers-Flow RFC-001, PROJECT-MAP.md is exclusively maintained\n"
                "by Truth Scribe based on independent QA PASS evidence.\n"
                "Self-marking progress in DEV workspace is strictly prohibited.\n"
                "======================================================================\n\n"
            )
            # Exit code 2 is the official Claude Code PreToolUse blocking code
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
