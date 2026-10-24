#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Security and Boundary Unit Tests.

Enforces:
1. Object type validation (commit vs tree/blob)
2. P0 defect blocking on claimed PASS
3. Manifest SHA-256 physical recalculation
4. DEV vs QA tested SHA strict consistency
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from packages.fpf_coordinator import coordinator


class TestTrustedEvaluator(unittest.TestCase):

    def setUp(self):
        # Resolve current git HEAD
        code, out, _ = coordinator.run_cmd(["git", "rev-parse", "HEAD"])
        self.head_sha = out if code == 0 else "0000000000000000000000000000000000000000"
        self.dev_card = {
            "handoff_version": 1,
            "kind": "DEV_HANDOFF",
            "task_id": "TEST-CI-001",
            "baseline_sha": self.head_sha,
            "tested_code_sha": self.head_sha,
            "pr_url": "https://github.com/huangzuomin/five-powers-flow/pull/1",
            "scope": "Test CI Scope",
            "changed_files": ["packages/fpf-coordinator/coordinator.py"],
            "dev_checks": [{"command": "pytest", "exit_code": 0}],
            "not_run": ["e2e"],
            "known_risks": [],
            "state": "DEV_READY_FOR_QA",
        }

    def test_p0_findings_blocks_pass(self):
        qa_card = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": self.head_sha,
            "runner_sha": self.head_sha,
            "environment": "Ubuntu 22.04",
            "verdict": "PASS",
            "evidence_manifest_sha256": "a" * 64,
            "checks": [{"name": "pytest", "exit_code": 0}],
            "findings": {"p0": ["Critical SQL injection vulnerability"]},
            "next_action": "MERGE",
        }
        errors = coordinator.validate_qa_result(qa_card, dev_data=self.dev_card)
        self.assertTrue(any("unresolved P0 findings" in e for e in errors))

    def test_sha_mismatch_blocks_pass(self):
        qa_card = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": "1234567890123456789012345678901234567890",
            "runner_sha": self.head_sha,
            "environment": "Ubuntu 22.04",
            "verdict": "PASS",
            "evidence_manifest_sha256": "a" * 64,
            "checks": [{"name": "pytest", "exit_code": 0}],
            "findings": {},
            "next_action": "MERGE",
        }
        errors = coordinator.validate_qa_result(qa_card, dev_data=self.dev_card)
        self.assertTrue(any("CRITICAL DISCREPANCY" in e for e in errors))

    def test_manifest_hash_recalculation(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("genuine evidence manifest bytes")
            tf_path = Path(tf.name)

        real_hash = hashlib.sha256(b"genuine evidence manifest bytes").hexdigest()
        tampered_hash = "b" * 64

        qa_card = {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "TEST-CI-001",
            "tested_sha": self.head_sha,
            "runner_sha": self.head_sha,
            "environment": "Ubuntu 22.04",
            "verdict": "PASS",
            "evidence_manifest_sha256": tampered_hash,
            "checks": [{"name": "pytest", "exit_code": 0}],
            "findings": {},
            "next_action": "MERGE",
        }

        # Tampered hash must fail
        errors = coordinator.validate_qa_result(
            qa_card, dev_data=self.dev_card, evidence_manifest_path=tf_path
        )
        self.assertTrue(any("MANIFEST HASH MISMATCH" in e for e in errors))

        # Real hash must pass
        qa_card["evidence_manifest_sha256"] = real_hash
        ok_errors = coordinator.validate_qa_result(
            qa_card, dev_data=self.dev_card, evidence_manifest_path=tf_path
        )
        self.assertEqual(len(ok_errors), 0)


if __name__ == "__main__":
    unittest.main()
