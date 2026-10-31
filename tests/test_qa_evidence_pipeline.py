"""Comprehensive unit tests for FPF independent QA evidence pipeline and reviewer gates."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.request
from unittest.mock import MagicMock, patch
import zipfile

from packages.fpf_policy.qa_artifact import (
    _NoAuthRedirectHandler,
    check_dev_branch_decoupling,
    independent_qa_evidence,
    verify_artifact_sha256,
)
from packages.fpf_policy.pr_gate import evaluate, verified_reviewer


class TestArtifactVerification(unittest.TestCase):
    """Test cryptographic artifact integrity and S3 credential protection."""

    def test_verify_artifact_sha256_success(self):
        payload = b"test artifact payload zip content"
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        verify_artifact_sha256(payload, digest)  # Should not raise

    def test_verify_artifact_sha256_tampered_fails(self):
        payload = b"original content"
        tampered = b"tampered content"
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        with self.assertRaises(ValueError) as ctx:
            verify_artifact_sha256(tampered, digest)
        self.assertIn("does not match", str(ctx.exception))

    def test_verify_artifact_sha256_invalid_format_fails(self):
        with self.assertRaises(ValueError) as ctx:
            verify_artifact_sha256(b"content", "not_a_valid_sha256")
        self.assertIn("missing or invalid", str(ctx.exception))

    def test_no_auth_redirect_handler_strips_auth(self):
        handler = _NoAuthRedirectHandler()
        req = urllib.request.Request("https://api.github.com/artifact", headers={
            "Authorization": "Bearer secret_token",
            "User-Agent": "FPF-QA",
        })
        redirected = handler.redirect_request(
            req, None, 302, "Found", {}, "https://s3.amazonaws.com/presigned-url"
        )
        self.assertNotIn("authorization", [k.lower() for k in redirected.headers])
        self.assertIn("user-agent", [k.lower() for k in redirected.headers])


class TestDevBranchDecoupling(unittest.TestCase):
    """Verify candidate DEV workspace decoupling from QA evidence."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="fpf-decouple-test-")
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_workspace_passes(self):
        (self.root / "src").mkdir()
        (self.root / "src" / "code.py").write_text("print('hello')", encoding="utf-8")
        violations = check_dev_branch_decoupling(self.root)
        self.assertEqual(len(violations), 0)

    def test_inlined_qa_artifact_detected(self):
        (self.root / "qa-artifact").mkdir()
        (self.root / "qa-artifact" / "manifest.json").write_text("{}", encoding="utf-8")
        violations = check_dev_branch_decoupling(self.root)
        self.assertEqual(len(violations), 1)
        self.assertIn("Inlined QA evidence found", violations[0])

    def test_inlined_qa_manifest_detected(self):
        (self.root / "qa-manifest.json").write_text("{}", encoding="utf-8")
        violations = check_dev_branch_decoupling(self.root)
        self.assertEqual(len(violations), 1)
        self.assertIn("qa-manifest.json", violations[0])


