"""Audit round five negative tests; all local and hermetic."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from packages.fpf_coordinator import coordinator
from packages.fpf_policy.protected import is_protected, is_protected_tool_path


class TestRoundFive(unittest.TestCase):
    def _evidence(self, directory: Path, profile="Library", na=False):
        ids = coordinator.REQUIRED_PROFILE_EVIDENCES[profile]
        items = []
        for eid in ids:
            filename = eid + ".log"
            digest = "0" * 64
            if not na:
                content = ("Real test example for " + eid).encode()
                (directory / filename).write_bytes(content)
                digest = hashlib.sha256(content).hexdigest()
            items.append({"id": eid, "path": filename, "sha256": digest,
                          "status": "NOT_APPLICABLE" if na else "PASS",
                          "reason": "not applicable to this test" if na else ""})
        data = {"manifest_version": 1, "task_id": "AUDIT", "profile": profile, "items": items}
        p = directory / "manifest.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def test_34_mandatory_na_cannot_count_as_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digest = self._evidence(root, na=True)
            err = coordinator.verify_evidence_directory(root, digest, "Library")
            self.assertTrue(any("Mandatory evidence cannot be NOT_APPLICABLE" in e for e in err))
            self.assertTrue(any("omitted mandatory evidence items" in e for e in err))

    def test_36_reject_unrecognized_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digest = self._evidence(root)
            self.assertTrue(any("Unsupported evidence profile" in e
                for e in coordinator.verify_evidence_directory(root, digest, "Typo-Profile")))
            self.assertFalse(coordinator.verify_evidence_directory(root, digest, "PROFILE-LIBRARY"))

    def test_37_full_stack_requires_browser_evidence(self):
        ids = coordinator.REQUIRED_PROFILE_EVIDENCES["Full-Stack"]
        self.assertEqual(len(ids), 28)
        self.assertTrue(all(f"EVID-{x:02d}" in ids for x in (21,22,23,24)))
        self.assertTrue(all(f"EVID-{x:02d}" in coordinator.REQUIRED_PROFILE_EVIDENCES["Rework"]
                            for x in (25,26,27,28)))

    def test_43_evidence_path_sibling_escape_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            evidence=root/"ev"
            sibling=root/"ev-escape"
            evidence.mkdir()
            sibling.mkdir()
            payload=b"fake evidence"
            (sibling/"secret.log").write_bytes(payload)
            sha=self._evidence(evidence)
            manifest=json.loads((evidence/"manifest.json").read_text())
            manifest["items"][0]["path"]="../ev-escape/secret.log"
            manifest["items"][0]["sha256"]=hashlib.sha256(payload).hexdigest()
            (evidence/"manifest.json").write_text(json.dumps(manifest))
            sha=hashlib.sha256((evidence/"manifest.json").read_bytes()).hexdigest()
            errors=coordinator.verify_evidence_directory(evidence,sha,"Library")
            self.assertTrue(any("Path traversal forbidden" in e for e in errors))

    def test_35_empty_not_run_is_rejected_with_any_exemption(self):
        dev={"kind":"DEV_HANDOFF","handoff_version":1,"task_id":"AUDIT",
             "baseline_sha":"0"*40,"tested_code_sha":"1"*40,
             "pr_url":"https://github.com/example/example/pull/1",
             "state":"DEV_READY_FOR_QA","author":"dev",
             "changed_files":["code.py"],"dev_checks":[{"command":"test","exit_code":0}],
             "not_run":[],"not_run_exemption_justification":"I promise everything passed"}
        e=coordinator.validate_dev_handoff(dev)
        self.assertTrue(any("not_run is empty" in x for x in e))
        self.assertTrue(any("self-attested exemptions" in x for x in e))

    def test_38_39_author_and_fixed_runner_cannot_be_self_signed(self):
        dev={"author":"dev-lead","task_id":"AUDIT","tested_code_sha":"a"*40}
        qa={"result_version":1,"kind":"QA_RESULT","task_id":"AUDIT",
            "tested_sha":"a"*40,"runner_sha":"a"*40,
            "qa_contract_sha":"a"*40,"author":"dev-lead",
            "environment":"test runner","verdict":"PASS",
            "checks":[{"name":"test","exit_code":0}],
            "evidence_manifest_sha256":"b"*64}
        e=coordinator.validate_qa_result(qa,dev_data=dev)
        self.assertTrue(any("must differ from tested_sha" in x for x in e))
        self.assertTrue(any("cannot sign as QA auditor" in x for x in e))
        e=coordinator.validate_qa_result({**qa,"author":"QA"},dev_data={**dev,"author":""})
        self.assertTrue(any("Missing required DEV/QA author" in x for x in e))

    def test_45_no_cryptographic_merge_without_git(self):
        s,msg=coordinator.compute_lifecycle_state(
            {},{"verdict":"PASS","tested_sha":"a"*40},[],[],pr_merged=True)
        self.assertEqual(s,"MERGE_UNVERIFIED")
        self.assertNotIn("verified merged",msg)

    def test_43_protected_path_policy(self):
        for path in ("AGENTS.md",".github/workflows/check.yml",".github/CODEOWNERS",
                     ".fpf/project.yaml","docs/coordination/HANDOFF-PROTOCOL.md",
                     "docs/coordination/PROJECT-MAP.md","schemas/manifest.schema.json"):
            self.assertTrue(is_protected(path),path)
        for path in ("src/agents.md","my-project-map.md","src/lessons.py"):
            self.assertFalse(is_protected(path),path)
        self.assertTrue(is_protected_tool_path("C:\\work\\repo\\.github\\CODEOWNERS"))


if __name__ == "__main__":
    unittest.main()
