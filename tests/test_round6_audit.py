"""Sixth-audit regressions. Hermetic tests do not assert real platform QA."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from packages.fpf_bootstrap.artifacts import bundle
from packages.fpf_coordinator import coordinator
from packages.fpf_policy.pr_gate import classify, _exact_card_diff, evaluate
from packages.fpf_policy.protected import is_protected
from packages.fpf_runtime.evidence_bridge import export_fpf_manifest


class TestSixthAudit(unittest.TestCase):
    def test_policy_must_not_bypass_gate_or_include_app_code(self):
        self.assertEqual(classify(["docs/SPECIFICATION.md"],"POLICY_CHANGE",set(),"fix/doc"),"POLICY_PR")
        for path in (".github/workflows/validate-handoff-cards.yml",
                     "packages/fpf_policy/pr_gate.py", "packages/fpf_bootstrap/artifacts.py",
                     "packages/fpf_runtime/github_pr.py", "tests/test_round6_audit.py"):
            self.assertEqual(classify([path],"POLICY_CHANGE",set(),"fix/audit"),"GATE_PR")
        with self.assertRaisesRegex(ValueError,"unrelated application"):
            classify(["src/payments.py"],"POLICY_CHANGE",set(),"fix/audit")
        with self.assertRaisesRegex(ValueError,"unrelated application"):
            classify([".github/CODEOWNERS","src/payments.py"],"POLICY_CHANGE",set(),"fix/audit")

    def test_policy_card_sha_and_diff_binding(self):
        head,base="a"*40,"b"*40
        card={"tested_code_sha":head,"baseline_sha":base,"changed_files":["docs/a.md"]}
        _exact_card_diff(card,["docs/a.md"],head,base)
        with self.assertRaisesRegex(ValueError,"PR HEAD"):
            _exact_card_diff({**card,"tested_code_sha":"c"*40},["docs/a.md"],head,base)
        with self.assertRaisesRegex(ValueError,"Git diff"):
            _exact_card_diff({**card,"changed_files":["docs/b.md"]},["docs/a.md"],head,base)

    def test_policy_gate_requires_two_reviewers_and_qa(self):
        head,base="a"*40,"b"*40
        payload="kind: POLICY_CHANGE\ntask_id: POLICY01\nrisk_acknowledged: true\n" + (
            "tested_code_sha: "+head+"\nbaseline_sha: "+base+
            "\nchanged_files:\n  - packages/fpf_policy/pr_gate.py\n")
        event={"pull_request":{"head":{"sha":head,"ref":"fix/policy"},
               "base":{"sha":base},"user":{"login":"dev-author"},
               "body":"\x60\x60\x60yaml\n"+payload+"\x60\x60\x60"}}
        review={"user":{"login":"qa-reviewer"},"commit_id":head,"state":"APPROVED",
                "body":"\x60\x60\x60yaml\nkind: QA_RESULT\n"
                       "author: qa-reviewer\ntask_id: POLICY01\ntested_sha: "+head+
                       "\nverdict: PASS\n\x60\x60\x60"}
        with self.assertRaisesRegex(ValueError,"second independent"):
            evaluate(event,[review],["packages/fpf_policy/pr_gate.py"],set())
        with self.assertRaisesRegex(ValueError,"No distinct"):
            evaluate(event,[],["packages/fpf_policy/pr_gate.py"],set())

    def test_bootstrap_schema_resolves_in_vendor_and_missing_fails(self):
        d={"sha":"a"*40,"base_ref":"main","tracked_files":0,"modules":[],"documents":[]}
        files=bundle("DEMO01","Demo",d,"api")
        self.assertEqual(files["schemas/manifest.schema.json"],
                         files[".fpf/vendor/schemas/manifest.schema.json"])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fake=root/".fpf/vendor/packages/fpf_coordinator/coordinator.py"
            fake.parent.mkdir(parents=True)
            schema=root/".fpf/vendor/schemas/manifest.schema.json"
            schema.parent.mkdir(parents=True)
            schema.write_text(files[".fpf/vendor/schemas/manifest.schema.json"])
            e=root/"qa"
            e.mkdir()
            m=e/"manifest.json"
            m.write_text(json.dumps({"manifest_version":1,"profile":"Library",
                         "task_id":"T01","items":[{"id":"bad"}]}))
            digest=hashlib.sha256(m.read_bytes()).hexdigest()
            with patch.object(coordinator,"__file__",str(fake)):
                first=coordinator.verify_evidence_directory(e,digest,"Library")
                self.assertTrue(any("violates schemas/" in x for x in first),first)
                schema.unlink()
                second=coordinator.verify_evidence_directory(e,digest,"Library")
                self.assertTrue(any("Manifest schema not found" in x for x in second),second)

    def test_governance_generators_are_protected(self):
        for path in ("packages/fpf_bootstrap/artifacts.py",
                     "packages/fpf_bootstrap/bootstrap.py",
                     "packages/fpf_runtime/github_pr.py",
                     "packages/fpf_runtime/runtime.py"):
            self.assertTrue(is_protected(path),path)

    def test_docs_library_profile_matches_enforcement(self):
        line=next(x for x in (Path(__file__).resolve().parents[1]/"docs/EVIDENCE-SPEC.md")
                 .read_text(encoding="utf-8").splitlines()
                 if "PROFILE-LIBRARY" in x and x.startswith("|"))
        for expected in ("A(01-04)","B(05-08)","C(09,10,12)","D(13)","H(29-32)","16 项"):
            self.assertIn(expected,line)
        self.assertEqual(len(coordinator.REQUIRED_PROFILE_EVIDENCES["Library"]),16)

    def test_evidence_index_anchor_are_exporter_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source"
            source.mkdir()
            physical={}
            for eid in set(coordinator.REQUIRED_PROFILE_EVIDENCES["Library"]) - {"EVID-31","EVID-32"}:
                path=source/(eid+".log")
                path.write_text("Observed QA execution "+eid)
                physical[eid]=path
            m,d=export_fpf_manifest(root/"out",physical,task_id="QA001",
                                    profile="Library",tested_sha="a"*40)
            self.assertFalse(coordinator.verify_evidence_directory(Path(m).parent,d,"Library"))
            self.assertTrue((Path(m).parent/"EVID-31.json").exists())
            self.assertTrue((Path(m).parent/"EVID-32.sha256").exists())
            with self.assertRaisesRegex(ValueError,"owned by"):
                export_fpf_manifest(root/"again",{**physical,"EVID-31":source/"EVID-01.log"},
                                    task_id="QA001",profile="Library")
