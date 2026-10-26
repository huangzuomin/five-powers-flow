"""Issue #61 reviewer regressions; fake runs do not constitute independent QA."""
import hashlib
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import yaml
from packages.fpf_coordinator.dispatch.scope_grant import resolve_scope_grant
from packages.fpf_coordinator.dispatch.github_records import from_github_records,parse_card
from packages.fpf_coordinator.dispatch.core import CanonicalSnapshot,Target,next_action,make_packet
from packages.fpf_coordinator.dispatch.journal import DispatchJournal
from packages.fpf_coordinator.dispatch.controller import Coordinator
from packages.fpf_coordinator.dispatch.runner import CoordinationRunner
from packages.fpf_coordinator.dispatch.transports import CodexThreadBridge

def fenced(card):
    return chr(96)*3+"yaml\n"+yaml.safe_dump(card,sort_keys=False)+chr(96)*3

class GitScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.repo=Path(self.tmp.name)
        self.git("init","-b","main")
        self.git("config","user.name","Reviewer")
        self.git("config","user.email","test@example.invalid")
        (self.repo/"base.txt").write_text("base")
        self.git("add",".");self.git("commit","-m","base")
        self.base=self.git("rev-parse","HEAD")
        self.git("switch","-c","feat/x")
        (self.repo/"allowed.py").write_text("a=1")
        self.git("add",".");self.git("commit","-m","feature")
        self.head=self.git("rev-parse","HEAD")
        self.work={"order_version":1,"kind":"WORK_ORDER","task_id":"T001",
                   "objective":"Scoped feature","target_branch":"feat/x",
                   "boundaries":{"allowed_paths":["allowed.py"]},
                   "acceptance_criteria":["Regression checks"]}
        self.issue={"html_url":"https://github.com/org/repo/issues/61",
                    "updated_at":"2026-10-26T01:00:00Z","body":fenced(self.work)}
        self.dev={"handoff_version":1,"kind":"DEV_HANDOFF","task_id":"T001",
                  "baseline_sha":self.base,"tested_code_sha":self.head,
                  "pr_url":"https://github.com/org/repo/pull/62",
                  "state":"DEV_READY_FOR_QA","author":"dev-person",
                  "changed_files":["allowed.py"],
                  "dev_checks":[{"command":"python -m unittest","exit_code":0}],
                  "not_run":["Browser check not run"]}
        self.pr={"html_url":self.dev["pr_url"],"head":{"sha":self.head,"ref":"feat/x"},
                 "base":{"sha":self.base,"ref":"main"},"user":{"login":"dev-person"},
                 "body":fenced(self.dev)}
        self.comments=[self.comment()]
        self.grant=self.scope()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self,*args):
        p=subprocess.run(["git",*args],cwd=self.repo,text=True,capture_output=True)
        if p.returncode: raise AssertionError(p.stderr)
        return p.stdout.strip()

    def comment(self,ident=10,kind="FPF_SCOPE_GRANT"):
        fields={"kind":kind,"issue_url":self.issue["html_url"]}
        if kind=="FPF_SCOPE_GRANT":
            fields.update(grant_version=1,task_id="T001",project_id="DEMO01",
                work_order_sha256=hashlib.sha256(self.issue["body"].encode()).hexdigest(),
                issue_revision=self.issue["updated_at"],baseline_sha=self.base,
                target_branch="feat/x",max_attempts=2)
        return {"id":ident,"user":{"login":"project-owner"},"body":fenced(fields)}

    def scope(self,comments=None):
        return resolve_scope_grant(self.issue,self.work,
            comments=self.comments if comments is None else comments,
            authorized_actor="project-owner",project_id="DEMO01",baseline_sha=self.base)

    def observed(self,pr=None,**kw):
        return from_github_records(self.issue,self.pr if pr is None else pr,
            baseline_sha=self.base,project_id="DEMO01",repo_path=self.repo,
            scope_grant=self.grant,**kw)

    def test_grant_revoke_and_edited_issue_invalidates(self):
        self.assertIsNotNone(self.grant)
        self.assertIsNone(self.scope(self.comments+[self.comment(11,"FPF_SCOPE_REVOKE")]))
        forged=dict(self.comments[0],user={"login":"outsider"})
        self.assertIsNone(self.scope([forged]))
        edited={**self.issue,"body":self.issue["body"]+"\nmodified"}
        self.assertFalse(self.grant.matches(edited,self.work,project_id="DEMO01",
                                             baseline_sha=self.base))
        self.assertEqual(next_action(from_github_records(
            self.issue,self.pr,baseline_sha=self.base,project_id="DEMO01",
            repo_path=self.repo)).phase,"HUMAN_GATE_SCOPE")

    def test_rogue_file_not_permitted_even_if_dev_card_lists_it(self):
        (self.repo/"rogue.py").write_text("x=2")
        self.git("add",".");self.git("commit","-m","rogue")
        head=self.git("rev-parse","HEAD")
        dev={**self.dev,"tested_code_sha":head,
             "changed_files":["allowed.py","rogue.py"]}
        pr={**self.pr,"head":{"sha":head,"ref":"feat/x"},"body":fenced(dev)}
        outcome=self.observed(pr=pr)
        self.assertFalse(outcome.dev_validated)
        self.assertEqual(next_action(outcome).phase,"BLOCKED")

    def test_wrong_pr_base_and_target_branch_rejected(self):
        self.assertTrue(self.observed().dev_validated)
        self.assertFalse(self.observed(pr={**self.pr,
            "base":{"sha":self.head,"ref":"main"}}).dev_validated)
        self.assertFalse(self.observed(pr={**self.pr,
            "head":{"sha":self.head,"ref":"feat/WRONG"}}).dev_validated)

    def test_four_field_qa_fail_does_not_trigger_rework(self):
        qa={"kind":"QA_RESULT","task_id":"T001",
            "tested_sha":self.head,"author":"qa-person","verdict":"FAIL"}
        review={"user":{"login":"qa-person"},"state":"CHANGES_REQUESTED",
                "commit_id":self.head,"body":fenced(qa)}
        with patch("packages.fpf_coordinator.dispatch.github_records.trusted.validate_qa_result",
                   return_value=[]) as checker:
            result=self.observed(reviews=[review],evidence_dir=self.repo,
                    authenticate_qa_failure=lambda *_:True)
        checker.assert_not_called()
        self.assertFalse(result.qa_authenticated)
        self.assertEqual(next_action(result).phase,"BLOCKED")

    def test_full_fail_requires_both_card_and_independent_evidence(self):
        qa={"result_version":1,"kind":"QA_RESULT","task_id":"T001",
            "tested_sha":self.head,"author":"qa-person","verdict":"FAIL",
            "runner_sha":self.base,"qa_contract_sha":self.base,
            "environment":"isolated QA worktree",
            "checks":[{"name":"regression","exit_code":1}],
            "evidence_manifest_sha256":"a"*64,
            "findings":{"p1":["test failure"]},"next_action":"REWORK"}
        review={"user":{"login":"qa-person"},"state":"CHANGES_REQUESTED",
                "commit_id":self.head,"body":fenced(qa)}
        self.assertEqual(next_action(self.observed(reviews=[review])).phase,"BLOCKED")
        with patch("packages.fpf_coordinator.dispatch.github_records.trusted.validate_qa_result",
                   return_value=[]) as check:
            outcome=self.observed(reviews=[review],evidence_dir=self.repo,
                authenticate_qa_failure=lambda *_:True)
        check.assert_called_once()
        self.assertEqual(next_action(outcome).role,"dev_lead")

    def test_real_github_merge_commit_unlocks_map_only_after_qa(self):
        self.git("switch","main")
        self.git("cherry-pick",self.head)
        merged=self.git("rev-parse","HEAD")
        pr={**self.pr,"merged":True,"merged_at":"2026-10-26T16:00:00Z",
            "merge_commit":{"sha":merged}}
        qa={"result_version":1,"kind":"QA_RESULT","task_id":"T001",
            "tested_sha":self.head,"author":"qa-person","verdict":"PASS",
            "runner_sha":self.base,"qa_contract_sha":self.base,
            "environment":"isolated QA",
            "checks":[{"name":"regression","exit_code":0}],
            "evidence_manifest_sha256":"a"*64,
            "findings":{"p0":[]},"next_action":"HUMAN_REVIEW"}
        review={"user":{"login":"qa-person"},"state":"APPROVED",
                "commit_id":self.head,"body":fenced(qa)}
        with patch("packages.fpf_coordinator.dispatch.github_records.trusted.validate_qa_result",
                   return_value=[]):
            outcome=self.observed(pr=pr,reviews=[review],evidence_dir=self.repo,
                authenticate_qa_pass=lambda *_:True)
        self.assertTrue(outcome.pr_merge_authenticated)
        self.assertEqual(next_action(outcome).phase,"HUMAN_GATE_MAP")

