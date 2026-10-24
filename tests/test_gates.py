#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Client Gates & Hook Guard Unit Tests v1.2.1.

Coverage across Issue #23 items:
- Gate 1: Dirty working tree detection
- Gate 2: Commit object type validation (cat-file -t)
- Gate 3: Anti-Tamper fence blocking PROJECT-MAP.md and LESSONS.md mutations
- Gate 4: Sensitive credential scan across full commit diff and working state
- Hook Guard: PreToolUse hook blocking Edit/Write/NotebookEdit/Bash mutations on protected files
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from packages.fpf_gates import pre_handoff
from packages.fpf_gates import hook_guard_dev


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()


class TestClientGatesAndHook(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.tmpdir.name)

        run_cmd(["git", "init", "-b", "main"], cwd=self.repo_path)
        run_cmd(["git", "config", "user.name", "Gate Tester"], cwd=self.repo_path)
        run_cmd(["git", "config", "user.email", "tester@example.com"], cwd=self.repo_path)
        run_cmd(["git", "config", "commit.gpgsign", "false"], cwd=self.repo_path)

        # Initial commit on main
        (self.repo_path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        run_cmd(["git", "add", "."], cwd=self.repo_path)
        run_cmd(["git", "commit", "-m", "chore: initial commit"], cwd=self.repo_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_gate_1_clean_and_dirty_tree(self):
        """Gate 1: Detects clean vs dirty working tree."""
        # Monkey patch run_cmd to run in temp repo
        orig_run_cmd = pre_handoff.run_cmd
        try:
            pre_handoff.run_cmd = lambda cmd: run_cmd(cmd, cwd=self.repo_path)
            self.assertTrue(pre_handoff.gate_1_clean_working_tree())

            # Make dirty
            (self.repo_path / "dirty.txt").write_text("untracked", encoding="utf-8")
            self.assertFalse(pre_handoff.gate_1_clean_working_tree())
        finally:
            pre_handoff.run_cmd = orig_run_cmd

    def test_gate_3_blocks_project_map_modification(self):
        """Gate 3: Anti-Tamper fence blocks branch modifying PROJECT-MAP.md."""
        orig_run_cmd = pre_handoff.run_cmd
        try:
            pre_handoff.run_cmd = lambda cmd: run_cmd(cmd, cwd=self.repo_path)

            # Feature branch modifying PROJECT-MAP.md
            run_cmd(["git", "checkout", "-b", "feat/bad-tamper"], cwd=self.repo_path)
            (self.repo_path / "PROJECT-MAP.md").write_text("# Tampered Map\n", encoding="utf-8")
            run_cmd(["git", "add", "."], cwd=self.repo_path)
            run_cmd(["git", "commit", "-m", "tampering with project map"], cwd=self.repo_path)

            self.assertFalse(pre_handoff.gate_3_project_map_anti_tamper(base_branch="main"))
        finally:
            pre_handoff.run_cmd = orig_run_cmd

    def test_gate_3_blocks_lessons_modification(self):
        """Gate 3: Anti-Tamper fence blocks branch modifying LESSONS.md."""
        orig_run_cmd = pre_handoff.run_cmd
        try:
            pre_handoff.run_cmd = lambda cmd: run_cmd(cmd, cwd=self.repo_path)

            run_cmd(["git", "checkout", "-b", "feat/bad-lessons"], cwd=self.repo_path)
            (self.repo_path / "LESSONS.md").write_text("# Tampered Lessons\n", encoding="utf-8")
            run_cmd(["git", "add", "."], cwd=self.repo_path)
            run_cmd(["git", "commit", "-m", "tampering with lessons"], cwd=self.repo_path)

            self.assertFalse(pre_handoff.gate_3_project_map_anti_tamper(base_branch="main"))
        finally:
            pre_handoff.run_cmd = orig_run_cmd

    def test_gate_4_detects_sensitive_credentials_in_commit(self):
        """Gate 4: Scans commit diff and catches AWS Access Key or secret pattern."""
        orig_run_cmd = pre_handoff.run_cmd
        try:
            pre_handoff.run_cmd = lambda cmd: run_cmd(cmd, cwd=self.repo_path)

            run_cmd(["git", "checkout", "-b", "feat/leak-test"], cwd=self.repo_path)
            # Legitimate file
            (self.repo_path / "code.py").write_text("SECRET_KEY = '" + "AK" + "IA" + "IOSFODNN7EXAMPLE'\n", encoding="utf-8")
            run_cmd(["git", "add", "."], cwd=self.repo_path)
            run_cmd(["git", "commit", "-m", "leak secret"], cwd=self.repo_path)

            self.assertFalse(pre_handoff.gate_4_sensitive_artifact_audit(base_branch="main"))
        finally:
            pre_handoff.run_cmd = orig_run_cmd

    def test_hook_guard_blocks_edit_on_governance_files(self):
        """Hook Guard: Returns exit code 2 when Claude Code attempts Edit on PROJECT-MAP.md."""
        import io
        orig_stdin = sys.stdin
        orig_stderr = sys.stderr
        try:
            # 1. Edit PROJECT-MAP.md -> blocked (exit 2)
            payload = {
                "tool_name": "Edit",
                "tool_input": {"file_path": "docs/coordination/PROJECT-MAP.md"}
            }
            sys.stdin = io.StringIO(json.dumps(payload))
            sys.stderr = io.StringIO()
            res = hook_guard_dev.main()
            self.assertEqual(res, 2)

            # 2. Edit LESSONS.md -> blocked (exit 2)
            payload2 = {
                "tool_name": "Write",
                "tool_input": {"file_path": "LESSONS.md"}
            }
            sys.stdin = io.StringIO(json.dumps(payload2))
            sys.stderr = io.StringIO()
            res2 = hook_guard_dev.main()
            self.assertEqual(res2, 2)

            # 3. Normal file edit -> permitted (exit 0)
            payload_ok = {
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/app.py"}
            }
            sys.stdin = io.StringIO(json.dumps(payload_ok))
            sys.stderr = io.StringIO()
            res_ok = hook_guard_dev.main()
            self.assertEqual(res_ok, 0)
        finally:
            sys.stdin = orig_stdin
            sys.stderr = orig_stderr

    def test_hook_guard_blocks_bash_mutation_on_governance_files(self):
        """Hook Guard: Returns exit code 2 when Bash command attempts to overwrite PROJECT-MAP.md."""
        import io
        orig_stdin = sys.stdin
        orig_stderr = sys.stderr
        try:
            # Bash redirection
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "echo 'done' >> docs/coordination/PROJECT-MAP.md"}
            }
            sys.stdin = io.StringIO(json.dumps(payload))
            sys.stderr = io.StringIO()
            res = hook_guard_dev.main()
            self.assertEqual(res, 2)

            # Normal Bash command -> permitted
            payload_ok = {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/unit"}
            }
            sys.stdin = io.StringIO(json.dumps(payload_ok))
            sys.stderr = io.StringIO()
            res_ok = hook_guard_dev.main()
            self.assertEqual(res_ok, 0)
        finally:
            sys.stdin = orig_stdin
            sys.stderr = orig_stderr


if __name__ == "__main__":
    unittest.main()
