"""Hermetic tests for integrated workflow, SDK role sessions and GitHub draft output."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import yaml

from packages.fpf_runtime.adapters import RoleResult, StepResult, git
from packages.fpf_runtime.evidence import verify_qa_evidence
from packages.fpf_runtime.github_pr import GhDraftPublisher
from packages.fpf_runtime.ledger import Ledger
from packages.fpf_runtime.runtime import SliceRuntime


def command(where: Path, *args: str):
    p = subprocess.run(args, cwd=where, capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout.strip()


class Planner:
    def ask(self, role, message, previous_response_id=None):
        return RoleResult("Implement and test requested function", "role-" + role)


class Coder:
    def __init__(self, fail_once=False):
        self.reviews = 0
        self.fail_once = fail_once

    def run(self, workspace, prompt, read_only=False):
        if read_only:
            self.reviews += 1
            failed = self.fail_once and self.reviews == 1
            return StepResult(0, json.dumps(
                {"verdict": "FAIL" if failed else "PASS",
                 "findings": ["needs fix"] if failed else []}))
        (workspace / "feature.txt").write_text("attempt-" + str(self.reviews), encoding="utf-8")
        return StepResult(0, "Implemented")


class Publisher:
    def __init__(self):
        self.calls = 0

    def publish(self, path, state):
        self.calls += 1
        if not verify_qa_evidence(state["evidence_path"], state["evidence_sha256"],
                                  state["head_sha"]):
            raise RuntimeError("bad evidence")
        return "https://github.com/example/example/pull/8"


class FakeGh(GhDraftPublisher):
    def __init__(self):
        super().__init__()
        self.body = ""

    def _gh(self, repo, *args):
        if args[:2] == ("repo", "view"):
            return '{"nameWithOwner": "example/example"}'
        if args[:2] == ("api", "user"):
            return "fpftest-author"
        if args[:2] == ("pr", "list"):
            return "[]"
        if args[:2] == ("auth", "status"):
            return "Authenticated"
        if args[:2] == ("pr", "create"):
            return "https://github.com/example/example/pull/8"
        if args[:2] == ("pr", "edit"):
            self.body = Path(args[-1]).read_text(encoding="utf-8")
            return ""
        raise AssertionError("Unexpected GitHub command: " + repr(args))


class TestIntegratedSlice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dev, self.qa, self.root = root / "dev", root / "qa", root
        self.dev.mkdir()
        command(self.dev, "git", "init", "-b", "main")
        command(self.dev, "git", "config", "user.name", "Tester")
        command(self.dev, "git", "config", "user.email", "tester@example.invalid")
        (self.dev / "README.md").write_text("Base\n", encoding="utf-8")
        command(self.dev, "git", "add", ".")
        command(self.dev, "git", "commit", "-m", "initial")
        self.base = git(self.dev, "rev-parse", "HEAD")
        command(self.dev, "git", "checkout", "-b", "feat/test")
        self.ledger = Ledger(root / "state.sqlite3")
        self.ledger.create("SLICE001", "Implement feature.txt", self.base, 3)
        self.dev_check = [sys.executable, "-B", "-c", "assert True"]
        self.qa_check = [sys.executable, "-B", "-c", "assert True"]

    def tearDown(self):
        self.ledger.conn.close()
        self.tmp.cleanup()

    def runtime(self, publisher=None):
        return SliceRuntime(
            self.ledger, Planner(), Coder(), self.dev, self.qa,
            self.dev_check, self.qa_check, publisher=publisher,
            evidence_root=self.root / "artifacts")

    def test_provisional_qa_evidence_matches_exact_commit(self):
        result = self.runtime().run("SLICE001")
        self.assertEqual(result["phase"], "READY_FOR_OWNER_REVIEW")
        self.assertTrue(verify_qa_evidence(
            result["evidence_path"], result["evidence_sha256"], result["head_sha"]))
        self.assertFalse(verify_qa_evidence(
            result["evidence_path"], result["evidence_sha256"], self.base))
        path = Path(result["evidence_path"]).parent / "check.log"
        path.write_text("Tampered", encoding="utf-8")
        self.assertFalse(verify_qa_evidence(
            result["evidence_path"], result["evidence_sha256"], result["head_sha"]))

    def test_publish_is_opt_in_and_final_state_contains_pr_url(self):
        publisher = Publisher()
        result = self.runtime(publisher).run("SLICE001")
        self.assertEqual(publisher.calls, 1)
        self.assertEqual(result["phase"], "READY_FOR_OWNER_REVIEW")
        self.assertEqual(result["pr_url"], "https://github.com/example/example/pull/8")
        self.assertIn("draft_pr_url", json.loads(result["report"]))
        self.assertEqual(git(self.dev, "rev-parse", "main"), self.base)

    def test_interrupted_external_publication_never_autoretries(self):
        state = self.ledger.read("SLICE001")
        self.ledger.save(state, "PUBLISH_RUNNING")
        pub = Publisher()
        result = self.runtime(pub).run("SLICE001")
        self.assertEqual(result["phase"], "BLOCKED_RECONCILIATION")
        self.assertEqual(pub.calls, 0)

    def test_model_pass_cannot_override_failed_test_process(self):
        self.qa_check = [sys.executable, "-B", "-c", "raise SystemExit(1)"]
        state = self.ledger.read("SLICE001")
        state["max_attempts"] = 1
        self.ledger.save(state, "NEW")
        result = self.runtime().run("SLICE001")
        self.assertEqual(result["phase"], "BLOCKED")
        self.assertFalse(verify_qa_evidence(
            result["evidence_path"], result["evidence_sha256"], result["head_sha"]))

    def test_github_draft_publisher_emits_valid_dev_card(self):
        result = self.runtime().run("SLICE001")
        remote = self.root / "remote.git"
        command(self.root, "git", "init", "--bare", str(remote))
        command(self.dev, "git", "remote", "add", "origin", str(remote))
        publisher = FakeGh()
        url = publisher.publish(self.dev, result)
        self.assertEqual(url, "https://github.com/example/example/pull/8")
        self.assertIn(url, publisher.body)
        marker = chr(96) * 3
        handoff = yaml.safe_load(publisher.body.split(marker + "yaml\n", 1)[1].split(marker, 1)[0])
        self.assertEqual(handoff["kind"], "DEV_HANDOFF")
        self.assertEqual(handoff["author"], "fpftest-author")
        self.assertEqual(handoff["tested_code_sha"], result["head_sha"])
        self.assertEqual(handoff["baseline_sha"], self.base)
        self.assertEqual(handoff["changed_files"], ["feature.txt"])

    def test_sdk_backend_uses_distinct_persistent_role_sessions(self):
        calls = []
        class Session:
            def __init__(self, sid, db):
                self.id = sid
                self.db = db
        class Agent:
            def __init__(self, name, instructions, model):
                self.name = name
        class Runner:
            @staticmethod
            def run_sync(agent, prompt, session):
                calls.append((agent.name, session.id, prompt))
                return types.SimpleNamespace(final_output="plan for " + agent.name)
        fake_sdk = types.SimpleNamespace(Agent=Agent, Runner=Runner, SQLiteSession=Session)
        with patch.dict(sys.modules, {"agents": fake_sdk}):
            from packages.fpf_runtime.sdk_roles import AgentsSDKRoles
            roles = AgentsSDKRoles("test-model", "SLICE001", self.root / "sessions.sqlite3")
            self.assertIn("DEV", roles.ask("DEV", "plan").text)
            self.assertIn("QA", roles.ask("QA", "review").text)
        self.assertNotEqual(calls[0][1], calls[1][1])


if __name__ == "__main__":
    unittest.main()