class Driver:
    def __init__(self):
        self.sends=[]
        self.lookups=[]
        self.status="accepted"
    def send_thread_message(self,**data):
        self.sends.append(data)
        return {"thread_id":data["thread_id"],"request_id":data["request_id"],
                "turn_id":"turn-001","message_id":"message-001"}
    def thread_lookup_by_request(self,**data):
        self.lookups.append(data)
        return {"thread_id":data["thread_id"],"request_id":data["request_id"],
                "turn_id":"turn-001","message_id":"message-001"}
    def thread_status(self,**data):
        return {"thread_id":data["thread_id"],"turn_id":data["turn_id"],
                "state":self.status,"result_ref":"run://1",
                "output_sha256":hashlib.sha256(b"output").hexdigest()}
    def cancel_thread_turn(self,**data):return True

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.ledger=DispatchJournal(Path(self.temp.name)/"coord.sqlite")
        self.target=Target("DEMO01","dev_lead","codex_thread",
            "codex-thread-001","C:/FPF/dev",approved=True)
        self.driver=Driver()
        self.time=[1000.0]
        self.engine=Coordinator(self.ledger,{"dev_lead":self.target},
             {"codex_thread":CodexThreadBridge(self.driver)},
             clock=lambda:self.time[0])
        self.snap=CanonicalSnapshot(
            "T001","DEMO01","https://github.com/org/repo/issues/61",
            "revision","a"*40,None,"Scoped feature",("Tests",),
            ("src/feature.py",),True,True,max_attempts=2,scope_grant_id=10)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_reconcile_real_request_id_without_resending(self):
        packet=make_packet(self.snap,self.target)
        self.ledger.create(packet,self.target)
        self.ledger.set_phase(packet.request_id,"SENDING")
        self.assertEqual(self.engine.reconcile(packet.request_id)["phase"],"ACKNOWLEDGED")
        self.assertEqual(len(self.driver.lookups),1)
        self.assertEqual(self.driver.sends,[])

    def test_attempt_and_retry_policy_cannot_be_reset_or_expanded(self):
        self.assertEqual(self.engine.dispatch_next(self.snap)["phase"],"ACKNOWLEDGED")
        failed=replace(self.snap,pr_head_sha="b"*40,dev_card={"tested_code_sha":"b"*40},
            dev_validated=True,qa_card={"tested_sha":"b"*40,"verdict":"FAIL"},
            qa_authenticated=True,attempt=2)
        self.assertEqual(self.ledger.canonical_attempt(failed),2)
        self.assertEqual(self.engine.dispatch_next(replace(failed,attempt=1))["phase"],
                         "BLOCKED_RECONCILIATION")
        self.assertEqual(self.engine.dispatch_next(failed)["phase"],"ACKNOWLEDGED")
        with self.assertRaisesRegex(ValueError,"authorization/limits changed"):
            self.ledger.canonical_attempt(replace(failed,max_attempts=3))
        self.assertEqual(len(self.driver.sends),2)

    def test_foreground_runner_does_not_invent_next_role(self):
        class Source:
            def __init__(self,s):self.current=s
            def snapshot(self,**kw):
                return replace(self.current,attempt=kw["journal"].canonical_attempt(self.current))
        src=Source(self.snap)
        runner=CoordinationRunner(src,self.engine,issue_number=61,pr_number=62,
             project_id="DEMO01",baseline_sha="a"*40,approved_owner_login="project-owner",
             repo_path=None)
        self.assertEqual(runner.tick()["phase"],"ACKNOWLEDGED")
        self.time[0]+=10
        self.driver.status="completed"
        self.assertEqual(runner.tick()["phase"],"TRANSPORT_COMPLETED_UNVERIFIED")
        src.current=replace(self.snap,pr_head_sha="b"*40,
            dev_card={"tested_code_sha":"b"*40},dev_validated=True)
        self.assertEqual(runner.tick()["phase"],"BLOCKED")
        src.current=replace(src.current,
            qa_card={"tested_sha":"b"*40,"verdict":"PASS"},qa_authenticated=True)
        self.assertEqual(runner.tick()["phase"],"QA_PASSED_AWAITING_OWNER_MERGE")

if __name__=="__main__":
    unittest.main()
