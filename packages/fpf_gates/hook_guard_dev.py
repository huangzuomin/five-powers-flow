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



SENSITIVE_FILE_PATTERNS = [
    r"(?:^|[/\s'\"])\.env(?:\.[a-zA-Z0-9_\-]+)?(?:$|[\s'\"])",
    r"\.(?:pem|key|pkcs12|pfx|p12|kdbx)(?:$|[\s'\"])",
    r"(?:^|[/\s'\"])id_(?:rsa|ed25519|ecdsa|dsa)(?:\.pub)?(?:$|[\s'\"])",
    r"(?:^|[/\s'\"])(?:credentials|client_secret|service_account|service-account).*\.json(?:$|[\s'\"])",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|above)\s+instructions",
    r"disregard\s+(?:all\s+)?(?:previous|above)\s+instructions",
    r"disregard\s+(?:the\s+)?system\s+prompt",
    r"system\s+prompt\s+override",
    r"you\s+are\s+now\s+(?:root|admin|superuser|unrestricted)",
    r"bypass\s+(?:all\s+)?(?:fpf|gate|security|policy|governance)",
    r"disable\s+(?:fpf\s+)?(?:hook|guard|gate)",
    r"override\s+(?:all\s+)?(?:rules|governance|authorization|permissions)",
    r"pretend\s+you\s+have\s+(?:root|admin|full)\s+privileges",
]


def is_credential_sensitive_path(path: str) -> bool:
    """Detect whether path refers to credentials, keys, or secret environment files."""
    norm = normalize_path(path)
    return any(re.search(pat, norm, re.IGNORECASE) for pat in SENSITIVE_FILE_PATTERNS)


def contains_prompt_injection(text: str) -> bool:
    """Detect prompt injection or malicious privilege escalation commands."""
    if not text or not isinstance(text, str):
        return False
    return any(re.search(pat, text, re.IGNORECASE) for pat in PROMPT_INJECTION_PATTERNS)


def normalize_path(p: str) -> str:
    """Normalize Windows/POSIX path separators and casing."""
    return os.path.normpath(p).replace("\\", "/").lower()


def check_pre_tool_use(payload: dict) -> int:
    """Evaluate Claude Code PreToolUse payload against FPF governance, credential, and injection gates.

    Returns:
        0: Tool invocation permitted.
        2: Tool invocation BLOCKED.
    """
    if not isinstance(payload, dict):
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0

    # 0. Intercept prompt injection in any parameter
    for key, val in tool_input.items():
        if isinstance(val, str) and contains_prompt_injection(val):
            sys.stderr.write(
                "\n======================================================================\n"
                "[FPF CRITICAL BLOCK] Prompt injection / malicious privilege escalation detected!\n"
                f"Parameter: {key}\n"
                "Under Five-Powers-Flow RFC-001, prompt injections and unauthorized overrides are blocked.\n"
                "======================================================================\n\n"
            )
            return 2

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

        if is_credential_sensitive_path(file_path):
            sys.stderr.write(
                "\n======================================================================\n"
                f"[FPF CRITICAL BLOCK] Tool invocation targets sensitive credential file: {base_name}!\n"
                "Under Five-Powers-Flow Security Policy, modifying credentials/secrets is forbidden.\n"
                "======================================================================\n\n"
            )
            return 2

    # 2. Intercept command-line mutation or secret-dumping attempts in Bash
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

        bash_secret_pat = r"(?:(?:cat|type|head|tail|more|less|grep|python|node|powershell|pwsh)\b|>|>>).*(?:\.env|\.pem|\.key|\.pfx|id_rsa|id_ed25519|credentials\.json)"
        if re.search(bash_secret_pat, command, re.IGNORECASE):
            sys.stderr.write(
                "\n======================================================================\n"
                "[FPF CRITICAL BLOCK] Bash command attempts to access/mutate sensitive credential file!\n"
                f"Command: {command}\n"
                "======================================================================\n\n"
            )
            return 2

    return 0


def main() -> int:
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            return 0
        payload = json.loads(raw_input)
    except Exception as exc:
        sys.stderr.write(f"[FPF HOOK WARNING] Failed to parse PreToolUse payload: {exc}\n")
        return 0

    return check_pre_tool_use(payload)


if __name__ == "__main__":
    sys.exit(main())
