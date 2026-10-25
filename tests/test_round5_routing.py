"""Review provenance, PR classes and honest QA evidence interoperability tests."""
from __future__ import annotations
import hashlib
from pathlib import Path
import tempfile
import unittest
from packages.fpf_policy.pr_gate import classify, verified_reviewer
from packages.fpf_runtime.evidence_bridge import export_fpf_manifest
from packages.fpf_coordinator.coordinator import REQUIRED_PROFILE_EVIDENCES, verify_evidence_directory
from packages.fpf_bootstrap.bootstrap import doctor, apply, plan
from packages.fpf_bootstrap.discovery import git
import subprocess

class TestTrustRouting(unittest.TestCase):
    def test_code_pr_cannot_modify_policy(self):
        with self.assertRaisesRegex(ValueError, "protected"):
            classify(["src/app.py","AGENTS.md"],"DEV_HANDOFF",set(),"feat/example")
        with self.assertRaisesRegex(ValueError, "protected"):
            classify([".github/workflows/ci.yml"],"DEV_HANDOFF",set(),"feat/example")

    def test_bootstrap_pr_is_narrow_allowlist(self):
        base=set()
        good=["AGENTS.md","docs/coordination/PROJECT-MAP.md",
              ".fpf/project.yaml",".github/workflows/validate-handoff-cards.yml"]
        self.assertEqual(classify(good,"BOOTSTRAP",base,"fpf/bootstrap-myapp"),
                         "BOOTSTRAP_PR")
        with self.assertRaisesRegex(ValueError,"unauthorized"):
            classify(good+["src/new.py"],"BOOTSTRAP",base,"fpf/bootstrap-myapp")
        with self.assertRaisesRegex(ValueError,"overwrite"):
            classify(good,"BOOTSTRAP",{"AGENTS.md".lower()},"fpf/bootstrap-myapp")

    def test_qa_review_must_be_platform_authenticated_and_at_current_sha(self):
        sha="e"*40
        accepted={"user":{"login":"qa-bot"},"state":"APPROVED","commit_id":sha,
                  "body":"```yaml\nkind: QA_RESULT\nauthor: qa-bot\n"
                         "task_id: T1\ntested_sha: "+sha+"\nverdict: PASS\n```"}
        person,card=verified_reviewer([accepted],"developer",sha)
        self.assertEqual(person,"qa-bot")
        with self.assertRaises(ValueError):
            verified_reviewer([accepted],"qa-bot",sha)
        with self.assertRaises(ValueError):
            verified_reviewer([accepted],"developer","a"*40)
        with self.assertRaises(ValueError):
            verified_reviewer([{**accepted,"body":accepted["body"].replace("qa-bot","someone")}],
                              "developer",sha)

    def test_export_bridge_never_synthesizes_mandatory_qa_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            with self.assertRaisesRegex(ValueError,"required EVIDs"):
                export_fpf_manifest(base/"out",{},task_id="T1",profile="Library")
            src=base/"src"
            src.mkdir()
            files={}
            for eid in REQUIRED_PROFILE_EVIDENCES["Library"]:
                f=src/(eid+".log")
                f.write_text("Independently generated QA runner output for "+eid)
                files[eid]=f
            path,digest=export_fpf_manifest(base/"out",files,task_id="T1",profile="Library")
            self.assertFalse(verify_evidence_directory(Path(path).parent,digest,"Library"))
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
            with self.assertRaisesRegex(ValueError,"overwrite"):
                export_fpf_manifest(base/"out",files,task_id="T1",profile="Library")


if __name__ == "__main__":
    unittest.main()
