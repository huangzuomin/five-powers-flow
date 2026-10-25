"""Independent QA collector's actual command execution and exact-SHA tests."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from packages.fpf_coordinator.coordinator import (
    REQUIRED_PROFILE_EVIDENCES, verify_evidence_directory
)
from packages.fpf_policy.qa_collector import collect


class TestTrustedQACollector(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.repo=root/"candidate"
        self.repo.mkdir()
        for argv in (
            ["git","init","-b","main"],
            ["git","config","user.name","CI Tester"],
            ["git","config","user.email","qa@example.invalid"],
        ):
            subprocess.run(argv,cwd=self.repo,check=True,capture_output=True)
        (self.repo/"project.py").write_text("print('ok')\n",encoding="utf-8")
        subprocess.run(["git","add","."],cwd=self.repo,check=True,capture_output=True)
        subprocess.run(["git","commit","-m","baseline"],cwd=self.repo,check=True,capture_output=True)
        self.sha=subprocess.check_output(["git","rev-parse","HEAD"],cwd=self.repo,text=True).strip()
        self.out=root/"out"
        self.plan=root/"qa-plan.json"
        commands={}
        for evid in REQUIRED_PROFILE_EVIDENCES["Library"]:
            if evid not in ("EVID-31","EVID-32"):
                commands[evid]=[sys.executable,"-c","print('Real command executed')"]
        self.commands=commands
        self.plan.write_text(json.dumps({"commands":commands}),encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_collect_real_command_outputs_and_hashed_manifest(self):
        digest=collect(self.plan,self.repo,self.out,"T001",self.sha,"Library")
        self.assertFalse(verify_evidence_directory(self.out,digest,"Library"))
        item=json.loads((self.out/"manifest.json").read_text())
        self.assertEqual(item["tested_sha"],self.sha)
        self.assertIn("Real command executed",(self.out/"EVID-01.log").read_text())
        self.assertIn("exit_code", (self.out/"EVID-01.log").read_text())

    def test_missing_mandatory_command_rejected(self):
        self.commands.pop("EVID-09")
        self.plan.write_text(json.dumps({"commands":self.commands}),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"lacks required"):
            collect(self.plan,self.repo,self.out,"T001",self.sha,"Library")

    def test_failed_subprocess_rejected(self):
        self.commands["EVID-01"]=[sys.executable,"-c","raise SystemExit(7)"]
        self.plan.write_text(json.dumps({"commands":self.commands}),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"nonzero exit"):
            collect(self.plan,self.repo,self.out,"T001",self.sha,"Library")

    def test_red_replay_requires_expected_nonzero_failure(self):
        self.commands = {
            k: ([sys.executable, "-c", "raise SystemExit(3)"] if k=="EVID-26"
                else [sys.executable, "-c", "print('executed')"])
            for k in REQUIRED_PROFILE_EVIDENCES["Rework"]
            if k not in ("EVID-31","EVID-32")
        }
        self.plan.write_text(json.dumps({
            "commands": self.commands,
            "expected_exit_codes": {"EVID-26":3},
        }),encoding="utf-8")
        digest=collect(self.plan,self.repo,self.out,"T001",self.sha,"Rework")
        self.assertFalse(verify_evidence_directory(self.out,digest,"Rework"))
        self.assertIn('"exit_code": 3',(self.out/"EVID-26.log").read_text())

    def test_red_replay_cannot_pass_with_zero_exit(self):
        self.commands.update({
            k: [sys.executable, "-c", "print('not red')"]
            for k in REQUIRED_PROFILE_EVIDENCES["Rework"]
        })
        self.commands.pop("EVID-31",None)
        self.commands.pop("EVID-32",None)
        self.plan.write_text(json.dumps({
            "commands":self.commands,"expected_exit_codes":{"EVID-26":3}
        }),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"trusted expected exit"):
            collect(self.plan,self.repo,self.out,"T001",self.sha,"Rework")

    def test_wrong_head_rejected(self):
        with self.assertRaisesRegex(ValueError,"HEAD differs"):
            collect(self.plan,self.repo,self.out,"T001","f"*40,"Library")


if __name__=="__main__":
    unittest.main()
