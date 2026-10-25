"""Hermetic one-slice tests; no network, API key, or Codex CLI required."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from packages.fpf_runtime.adapters import RoleResult, StepResult, ensure_qa_worktree, git
from packages.fpf_runtime.ledger import Ledger
from packages.fpf_runtime.runtime import SliceRuntime


def cmd(repo, *args):
    p = subprocess.run(args, cwd=repo, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout.strip()


class FakeRoles:
    def __init__(self):
        self.calls = []

    def ask(self, role, message, previous_response_id=None):
        self.calls.append((role, previous_response_id))
        return RoleResult("Work order from " + role, "response-" + role)


class FakeCodex:
    def __init__(self, qa_fail_first=False, commit_inside=False):
        self.qa_calls = 0
        self.qa_fail_first = qa_fail_first
        self.commit_inside = commit_inside

    def run(self, workspace, prompt, read_only=False):
        if read_only:
            self.qa_calls += 1
            fail = self.qa_fail_first and self.qa_calls == 1
            return StepResult(0, json.dumps(
                {"verdict": "FAIL" if fail else "PASS",
                 "findings": ["adversarial failure"] if fail else []}))
        (workspace / "feature.txt").write_text("iteration " + str(self.qa_calls), encoding="utf-8")
        if self.commit_inside:
            cmd(workspace, "git", "add", "feature.txt")
            cmd(workspace, "git", "commit", "-m", "fake DEV commit")
        return StepResult(0, "Codex finished")


class TestSliceRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dev, self.qa = root / "dev", root / "qa"
        self.dev.mkdir()
        cmd(self.dev, "git", "init", "-b", "main")
        cmd(self.dev, "git", "config", "user.name", "Test Runner")
        cmd(self.dev, "git", "config", "user.email", "runner@example.test")
        (self.dev / "README.md").write_text("# baseline\n", encoding="utf-8")
        cmd(self.dev, "git", "add", ".")
        cmd(self.dev, "git", "commit", "-m", "baseline")
        self.base = git(self.dev, "rev-parse", "HEAD")
        cmd(self.dev, "git", "checkout", "-b", "feat/slice")
        self.ledger = Ledger(root / "runtime.sqlite3")
        self.ledger.create("SLICE_001", "Produce feature.txt", self.base, 3)
        self.roles = FakeRoles()
        self.codex = FakeCodex()

    def tearDown(self):
        self.ledger.conn.close()
        self.tmp.cleanup()

    def runtime(self):
        check = [sys.executable, "-B", "-c", "assert True"]
        return SliceRuntime(self.ledger, self.roles, self.codex, self.dev, self.qa, check, check)

    def test_success_and_main_not_merged(self):
        r = self.runtime().run("SLICE_001")
        self.assertEqual(r["phase"], "READY_FOR_OWNER_REVIEW")
        self.assertEqual(r["attempt"], 1)
        self.assertEqual(git(self.dev, "rev-parse", "main"), self.base)
        self.assertEqual(git(self.qa, "rev-parse", "HEAD"), r["head_sha"])
        self.assertIn("READY_FOR_OWNER_REVIEW", r["report"])

    def test_qa_fail_then_dev_retry_then_new_qa_pass(self):
        self.codex = FakeCodex(qa_fail_first=True)
        r = self.runtime().run("SLICE_001")
        self.assertEqual(r["phase"], "READY_FOR_OWNER_REVIEW")
        self.assertEqual(r["attempt"], 2)
        self.assertEqual(self.codex.qa_calls, 2)
        self.assertEqual(git(self.qa, "rev-parse", "HEAD"), r["head_sha"])
        self.assertEqual([e["state"] for e in self.ledger.events("SLICE_001")].count("NEEDS_REWORK"), 1)
        self.assertEqual([r for r, _ in self.roles.calls], ["DEV", "QA", "DEV", "QA"])
        self.assertEqual(self.roles.calls[2][1], "response-DEV")

    def test_codex_workspace_edits_are_committed_by_orchestrator(self):
        r = self.runtime().run("SLICE_001")
        self.assertNotEqual(r["head_sha"], self.base)
        self.assertEqual(git(self.dev, "status", "--porcelain"), "")

    def test_codex_precommitted_changes_are_supported(self):
        self.codex = FakeCodex(commit_inside=True)
        self.assertEqual(self.runtime().run("SLICE_001")["phase"], "READY_FOR_OWNER_REVIEW")

    def test_attempts_are_bounded(self):
        self.codex = FakeCodex(qa_fail_first=True)
        s = self.ledger.read("SLICE_001")
        s["max_attempts"] = 1
        self.ledger.save(s, "NEW")
        self.assertEqual(self.runtime().run("SLICE_001")["phase"], "BLOCKED")

    def test_crash_during_qa_stops_for_reconciliation(self):
        s = self.ledger.read("SLICE_001")
        self.ledger.save(s, "QA_RUNNING")
        self.assertEqual(self.runtime().run("SLICE_001")["phase"], "BLOCKED_RECONCILIATION")
        self.assertEqual(self.codex.qa_calls, 0)

    def test_task_id_collision_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.create("SLICE_001", "different goal", self.base, 3)

    def test_unrelated_qa_repository_is_rejected(self):
        self.qa.mkdir()
        cmd(self.qa, "git", "init", "-b", "main")
        with self.assertRaises(RuntimeError):
            ensure_qa_worktree(self.dev, self.qa, self.base)

    def test_main_branch_is_not_a_dev_workspace(self):
        cmd(self.dev, "git", "checkout", "main")
        with self.assertRaises(ValueError):
            self.runtime()

    def test_qa_markdown_code_fence_is_parsed(self):
        class MarkdownFenceCodex(FakeCodex):
            def run(self, workspace, prompt, read_only=False):
                if read_only:
                    return StepResult(0, "```json\n{\"verdict\": \"PASS\", \"findings\": []}\n```")
                return super().run(workspace, prompt, read_only=read_only)
        self.codex = MarkdownFenceCodex()
        r = self.runtime().run("SLICE_001")
        self.assertEqual(r["phase"], "READY_FOR_OWNER_REVIEW")

    def test_openai_responses_roles_custom_base_url_and_localhost_key(self):
        from packages.fpf_runtime.adapters import OpenAIResponsesRoles
        roles = OpenAIResponsesRoles("auto/gpt-5.6-luna", base_url="http://127.0.0.1:3425/v1")
        self.assertEqual(roles.base_url, "http://127.0.0.1:3425/v1")
        self.assertEqual(roles.api_key, "magpie")

    def test_cli_windows_path_shlex_preserves_backslashes(self):
        import shlex
        cmd_str = r"python -m unittest D:\foo\bar"
        # On Windows (posix=False), shlex.split preserves backslashes instead of stripping them
        args_win = shlex.split(cmd_str, posix=False)
        self.assertIn(r"D:\foo\bar", args_win)


if __name__ == "__main__":
    unittest.main()
