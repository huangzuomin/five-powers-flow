"""Squash PR merge verification cannot be inferred solely from commit ancestry."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from packages.fpf_coordinator import coordinator

class TestMergeProvenance(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.repo=Path(self.t.name)
        for args in (
            ["git","init","-b","main"],
            ["git","config","user.name","FPF QA"],
            ["git","config","user.email","qa@example.invalid"],
        ):
            self.assertEqual(coordinator.run_cmd(args,self.repo)[0],0)
        (self.repo/"main.txt").write_text("initial")
        coordinator.run_cmd(["git","add","."],self.repo)
        coordinator.run_cmd(["git","commit","-m","baseline"],self.repo)
        self.base=coordinator.run_cmd(["git","rev-parse","HEAD"],self.repo)[1]
        coordinator.run_cmd(["git","checkout","-b","feature"],self.repo)
        (self.repo/"feature.txt").write_text("feature")
        coordinator.run_cmd(["git","add","."],self.repo)
        coordinator.run_cmd(["git","commit","-m","feature"],self.repo)
        self.tested=coordinator.run_cmd(["git","rev-parse","HEAD"],self.repo)[1]
        coordinator.run_cmd(["git","checkout","main"],self.repo)
        coordinator.run_cmd(["git","merge","--squash","feature"],self.repo)
        coordinator.run_cmd(["git","commit","-m","squash"],self.repo)
        self.merged=coordinator.run_cmd(["git","rev-parse","HEAD"],self.repo)[1]
    def tearDown(self):
        self.t.cleanup()

    def test_asserted_merge_only_rejects_nonancestor_sha(self):
        state,msg=coordinator.compute_lifecycle_state(
            {},{"verdict":"PASS","tested_sha":self.tested},
            [],[],pr_merged=True,repo_path=self.repo)
        self.assertEqual(state,"MERGE_UNVERIFIED")

    def test_verified_merge_commit_allows_actual_squash(self):
        state,msg=coordinator.compute_lifecycle_state(
            {},{"verdict":"PASS","tested_sha":self.tested},
            [],[],pr_merged=True,repo_path=self.repo,
            verified_merge_sha=self.merged)
        self.assertEqual(state,"MERGED_AND_CLOSED")
        self.assertIn("GitHub",msg)

    def test_gh_head_mismatch_rejected(self):
        gh={"state":"MERGED","mergedAt":"2026-10-25T03:00:00Z",
            "headRefOid":self.tested,"mergeCommit":{"oid":self.merged}}
        with patch.object(coordinator,"run_cmd",
                          return_value=(0,json.dumps(gh),"")):
            verified,_,msg=coordinator.verify_github_pr_merge(
                "12",expected_tested_sha=self.base)
            self.assertFalse(verified)
            self.assertIn("head",msg)

    def test_gh_exact_head_allows_merge_commit_proof(self):
        gh={"state":"MERGED","mergedAt":"2026-10-25T03:00:00Z",
            "headRefOid":self.tested,"mergeCommit":{"oid":self.merged}}
        with patch.object(coordinator,"run_cmd",
                          return_value=(0,json.dumps(gh),"")):
            verified,merged,msg=coordinator.verify_github_pr_merge(
                "12",expected_tested_sha=self.tested)
            self.assertTrue(verified)
            self.assertEqual(merged,self.merged)

if __name__=="__main__":
    unittest.main()
