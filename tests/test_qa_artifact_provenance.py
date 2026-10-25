"""Fifth-audit authenticated artifact runner provenance — hermetic negative tests."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from packages.fpf_policy.qa_artifact import independent_qa_evidence
from packages.fpf_coordinator.coordinator import REQUIRED_PROFILE_EVIDENCES
from packages.fpf_runtime.evidence_bridge import export_fpf_manifest


class TestIndependentQAArtifact(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sha = "f" * 40
        self.qa = {"qa_run_id": 1001, "qa_artifact_id": 2234,
                   "profile": "Library", "evidence_manifest_sha256": ""}
        self.run = {
            "conclusion": "success", "status": "completed", "event": "workflow_dispatch",
            "actor": {"login": "qa-reviewer"}, "triggering_actor": {"login": "qa-reviewer"},
            "path": "org/project/.github/workflows/fpf-independent-qa.yml",
            "head_sha": "a" * 40,
        }
        self.artifact = {
            "expired": False, "name": "fpf-qa-" + self.sha,
            "workflow_run": {"id": 1001},
        }

    def tearDown(self):
        self.temp.cleanup()

    def evidence_zip(self):
        src = self.root / "original"
        src.mkdir()
        physical = {}
        for evid in REQUIRED_PROFILE_EVIDENCES["Library"]:
            file = src / (evid + ".log")
            file.write_text("Real separate QA command log for " + evid, encoding="utf-8")
            physical[evid] = file
        p, claimed = export_fpf_manifest(
            self.root / "export", physical, task_id="T1",
            profile="Library", tested_sha=self.sha)
        self.qa["evidence_manifest_sha256"] = claimed
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as z:
            for f in Path(p).parent.iterdir():
                z.write(f, arcname=f.name)
        return payload.getvalue()

    def verify(self, body, run=None, artifact=None):
        run = run if run is not None else self.run
        artifact = artifact if artifact is not None else self.artifact

        def api(repo, path, token):
            if path == "actions/runs/1001":
                return run
            if path == "actions/artifacts/2234":
                return artifact
            raise AssertionError("Unexpected API endpoint")
        with patch("packages.fpf_policy.qa_artifact.api_json", side_effect=api), \
             patch("packages.fpf_policy.qa_artifact.download_zip", return_value=body), \
             patch("packages.fpf_policy.qa_artifact.ancestor", return_value=True):
            with independent_qa_evidence(
                repo="org/project", qa=self.qa, reviewer="qa-reviewer",
                tested_sha=self.sha, task_id="T1", token="test-token",
                repository_dir=self.root,
            ) as d:
                self.assertTrue((d / "manifest.json").exists())

    def test_trusted_run_and_exact_commit_artifact(self):
        self.verify(self.evidence_zip())

    def test_wrong_review_actor_is_rejected(self):
        z=self.evidence_zip()
        with self.assertRaisesRegex(ValueError, "actor differs"):
            self.verify(z, run={**self.run,"actor":{"login":"dev-author"}})

    def test_rerun_by_different_actor_rejected(self):
        z=self.evidence_zip()
        with self.assertRaisesRegex(ValueError, "re-run"):
            self.verify(z, run={**self.run,"triggering_actor":{"login":"dev-author"}})

    def test_non_dispatched_workflow_rejected(self):
        z=self.evidence_zip()
        with self.assertRaisesRegex(ValueError, "dispatched"):
            self.verify(z, run={**self.run,"event":"pull_request"})

    def test_wrong_artifact_ownership_rejected(self):
        z=self.evidence_zip()
        with self.assertRaisesRegex(ValueError, "Artifact identity"):
            self.verify(z, artifact={**self.artifact, "workflow_run":{"id":2}})

    def test_wrong_code_sha_in_artifact_rejected(self):
        z=self.evidence_zip()
        self.qa["evidence_manifest_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError, "Rejected independent QA manifest"):
            self.verify(z)

    def test_missing_run_ids_rejected(self):
        self.qa.pop("qa_run_id")
        with self.assertRaisesRegex(ValueError, "qa_run_id"):
            self.verify(b"")


if __name__ == "__main__":
    unittest.main()