class TestDualReviewerGates(unittest.TestCase):
    """Verify PR gate dual-reviewer and sovereign override rules."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="fpf-gate-test-")
        self.repo_dir = Path(self.temp_dir.name)
        # Initialize git repo in temp dir
        import subprocess
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir, capture_output=True, check=True)
        (self.repo_dir / "README.md").write_text("# Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo_dir, capture_output=True, check=True)
        self.head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_verified_reviewer_finds_approved_qa_result(self):
        reviews = [
            {
                "user": {"login": "fpf-qa-bot"},
                "state": "APPROVED",
                "commit_id": self.head_sha,
                "body": f"""```yaml
kind: QA_RESULT
task_id: TASK-100
tested_sha: {self.head_sha}
verdict: PASS
author: fpf-qa-bot
```""",
            }
        ]
        reviewer, qa = verified_reviewer(reviews, pr_author="dev-author", sha=self.head_sha)
        self.assertEqual(reviewer, "fpf-qa-bot")
        self.assertEqual(qa["task_id"], "TASK-100")

    def test_author_self_approval_rejected(self):
        reviews = [
            {
                "user": {"login": "dev-author"},
                "state": "APPROVED",
                "commit_id": self.head_sha,
                "body": f"""```yaml
kind: QA_RESULT
task_id: TASK-100
tested_sha: {self.head_sha}
verdict: PASS
author: dev-author
```""",
            }
        ]
        with self.assertRaises(ValueError) as ctx:
            verified_reviewer(reviews, pr_author="dev-author", sha=self.head_sha)
        self.assertIn("No distinct GitHub-authenticated APPROVED QA_RESULT", str(ctx.exception))

    @patch("packages.fpf_policy.qa_artifact.independent_qa_evidence")
    @patch("packages.fpf_coordinator.coordinator.validate_qa_result")
    def test_gate_pr_dual_approved_succeeds(self, mock_validate, mock_evidence):
        mock_evidence.return_value.__enter__.return_value = self.repo_dir
        mock_validate.return_value = []

        files = ["packages/fpf_policy/pr_gate.py"]
        event = {
            "pull_request": {
                "head": {"sha": self.head_sha, "ref": "feat/policy-change"},
                "base": {"sha": self.head_sha},
                "user": {"login": "author-user"},
                "body": f"""```yaml
kind: POLICY_CHANGE
task_id: TASK-GATE-1
risk_acknowledged: true
baseline_sha: {self.head_sha}
tested_code_sha: {self.head_sha}
changed_files:
  - packages/fpf_policy/pr_gate.py
```""",
            }
        }
        reviews = [
            {
                "user": {"login": "qa-bot"},
                "state": "APPROVED",
                "commit_id": self.head_sha,
                "body": f"""```yaml
kind: QA_RESULT
task_id: TASK-GATE-1
tested_sha: {self.head_sha}
verdict: PASS
author: qa-bot
```""",
            },
            {
                "user": {"login": "human-sec-reviewer"},
                "state": "APPROVED",
                "commit_id": self.head_sha,
                "body": "LGTM",
            },
        ]
        os.environ["GITHUB_REPOSITORY"] = "org/repo"
        os.environ["FPF_CANDIDATE_REPO"] = str(self.repo_dir)

        res = evaluate(event, reviews, files, set(files))
        self.assertIn("independently QA verified and dual-approved", res)

    @patch("packages.fpf_policy.qa_artifact.independent_qa_evidence")
    @patch("packages.fpf_coordinator.coordinator.validate_qa_result")
    def test_gate_pr_missing_second_fails_without_sovereign_override(self, mock_validate, mock_evidence):
        mock_evidence.return_value.__enter__.return_value = self.repo_dir
        mock_validate.return_value = []

        files = ["packages/fpf_policy/pr_gate.py"]
        event = {
            "pull_request": {
                "head": {"sha": self.head_sha, "ref": "feat/policy-change"},
                "base": {"sha": self.head_sha},
                "user": {"login": "author-user"},
                "body": f"""```yaml
kind: POLICY_CHANGE
task_id: TASK-GATE-2
risk_acknowledged: true
baseline_sha: {self.head_sha}
tested_code_sha: {self.head_sha}
changed_files:
  - packages/fpf_policy/pr_gate.py
```""",
            }
        }
        reviews = [
            {
                "user": {"login": "qa-bot"},
                "state": "APPROVED",
                "commit_id": self.head_sha,
                "body": f"""```yaml
kind: QA_RESULT
task_id: TASK-GATE-2
tested_sha: {self.head_sha}
verdict: PASS
author: qa-bot
```""",
            }
        ]
        os.environ["GITHUB_REPOSITORY"] = "org/repo"
        os.environ["FPF_CANDIDATE_REPO"] = str(self.repo_dir)

        with self.assertRaises(ValueError) as ctx:
            evaluate(event, reviews, files, set(files))
        self.assertIn("requires second independent APPROVED review", str(ctx.exception))

    @patch("packages.fpf_policy.qa_artifact.independent_qa_evidence")
    @patch("packages.fpf_coordinator.coordinator.validate_qa_result")
    def test_gate_pr_sovereign_override_succeeds(self, mock_validate, mock_evidence):
        mock_evidence.return_value.__enter__.return_value = self.repo_dir
        mock_validate.return_value = []

        files = ["packages/fpf_policy/pr_gate.py"]
        event = {
            "pull_request": {
                "head": {"sha": self.head_sha, "ref": "feat/policy-change"},
                "base": {"sha": self.head_sha},
                "user": {"login": "author-user"},
                "body": f"""```yaml
kind: POLICY_CHANGE
task_id: TASK-GATE-3
risk_acknowledged: true
sovereign_override: true
sovereign_authorizer: author-user
baseline_sha: {self.head_sha}
tested_code_sha: {self.head_sha}
changed_files:
  - packages/fpf_policy/pr_gate.py
```""",
            }
        }
        reviews = [
            {
                "user": {"login": "qa-bot"},
                "state": "APPROVED",
                "commit_id": self.head_sha,
                "body": f"""```yaml
kind: QA_RESULT
task_id: TASK-GATE-3
tested_sha: {self.head_sha}
verdict: PASS
author: qa-bot
```""",
            }
        ]
        os.environ["GITHUB_REPOSITORY"] = "org/repo"
        os.environ["FPF_CANDIDATE_REPO"] = str(self.repo_dir)

        res = evaluate(event, reviews, files, set(files))
        self.assertIn("independently QA verified with human sovereign override", res)


if __name__ == "__main__":
    unittest.main()
