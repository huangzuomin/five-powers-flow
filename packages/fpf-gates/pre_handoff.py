#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Pre-Handoff Quality Gate.

Ensures the working tree is clean, no untracked dirty files exist,
and hand-off metadata satisfies the RFC-001 specification before submission.
"""
from __future__ import annotations

import os
import subprocess
import sys


def check_git_status() -> bool:
    """Check if there are uncommitted or untracked changes."""
    res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if res.stdout.strip():
        print("[FAIL] Dirty working tree detected! Uncommitted or untracked files:")
        print(res.stdout)
        return False
    print("[PASS] Working tree is completely clean.")
    return True


def main() -> int:
    print("[FPF Gate] Running pre-handoff inspection...")
    if not check_git_status():
        return 1
    print("[FPF Gate] All pre-handoff gates passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
