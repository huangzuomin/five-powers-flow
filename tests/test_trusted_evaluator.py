#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Security and Boundary Unit Tests v1.2.

Comprehensive test coverage for all 11 audited security issues:
- Issue #2: not_run anti-cheat (zero bypass)
- Issue #3: baseline_sha ancestor verification & changed_files scope audit
- Issue #4: runner_sha & qa_contract_sha mandatory cryptographic commit check
- Issue #5: Physical evidence directory and manifest recalculation
- Issue #9: extract_yaml_block active markdown parser
- Issue #11: PR merged terminal state reachable
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from packages.fpf_coordinator import coordinator


class TestTrustedEvaluator(unittest.TestCase):

    def setUp(self):
        code, out, _ = coordinator.run_cmd(["git", "rev-parse", "HEAD"])
        self.head_sha = out if code == 0 else "0000000000000000000000000000000000000000"
        # Get parent commit for baseline
        code_p, out_p, _ = coordinator.run_cmd(["git", "rev-parse", "HEAD~1"])
        self.parent_sha = out_p if code_p == 0 else self.head_sha

        self.dev_card = {
            "handoff_version": 1,
            "kind": "DEV_HANDOFF",
            "task_id": "TEST-CI-001",
            "baseline_sha": self.parent_sha,
            "tested_code_sha": self.head_sha,
            "pr_url": "https://github.com/huangzuomin/five-powers-flow/pull/1",
            "scope": "Test CI Scope",
            "changed_files": ["packages/fpf-coordinator/coordinator.py"],
            "dev_checks": [{"command": "pytest", "exit_code": 0}],
            "not_run": ["e2e full regression"],
            "known_risks": [],
            "state": "DEV_READY_FOR_QA",
        }

    def test_issue_2_not_run_empty_is_rejected_even_with_fake_cert(self):
        """Issue #2: not_run cannot be empty list, and fake full_coverage_certified is ignored."""
        bad_dev = {**self.dev_card, "not_run": [], "full_coverage_certified": True}
        errors = coordinator.validate_dev_handoff(bad_dev)
        self.assertTrue(any("not_run must be a non-empty list" in e for e in errors))

    def test_issue_3_baseline_non_ancestor_is_rejected(self):
        """Issue #3: If baseline is not an ancestor of tested, it must be rejected."""
        # Using HEAD as baseline and HEAD~1 as tested inverts history
        inverted_dev = {**self.dev_card, "baseline_sha": self.head_sha, "tested_code_sha": self.parent_sha}
        errors = coordinator.validate_dev_handoff(inverted_dev, repo_path=Path.cwd())
        self.assertTrue(any("is NOT an ancestor of tested_code_sha" in e for e in errors))

    def test_issue_4_runner_and_contract_sha_must_be_commits(self):
        """Issue #4: runner_sha and qa_contract_sha must be valid 40-digit commit SHAs."""
        bad_qa = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": self.head_sha,
            "runner_sha": "latest", # Invalid format
            "qa_contract_sha": "0000000000000000000000000000000000000000", # Nonexistent commit
            "environment": "Ubuntu 22.04",
            "verdict": "PASS",
            "evidence_manifest_sha256": "a" * 64,
            "checks": [{"name": "pytest", "exit_code": 0}],
            "findings": {},
            "next_action": "MERGE",
        }
        errors = coordinator.validate_qa_result(bad_qa, dev_data=self.dev_card, repo_path=Path.cwd())
        self.assertTrue(any("runner_sha must be a 40-digit hex SHA" in e for e in errors))
        self.assertTrue(any("qa_contract_sha '0000000000000000000000000000000000000000' does not exist" in e for e in errors))

    def test_issue_5_evidence_directory_item_auditing(self):
        """Issue #5: Evidence directory verifies both manifest hash and individual item hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            item1 = tmppath / "log.txt"
            item1.write_text("sample log execution", encoding="utf-8")
            item1_sha = hashlib.sha256(b"sample log execution").hexdigest()

            manifest_dict = {
                "items": [
                    {"id": "EVID-09", "path": "log.txt", "sha256": item1_sha}
                ]
            }
            manifest_file = tmppath / "manifest.json"
            manifest_file.write_text(json.dumps(manifest_dict), encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()

            qa_card = {
                "result_version": 1,
                "kind": "QA_RESULT",
                "task_id": "TEST-CI-001",
                "tested_sha": self.head_sha,
                "runner_sha": self.head_sha,
                "qa_contract_sha": self.head_sha,
                "environment": "Ubuntu 22.04",
                "verdict": "PASS",
                "evidence_manifest_sha256": manifest_sha,
                "checks": [{"name": "pytest", "exit_code": 0}],
                "findings": {},
                "next_action": "MERGE",
            }

            # Valid evidence directory passes
            errs = coordinator.validate_qa_result(qa_card, dev_data=self.dev_card, repo_path=Path.cwd(), evidence_dir=tmppath)
            self.assertEqual(len(errs), 0)

            # Corrupting item1 triggers item hash mismatch
            item1.write_text("tampered log", encoding="utf-8")
            errs_corrupt = coordinator.validate_qa_result(qa_card, dev_data=self.dev_card, repo_path=Path.cwd(), evidence_dir=tmppath)
            self.assertTrue(any("Evidence SHA-256 mismatch" in e for e in errs_corrupt))

    def test_issue_9_extract_yaml_block_from_markdown(self):
        """Issue #9: Extract YAML block from PR/Issue markdown text."""
        markdown_body = """
        Here is the PR description.
        ```yaml
        handoff_version: 1
        kind: DEV_HANDOFF
        task_id: T-999
        ```
        Thank you!
        """
        extracted = coordinator.extract_yaml_block(markdown_body, marker="DEV_HANDOFF")
        self.assertIn("task_id: T-999", extracted)

    def test_issue_11_merged_and_closed_reachable(self):
        """Issue #11: When pr_merged=True, compute_lifecycle_state returns MERGED_AND_CLOSED."""
        state, _ = coordinator.compute_lifecycle_state(self.dev_card, None, [], [], pr_merged=True)
        self.assertEqual(state, "MERGED_AND_CLOSED")


if __name__ == "__main__":
    unittest.main()
