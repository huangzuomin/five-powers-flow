#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Security and Boundary Unit Tests v1.2.1.

Comprehensive test coverage across FPF RFC-001 audit boundaries:
- Issue #2 / P2-1: not_run anti-cheat & exemption matrix validation
- Issue #3: baseline_sha ancestor verification & changed_files scope audit
- Issue #4: runner_sha & qa_contract_sha mandatory cryptographic commit check
- Issue #5 / P1-3: Evidence directory profile coverage, empty manifest rejection, item sha256 recalculation
- Issue #9: extract_yaml_block active markdown parser
- Issue #17: hook_guard_dev blocking project-map & lessons mutations in Edit/Write/Bash
- Issue #19: --manifest parameter resolves containing evidence directory
- Issue #21: manifest.schema.json validation and NOT_APPLICABLE justification enforcement
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
        # Create a hermetic git repository for the test suite
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.tmpdir.name)

        coordinator.run_cmd(["git", "init", "-b", "main"], cwd=self.repo_path)
        coordinator.run_cmd(["git", "config", "user.name", "FPF Test Agent"], cwd=self.repo_path)
        coordinator.run_cmd(["git", "config", "user.email", "agent@fpf.org"], cwd=self.repo_path)
        coordinator.run_cmd(["git", "config", "commit.gpgsign", "false"], cwd=self.repo_path)

        # Baseline commit (Commit A)
        p1 = self.repo_path / "coordinator.py"
        p1.write_text("# Initial baseline code\n", encoding="utf-8")
        coordinator.run_cmd(["git", "add", "."], cwd=self.repo_path)
        coordinator.run_cmd(["git", "commit", "-m", "chore: baseline initial commit"], cwd=self.repo_path)
        _, self.parent_sha, _ = coordinator.run_cmd(["git", "rev-parse", "HEAD"], cwd=self.repo_path)

        # Tested commit (Commit B) on main
        p1.write_text("# Initial baseline code\n# Feature addition\n", encoding="utf-8")
        coordinator.run_cmd(["git", "add", "."], cwd=self.repo_path)
        coordinator.run_cmd(["git", "commit", "-m", "feat: tested feature commit"], cwd=self.repo_path)
        _, self.head_sha, _ = coordinator.run_cmd(["git", "rev-parse", "HEAD"], cwd=self.repo_path)

        self.dev_card = {
            "handoff_version": 1,
            "kind": "DEV_HANDOFF",
            "task_id": "TEST-CI-001",
            "baseline_sha": self.parent_sha,
            "tested_code_sha": self.head_sha,
            "pr_url": "https://github.com/huangzuomin/five-powers-flow/pull/1",
            "scope": "Test CI Scope",
            "changed_files": ["coordinator.py"],
            "dev_checks": [{"command": "pytest", "exit_code": 0}],
            "not_run": ["e2e full regression"],
            "known_risks": [],
            "state": "DEV_READY_FOR_QA",
            "author": "dev-test",
        }

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_issue_2_not_run_empty_without_justification_is_rejected(self):
        """Issue #2: not_run cannot be empty without an explicit justification."""
        bad_dev = {**self.dev_card, "not_run": []}
        errors = coordinator.validate_dev_handoff(bad_dev, repo_path=self.repo_path)
        self.assertTrue(any("not_run is empty" in e for e in errors))

    def test_audit_35_not_run_exemption_justification_is_rejected(self):
        """P2-1: not_run empty is accepted if legitimate exemption justification is provided."""
        valid_exempt_dev = {
            **self.dev_card,
            "not_run": [],
            "not_run_exemption_justification": "Verified 100% boundary testing across unit and integration matrix in CI.",
        }
        errors = coordinator.validate_dev_handoff(valid_exempt_dev, repo_path=self.repo_path)
        self.assertTrue(any("not_run is empty" in e for e in errors))

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
        errors = coordinator.validate_qa_result(bad_qa, dev_data=self.dev_card, repo_path=self.repo_path)
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
        errors = coordinator.validate_qa_result(qa_pass_no_dir, dev_data=self.dev_card, repo_path=self.repo_path, evidence_dir=None)
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
                "verdict": "PASS",
                "evidence_manifest_sha256": "a" * 64,
                "checks": [{"name": "pytest", "exit_code": 1}],
                "findings": {},
                "next_action": "MERGE",
            }
            errors = coordinator.validate_qa_result(qa_fail_check, dev_data=self.dev_card, repo_path=self.repo_path, evidence_dir=tmppath)
            self.assertTrue(any("failed with exit_code 1. Verdict cannot be PASS" in e for e in errors))

    def test_p0_03_empty_manifest_items_rejected(self):
        """P0-03: Empty items list in manifest.json is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            manifest_file = tmppath / "manifest.json"
            manifest_file.write_text(json.dumps({"manifest_version": 1, "task_id": "T1", "profile": "Library", "items": []}), encoding="utf-8")
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

            manifest_dict = {
                "manifest_version": 1,
                "task_id": "T-EVID",
                "profile": "Library",
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
            for evid_id in coordinator.REQUIRED_PROFILE_EVIDENCES["Library"]:
                fname = evid_id + ".log"
                f = tmppath / fname
                f.write_text(f"log data for {evid_id}", encoding="utf-8")
                h = hashlib.sha256(f.read_bytes()).hexdigest()
                items_decl.append({"id": evid_id, "path": fname, "sha256": h})

            manifest_dict = {
                "manifest_version": 1,
                "task_id": "TEST-CI-001",
                "profile": "Library",
                "items": items_decl,
            }
            manifest_file = tmppath / "manifest.json"
            manifest_file.write_text(json.dumps(manifest_dict), encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()

            qa_card = {
                "result_version": 1,
                "kind": "QA_RESULT",
                "task_id": "TEST-CI-001",
                "tested_sha": self.head_sha,
                "runner_sha": self.parent_sha,
                "qa_contract_sha": self.parent_sha,
                "profile": "Library",
                "environment": "Ubuntu 22.04",
                "verdict": "PASS",
                "evidence_manifest_sha256": manifest_sha,
                "checks": [{"name": "pytest", "exit_code": 0}],
                "findings": {},
                "next_action": "MERGE",
                "author": "qa-test",
            }

            errs = coordinator.validate_qa_result(qa_card, dev_data=self.dev_card, repo_path=self.repo_path, evidence_dir=tmppath)
            self.assertEqual(len(errs), 0)

            # Corrupting unit.log triggers item hash mismatch
            (tmppath / "unit.log").write_text("tampered log", encoding="utf-8")
            errs_corrupt = coordinator.validate_qa_result(qa_card, dev_data=self.dev_card, repo_path=self.repo_path, evidence_dir=tmppath)
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
            "author": "developer-alice",
            "environment": "Ubuntu 22.04",
            "verdict": "FAIL",
            "evidence_manifest_sha256": "a" * 64,
            "checks": [{"name": "pytest", "exit_code": 1}],
            "findings": {},
            "next_action": "REWORK",
        }
        errors = coordinator.validate_qa_result(qa_same_author, dev_data=dev_with_author, repo_path=self.repo_path)
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
            repo_path=self.repo_path,
        )
        self.assertEqual(state, "MERGED_AND_CLOSED")

    def test_p0_04_merged_rejected_when_commit_not_ancestor_of_main(self):
        """P0-04: PR merged asserted but commit is not merged into main branch."""
        # Create a detached branch with unmerged commit
        coordinator.run_cmd(["git", "checkout", "-b", "unmerged-feat"], cwd=self.repo_path)
        (self.repo_path / "feat.txt").write_text("unmerged work", encoding="utf-8")
        coordinator.run_cmd(["git", "add", "."], cwd=self.repo_path)
        coordinator.run_cmd(["git", "commit", "-m", "unmerged commit"], cwd=self.repo_path)
        _, unmerged_sha, _ = coordinator.run_cmd(["git", "rev-parse", "HEAD"], cwd=self.repo_path)
        # Switch back to main
        coordinator.run_cmd(["git", "checkout", "main"], cwd=self.repo_path)

        qa_pass = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": unmerged_sha,
            "verdict": "PASS",
        }
        state, reason = coordinator.compute_lifecycle_state(
            self.dev_card,
            qa_pass,
            [],
            [],
            pr_merged=True,
            repo_path=self.repo_path,
        )
        self.assertEqual(state, "MERGE_UNVERIFIED")
        self.assertIn("is NOT an ancestor", reason)

    def test_issue_21_not_applicable_item_requires_reason(self):
        """Issue #21: NOT_APPLICABLE status requires architectural justification in 'reason'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            manifest_dict = {
                "manifest_version": 1,
                "task_id": "T-NA",
                "profile": "Library",
                "items": [
                    {"id": "EVID-01", "path": "evid01.log", "sha256": "a"*64, "status": "NOT_APPLICABLE", "reason": "short"}
                ]
            }
            manifest_file = tmppath / "manifest.json"
            manifest_file.write_text(json.dumps(manifest_dict), encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()

            errors = coordinator.verify_evidence_directory(tmppath, manifest_sha, profile="Library")
            self.assertTrue(any("requires architectural justification in 'reason'" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
