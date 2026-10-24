#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Security and Boundary Unit Tests v1.2.1.

Comprehensive test coverage across FPF RFC-001 audit boundaries:
- Issue #2 / P2-1: not_run anti-cheat & exemption matrix validation
- Issue #3: baseline_sha ancestor verification & changed_files scope audit
- Issue #4: runner_sha & qa_contract_sha mandatory cryptographic commit check
- Issue #5 / P1-3: Evidence directory profile coverage, empty manifest rejection, item sha256 recalculation
- Issue #9: extract_yaml_block active markdown parser
- P0-03: checks exit code enforcement for PASS verdict & mandatory evidence-dir
- P0-04: compute_lifecycle_state fail-closed precedence and cryptographic merge reachability
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
            "changed_files": ["packages/fpf_coordinator/coordinator.py"],
            "dev_checks": [{"command": "pytest", "exit_code": 0}],
            "not_run": ["e2e full regression"],
            "known_risks": [],
            "state": "DEV_READY_FOR_QA",
        }

    def test_issue_2_not_run_empty_without_justification_is_rejected(self):
        """Issue #2: not_run cannot be empty without an explicit justification."""
        bad_dev = {**self.dev_card, "not_run": []}
        errors = coordinator.validate_dev_handoff(bad_dev)
        self.assertTrue(any("not_run is empty" in e for e in errors))

    def test_p2_1_not_run_with_exemption_justification_accepted(self):
        """P2-1: not_run empty is accepted if legitimate exemption justification is provided."""
        valid_exempt_dev = {
            **self.dev_card,
            "not_run": [],
            "not_run_exemption_justification": "Verified 100% boundary testing across unit and integration matrix in CI.",
        }
        errors = coordinator.validate_dev_handoff(valid_exempt_dev, repo_path=Path.cwd())
        # Should not have not_run errors
        self.assertFalse(any("not_run is empty" in e for e in errors))

    def test_issue_3_baseline_non_ancestor_is_rejected(self):
        """Issue #3: If baseline is not an ancestor of tested, it must be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            coordinator.run_cmd(["git", "init"], cwd=tmppath)
            coordinator.run_cmd(["git", "config", "user.name", "CI Tester"], cwd=tmppath)
            coordinator.run_cmd(["git", "config", "user.email", "ci@example.com"], cwd=tmppath)
            coordinator.run_cmd(["git", "config", "commit.gpgsign", "false"], cwd=tmppath)

            (tmppath / "file.txt").write_text("commit A", encoding="utf-8")
            coordinator.run_cmd(["git", "add", "."], cwd=tmppath)
            coordinator.run_cmd(["git", "commit", "-m", "commit A"], cwd=tmppath)
            _, sha_a, _ = coordinator.run_cmd(["git", "rev-parse", "HEAD"], cwd=tmppath)

            (tmppath / "file.txt").write_text("commit B", encoding="utf-8")
            coordinator.run_cmd(["git", "add", "."], cwd=tmppath)
            coordinator.run_cmd(["git", "commit", "-m", "commit B"], cwd=tmppath)
            _, sha_b, _ = coordinator.run_cmd(["git", "rev-parse", "HEAD"], cwd=tmppath)

            inverted_dev = {
                **self.dev_card,
                "baseline_sha": sha_b,
                "tested_code_sha": sha_a,
                "changed_files": ["file.txt"],
            }
            errors = coordinator.validate_dev_handoff(inverted_dev, repo_path=tmppath)
            self.assertTrue(any("is NOT an ancestor of tested_code_sha" in e for e in errors))

    def test_issue_4_runner_and_contract_sha_must_be_commits(self):
        """Issue #4: runner_sha and qa_contract_sha must be valid 40-digit commit SHAs."""
        bad_qa = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": self.head_sha,
            "runner_sha": "latest",
            "qa_contract_sha": "0000000000000000000000000000000000000000",
            "environment": "Ubuntu 22.04",
            "verdict": "FAIL",
            "evidence_manifest_sha256": "a" * 64,
            "checks": [{"name": "pytest", "exit_code": 1}],
            "findings": {},
            "next_action": "REWORK",
        }
        errors = coordinator.validate_qa_result(bad_qa, dev_data=self.dev_card, repo_path=Path.cwd())
        self.assertTrue(any("runner_sha must be a 40-digit hex SHA" in e for e in errors))
        self.assertTrue(any("qa_contract_sha '0000000000000000000000000000000000000000' does not exist" in e for e in errors))

    def test_p0_03_qa_pass_requires_evidence_directory(self):
        """P0-03: QA verdict PASS strictly requires a physical evidence directory."""
        qa_pass_no_dir = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": self.head_sha,
            "runner_sha": self.head_sha,
            "qa_contract_sha": self.head_sha,
            "environment": "Ubuntu 22.04",
            "verdict": "PASS",
            "evidence_manifest_sha256": "a" * 64,
            "checks": [{"name": "pytest", "exit_code": 0}],
            "findings": {},
            "next_action": "MERGE",
        }
        errors = coordinator.validate_qa_result(qa_pass_no_dir, dev_data=self.dev_card, repo_path=Path.cwd(), evidence_dir=None)
        self.assertTrue(any("strictly requires physical evidence directory" in e for e in errors))

    def test_p0_03_nonzero_exit_code_rejects_pass(self):
        """P0-03: Non-zero exit code in executed checks strictly rejects PASS verdict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            qa_fail_check = {
                "result_version": 1,
                "kind": "QA_RESULT",
                "task_id": "TEST-CI-001",
                "tested_sha": self.head_sha,
                "runner_sha": self.head_sha,
                "qa_contract_sha": self.head_sha,
                "environment": "Ubuntu 22.04",
                "verdict": "PASS", # Claiming PASS fraudulently
                "evidence_manifest_sha256": "a" * 64,
                "checks": [{"name": "pytest", "exit_code": 1}], # But exit code was 1!
                "findings": {},
                "next_action": "MERGE",
            }
            errors = coordinator.validate_qa_result(qa_fail_check, dev_data=self.dev_card, repo_path=Path.cwd(), evidence_dir=tmppath)
            self.assertTrue(any("failed with exit_code 1. Verdict cannot be PASS" in e for e in errors))

    def test_p0_03_empty_manifest_items_rejected(self):
        """P0-03: Empty items list in manifest.json is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            manifest_file = tmppath / "manifest.json"
            manifest_file.write_text(json.dumps({"items": []}), encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()

            errors = coordinator.verify_evidence_directory(tmppath, manifest_sha, profile="Library")
            self.assertTrue(any("items' list cannot be empty" in e for e in errors))

    def test_p1_03_profile_missing_mandatory_evidences_rejected(self):
        """P1-03: Evidence manifest missing required profile items is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            f1 = tmppath / "evid01.log"
            f1.write_text("test logs", encoding="utf-8")
            h1 = hashlib.sha256(b"test logs").hexdigest()

            # Library profile requires EVID-01, EVID-04, EVID-09; here we omit EVID-04 and EVID-09
            manifest_dict = {
                "items": [{"id": "EVID-01", "path": "evid01.log", "sha256": h1}]
            }
            manifest_file = tmppath / "manifest.json"
            manifest_file.write_text(json.dumps(manifest_dict), encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()

            errors = coordinator.verify_evidence_directory(tmppath, manifest_sha, profile="Library")
            self.assertTrue(any("omitted mandatory evidence items" in e for e in errors))

    def test_issue_5_evidence_directory_full_profile_auditing(self):
        """Issue #5: Evidence directory verifies manifest hash, individual items, and profile coverage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            items_decl = []
            for evid_id, fname in [("EVID-01", "unit.log"), ("EVID-04", "exit_codes.log"), ("EVID-09", "lint.log")]:
                f = tmppath / fname
                f.write_text(f"log data for {evid_id}", encoding="utf-8")
                h = hashlib.sha256(f.read_bytes()).hexdigest()
                items_decl.append({"id": evid_id, "path": fname, "sha256": h})

            manifest_file = tmppath / "manifest.json"
            manifest_file.write_text(json.dumps({"items": items_decl}), encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()

            qa_card = {
                "result_version": 1,
                "kind": "QA_RESULT",
                "task_id": "TEST-CI-001",
                "tested_sha": self.head_sha,
                "runner_sha": self.head_sha,
                "qa_contract_sha": self.head_sha,
                "profile": "Library",
                "environment": "Ubuntu 22.04",
                "verdict": "PASS",
                "evidence_manifest_sha256": manifest_sha,
                "checks": [{"name": "pytest", "exit_code": 0}],
                "findings": {},
                "next_action": "MERGE",
            }

            errs = coordinator.validate_qa_result(qa_card, dev_data=self.dev_card, repo_path=Path.cwd(), evidence_dir=tmppath)
            self.assertEqual(len(errs), 0)

            # Corrupting unit.log triggers item hash mismatch
            (tmppath / "unit.log").write_text("tampered log", encoding="utf-8")
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

    def test_p1_02_dev_author_equals_qa_author_rejected(self):
        """P1-02: Separation of Powers: DEV author cannot sign as QA auditor."""
        dev_with_author = {**self.dev_card, "author": "developer-alice"}
        qa_same_author = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": self.head_sha,
            "runner_sha": self.head_sha,
            "qa_contract_sha": self.head_sha,
            "author": "developer-alice", # Same person!
            "environment": "Ubuntu 22.04",
            "verdict": "FAIL",
            "evidence_manifest_sha256": "a" * 64,
            "checks": [{"name": "pytest", "exit_code": 1}],
            "findings": {},
            "next_action": "REWORK",
        }
        errors = coordinator.validate_qa_result(qa_same_author, dev_data=dev_with_author, repo_path=Path.cwd())
        self.assertTrue(any("cannot sign as QA auditor" in e for e in errors))

    def test_p0_04_merged_fails_closed_when_errors_exist(self):
        """P0-04: PR merged assertion fails-closed if validation errors are present."""
        state, _ = coordinator.compute_lifecycle_state(
            self.dev_card,
            None,
            dev_errors=["baseline_sha format error"],
            qa_errors=[],
            pr_merged=True,
        )
        self.assertEqual(state, "DEV_REJECTED")

    def test_p0_04_merged_requires_qa_pass_and_ancestry(self):
        """P0-04: PR merged requires QA PASS and returns MERGED_AND_CLOSED if commit is ancestor."""
        qa_pass = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": self.head_sha,
            "verdict": "PASS",
        }
        state, reason = coordinator.compute_lifecycle_state(
            self.dev_card,
            qa_pass,
            [],
            [],
            pr_merged=True,
            repo_path=Path.cwd(),
        )
        self.assertEqual(state, "MERGED_AND_CLOSED")


if __name__ == "__main__":
    unittest.main()
