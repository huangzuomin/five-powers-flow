"""Issue #61 regression suite. Fake drivers are NOT live QA evidence."""
import hashlib
import json
import hashlib
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

from packages.fpf_coordinator.dispatch.core import CanonicalSnapshot, Target, make_packet, next_action
from packages.fpf_coordinator.dispatch.controller import Coordinator
from packages.fpf_coordinator.dispatch.journal import DispatchJournal
from packages.fpf_coordinator.dispatch.transports import (
    CodexThreadBridge, ChatGPTWebTransport, Receipt, Observation, UnavailableTransport)
from packages.fpf_coordinator.dispatch.github_records import from_github_records, parse_card
from packages.fpf_coordinator.dispatch.scope_grant import ScopeGrant, resolve_scope_grant



def grant_for(issue, baseline="a"*40, project="DEMO01", max_attempts=2):
    work=parse_card(issue["body"],"WORK_ORDER")
    return ScopeGrant(1,"project-owner",work["task_id"],project,
        issue["html_url"],hashlib.sha256(issue["body"].encode("utf-8")).hexdigest(),
        issue["updated_at"],baseline,work["target_branch"],max_attempts)


def comment_for(issue,baseline="a"*40):
    grant=grant_for(issue,baseline)
    payload={"kind":"FPF_SCOPE_GRANT","grant_version":1,
             "task_id":grant.task_id,"project_id":grant.project_id,
             "issue_url":grant.issue_url,"work_order_sha256":grant.work_order_sha256,
             "issue_revision":grant.issue_revision,"baseline_sha":grant.baseline_sha,
             "target_branch":grant.target_branch,"max_attempts":grant.max_attempts}
    return {"id":123,"user":{"login":"project-owner"},
            "body":"\x60\x60\x60yaml\n"+yaml.safe_dump(payload)+"\x60\x60\x60"}


class Driver:
    def __init__(self):
        self.sent=[]
        self.state="accepted"
        self.raise_after_send=False

    def send_thread_message(self, **kw):
        self.sent.append(kw)
        if self.raise_after_send:
            raise ConnectionError("possible send before transport disconnect")
        return {"thread_id":kw["thread_id"],"request_id":kw["request_id"],
                "turn_id":"turn-001","message_id":"msg-001"}

    def thread_status(self, **kw):
        return {"thread_id":kw["thread_id"],"turn_id":kw["turn_id"],
                "state":self.state,"result_ref":"runner://001",
                "output_sha256":hashlib.sha256(b"actual fixture").hexdigest()}

    def cancel_thread_turn(self, **kw):
        return True


class WebDriver:
    def send_visible_message(self, **kw):
        return {"conversation_url":kw["conversation_url"],
                "request_id":kw["request_id"],"message_visible":True,
                "turn_id":"turn-web","message_id":"msg-web"}
    def read_visible_reply(self, **kw):
        return {"conversation_url":kw["conversation_url"],"state":"completed",
                "result_ref":"web://turn-web",
                "output_sha256":hashlib.sha256(b"reply fixture").hexdigest()}


def state(**diff):
    x=CanonicalSnapshot(
        "T001","DEMO01","https://github.com/org/repo/issues/61","2026-10-26T01:00Z",
        "a"*40,None,"Implement bounded feature",("Pass regression tests",),
        ("src/module.py",),True,True,attempt=1,max_attempts=2)
    return replace(x,**diff)


class RoleDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"coordination.db"
        self.ledger=DispatchJournal(self.path)
        self.dev=Target("DEMO01","dev_lead","codex_thread","codex-thread-001",
                        "C:/FPF/dev",approved=True)
        self.qa=Target("DEMO01","qa_lead","codex_thread","codex-thread-qa01",
                       "C:/FPF/qa",approved=True)
        self.driver=Driver()
        self.now=[1000.0]
        self.engine=Coordinator(self.ledger,{"dev_lead":self.dev,"qa_lead":self.qa},
                                {"codex_thread":CodexThreadBridge(self.driver)},max_polls=3,
                                poll_base_seconds=5,clock=lambda:self.now[0])

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def test_one_send_only_after_repeated_ticks(self):
        first=self.engine.dispatch_next(state())
        second=self.engine.dispatch_next(state())
        self.assertEqual(first["phase"],"ACKNOWLEDGED")
        self.assertEqual(first["request_id"],second["request_id"])
        self.assertEqual(len(self.driver.sent),1)
        self.assertEqual(len(self.ledger.events(first["request_id"])),3)

    def test_accepted_and_completed_are_not_qa_pass(self):
        req=self.engine.dispatch_next(state())["request_id"]
        self.assertEqual(self.engine.observe(req)["phase"],"ACKNOWLEDGED")
        self.driver.state="running"
        self.now[0]+=5
        self.assertEqual(self.engine.observe(req)["phase"],"RUNNING")
        self.driver.state="completed"
        self.now[0]+=10
        self.assertEqual(self.engine.observe(req)["phase"],"TRANSPORT_COMPLETED_UNVERIFIED")

    def test_restart_during_sending_never_resends(self):
        packet=make_packet(state(),self.dev)
        self.ledger.create(packet,self.dev)
        self.ledger.set_phase(packet.request_id,"SENDING")
        self.ledger.close()
        self.ledger=DispatchJournal(self.path)
        self.engine=Coordinator(self.ledger,{"dev_lead":self.dev},
                                {"codex_thread":CodexThreadBridge(self.driver)})
        row=self.engine.dispatch_next(state())
        self.assertEqual(row["phase"],"BLOCKED_RECONCILIATION")
        self.assertEqual(self.driver.sent,[])

    def test_post_send_exception_is_ambiguous_and_no_retry(self):
        self.driver.raise_after_send=True
        row=self.engine.dispatch_next(state())
        self.assertEqual(row["phase"],"BLOCKED_RECONCILIATION")
        self.engine.dispatch_next(state())
        self.assertEqual(len(self.driver.sent),1)

    def test_changed_revision_cannot_duplicate_task(self):
        self.engine.dispatch_next(state())
        with self.assertRaisesRegex(ValueError,"revision/target drift"):
            self.engine.dispatch_next(state(revision="2026-10-26T02:00Z"))

    def test_no_scope_grant_means_no_dispatch(self):
        self.assertEqual(self.engine.dispatch_next(state(scope_authorized=False))["phase"],
                         "HUMAN_GATE_SCOPE")
        self.assertEqual(self.driver.sent,[])

    def test_dev_handoff_must_be_validated_and_on_pr_head(self):
        card={"tested_code_sha":"b"*40}
        self.assertEqual(next_action(state(dev_card=card,pr_head_sha="b"*40)).phase,"BLOCKED")
        self.assertEqual(next_action(state(dev_card=card,dev_validated=True,
                                           pr_head_sha="c"*40)).phase,"BLOCKED")
        authorized=state(dev_card=card,dev_validated=True,pr_head_sha="b"*40)
        self.assertEqual(next_action(authorized).role,"qa_lead")
        self.engine.dispatch_next(authorized)
        self.assertEqual(self.driver.sent[0]["thread_id"],self.qa.identity)

    def test_qa_self_signed_pass_is_blocked(self):
        current=state(dev_card={"tested_code_sha":"b"*40},dev_validated=True,
                      pr_head_sha="b"*40,
                      qa_card={"tested_sha":"b"*40,"verdict":"PASS"})
        self.assertEqual(next_action(current).phase,"BLOCKED")
        self.assertEqual(next_action(replace(current,qa_authenticated=True)).phase,
                         "QA_PASSED_AWAITING_OWNER_MERGE")

    def test_bounded_rework(self):
        current=state(dev_card={"tested_code_sha":"b"*40},dev_validated=True,
                      pr_head_sha="b"*40,qa_authenticated=True,
                      qa_card={"tested_sha":"b"*40,"verdict":"FAIL"})
        self.assertEqual(next_action(current).role,"dev_lead")
        self.assertEqual(next_action(replace(current,attempt=3)).phase,"BLOCKED")

    def test_unknown_provider_observation_never_means_failure(self):
        req=self.engine.dispatch_next(state())["request_id"]
        self.driver.state="unknown"
        self.assertEqual(self.engine.observe(req)["phase"],"BLOCKED_RECONCILIATION")

    def test_persisted_poll_backoff_survives_restart(self):
        req=self.engine.dispatch_next(state())["request_id"]
        self.engine.observe(req)
        self.assertEqual(self.ledger.row(req)["next_poll_at"],1005.0)
        self.assertEqual(self.engine.observe(req)["poll_count"],1)
        self.ledger.close()
        self.ledger=DispatchJournal(self.path)
        engine=Coordinator(self.ledger,{"dev_lead":self.dev},
                           {"codex_thread":CodexThreadBridge(self.driver)},max_polls=3,
                           poll_base_seconds=5,clock=lambda:self.now[0])
        self.assertEqual(engine.observe(req)["poll_count"],1)
        self.now[0]+=5
        self.assertEqual(engine.observe(req)["poll_count"],2)
        self.assertEqual(self.ledger.row(req)["next_poll_at"],1015.0)

    def test_bounded_observation_poll_count(self):
        req=self.engine.dispatch_next(state())["request_id"]
        for _ in range(3):
            self.engine.observe(req)
            self.now[0]+=30
        self.assertEqual(self.engine.observe(req)["phase"],"BLOCKED_RECONCILIATION")

    def test_wrong_project_and_unknown_transport_rejected(self):
        target=Target("OTHER01","dev_lead","codex_thread","codex-thread-001",
                      "C:/FPF/dev",approved=True)
        with self.assertRaisesRegex(ValueError,"another project"):
            make_packet(state(),target)
        engine=Coordinator(self.ledger,{"dev_lead":self.dev},{})
        self.assertEqual(engine.dispatch_next(state())["phase"],"BLOCKED")

    def test_explicit_chatgpt_target_and_visible_reply_only(self):
        with self.assertRaises(ValueError):
            Target("DEMO01","dev_lead","chatgpt_web",
                   "https://chatgpt.com/c/abcdef123456","web",approved=False)
        target=Target("DEMO01","dev_lead","chatgpt_web",
                      "https://chatgpt.com/c/abcdef123456","web",approved=True)
        transport=ChatGPTWebTransport(WebDriver())
        receipt=transport.dispatch(target,make_packet(state(),target))
        self.assertEqual(transport.read_status(target,receipt).state,"completed")

    def test_unavailable_bridge_blocks_instead_of_inventing_receipt(self):
        engine=Coordinator(self.ledger,{"dev_lead":self.dev},
                           {"codex_thread":UnavailableTransport()})
        self.assertEqual(engine.dispatch_next(state())["phase"],"BLOCKED_RECONCILIATION")

    def test_no_protected_governance_path_in_normal_dev_packet(self):
        with self.assertRaisesRegex(ValueError,"Protected governance"):
            make_packet(state(allowed_paths=("packages/fpf_coordinator/dispatch/core.py",)),self.dev)
        with self.assertRaises(ValueError):
            make_packet(state(allowed_paths=("../outside.py",)),self.dev)

    def test_reject_same_repo_issue_url_when_pr_required(self):
        text=("\x60\x60\x60yaml\norder_version: 1\nkind: WORK_ORDER\n"
              "task_id: T001\nobjective: Test\nboundaries:\n"
              "  allowed_paths: [src/module.py]\nacceptance_criteria: [Test]\n"
              "target_branch: feat/demo\n\x60\x60\x60")
        issue={"html_url":"https://github.com/org/repo/issues/61",
               "updated_at":"2026-10-26T01:00:00Z","body":text}
        with self.assertRaisesRegex(ValueError,"Expected PR"):
            from_github_records(issue,{"html_url":"https://github.com/org/repo/issues/62",
                "head":{"sha":"b"*40}},baseline_sha="a"*40,project_id="DEMO01",
                scope_grant=grant_for(issue))

    def test_never_authorize_merge_deploy_qa_signing(self):
        self.assertFalse(set(make_packet(state(),self.dev).allowed_actions) &
                         {"merge","deploy","publish","sign_qa"})
        with self.assertRaises(ValueError):
            state(record_url="https://github.com.evil.org/x/y/issues/61")

    def test_receipts_require_exact_turn_and_output_digest(self):
        with self.assertRaises(ValueError):
            Receipt("req","identity","","message")
        with self.assertRaises(ValueError):
            Observation("req","identity","completed","ref",None)

    def test_read_work_order_from_github_issue(self):
        body=("\x60\x60\x60yaml\norder_version: 1\nkind: WORK_ORDER\n"
              "task_id: T001\nobjective: Test one feature\n"
              "boundaries:\n  allowed_paths: [src/module.py]\n"
              "acceptance_criteria: [Unit tests pass]\n"
              "target_branch: feat/demo\n\x60\x60\x60")
        issue={"html_url":"https://github.com/org/repo/issues/61",
               "updated_at":"2026-10-26T01:00:00Z","body":body}
        observed=from_github_records(issue,None,baseline_sha="a"*40,
                                     project_id="DEMO01",scope_grant=grant_for(issue))
        self.assertEqual(next_action(observed).role,"dev_lead")
        self.assertFalse(observed.qa_authenticated)

    def test_github_readonly_source_checks_platform_identity_and_pagination(self):
        from unittest.mock import patch
        from packages.fpf_coordinator.dispatch.github_reader import GitHubReadOnlySource
        reader=GitHubReadOnlySource("org/repo")
        work=("\x60\x60\x60yaml\norder_version: 1\nkind: WORK_ORDER\n"
              "task_id: T001\nobjective: Approved task\nboundaries:\n"
              "  allowed_paths: [src/module.py]\nacceptance_criteria: [Tests]\n"
              "target_branch: feat/demo\n\x60\x60\x60")
        issue={"html_url":"https://github.com/org/repo/issues/61",
               "user":{"login":"project-owner"},"body":work,
               "updated_at":"2026-10-26T15:00:00Z"}
        def api(endpoint):
            if endpoint.startswith("collaborators/"):
                return {"permission":"write"}
            return [comment_for(issue)] if "comments" in endpoint else issue
        with patch.object(reader,"_api",side_effect=api):
            self.assertEqual(next_action(reader.snapshot(issue_number=61,pr_number=None,
                project_id="DEMO01",baseline_sha="a"*40,approved_owner_login="project-owner",
                repo_path=None)).role,"dev_lead")
            self.assertEqual(next_action(reader.snapshot(issue_number=61,pr_number=None,
                project_id="DEMO01",baseline_sha="a"*40,approved_owner_login="unknown",
                repo_path=None)).phase,"HUMAN_GATE_SCOPE")
        def removed(endpoint):
            return {"permission":"read"} if endpoint.startswith("collaborators/") else api(endpoint)
        with patch.object(reader,"_api",side_effect=removed):
            with self.assertRaisesRegex(ValueError,"current GitHub write permission"):
                reader.snapshot(issue_number=61,pr_number=None,project_id="DEMO01",
                  baseline_sha="a"*40,approved_owner_login="project-owner",repo_path=None)
        with patch.object(reader,"_api",side_effect=[[{"id":k} for k in range(100)],[{"id":100}]]):
            self.assertEqual(len(reader.reviews(88)),101)

    def test_github_readonly_source_never_runs_write_commands(self):
        from unittest.mock import patch
        from packages.fpf_coordinator.dispatch.github_reader import GitHubReadOnlySource
        import types
        reader=GitHubReadOnlySource("org/repo")
        with patch("packages.fpf_coordinator.dispatch.github_reader.subprocess.run",
                   return_value=types.SimpleNamespace(returncode=0,stdout="{}")) as runner:
            reader.issue(61)
            command=runner.call_args.args[0]
            self.assertEqual(command,["gh","api","repos/org/repo/issues/61"])

    def test_real_git_dev_card_then_qa_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)
            def git(*args):
                return subprocess.check_output(["git",*args],cwd=repo,text=True).strip()
            git("init","-b","main")
            git("config","user.name","Fixture")
            git("config","user.email","fixture@example.invalid")
            (repo/"base.txt").write_text("base")
            git("add",".");git("commit","-m","base")
            base=git("rev-parse","HEAD")
            (repo/"new.py").write_text("x=1")
            git("add",".");git("commit","-m","feature")
            head=git("rev-parse","HEAD")
            body=("\x60\x60\x60yaml\norder_version: 1\nkind: WORK_ORDER\n"
                  "task_id: T001\nobjective: Test\nboundaries:\n"
                  "  allowed_paths: [new.py]\nacceptance_criteria: [Check]\n"
                  "target_branch: feat/x\n\x60\x60\x60")
            issue={"html_url":"https://github.com/org/repo/issues/61",
                   "updated_at":"2026-10-26T01:00:00Z","body":body}
            dev={"handoff_version":1,"kind":"DEV_HANDOFF","task_id":"T001",
                 "baseline_sha":base,"tested_code_sha":head,
                 "pr_url":"https://github.com/org/repo/pull/90",
                 "state":"DEV_READY_FOR_QA","author":"developer",
                 "changed_files":["new.py"],
                 "dev_checks":[{"command":"python tests","exit_code":0}],
                 "not_run":["API integration not run"]}
            # JSON is a YAML subset.
            pr={"html_url":dev["pr_url"],"head":{"sha":head,"ref":"feat/x"},
                "base":{"sha":base,"ref":"main"},"user":{"login":"developer"},
                "body":"\x60\x60\x60yaml\n"+yaml.safe_dump(dev)+"\n\x60\x60\x60"}
            observed=from_github_records(issue,pr,baseline_sha=base,
                               project_id="DEMO01",repo_path=repo,scope_grant=grant_for(issue,base))
            self.assertTrue(observed.dev_validated)
            self.assertEqual(next_action(observed).role,"qa_lead")
            bad_qa={"kind":"QA_RESULT","task_id":"T001","tested_sha":head,
                    "author":"qa-reviewer","verdict":"FAIL"}
            reviews=[{"state":"CHANGES_REQUESTED","commit_id":head,
                      "user":{"login":"qa-reviewer"},
                      "body":"\x60\x60\x60yaml\n"+yaml.safe_dump(bad_qa)+"\x60\x60\x60"}]
            fail=from_github_records(issue,pr,baseline_sha=base,
                project_id="DEMO01",repo_path=repo,scope_grant=grant_for(issue,base),reviews=reviews)
            self.assertEqual(next_action(fail).phase,"BLOCKED")
            good_qa={**bad_qa,"verdict":"PASS"}
            passed=[{**reviews[0],"state":"APPROVED",
                     "body":"\x60\x60\x60yaml\n"+yaml.safe_dump(good_qa)+"\x60\x60\x60"}]
            unproven=from_github_records(issue,pr,baseline_sha=base,
                project_id="DEMO01",repo_path=repo,scope_grant=grant_for(issue,base),reviews=passed)
            self.assertEqual(next_action(unproven).phase,"BLOCKED")
            wrong=from_github_records(issue,{**pr,"user":{"login":"wrong"}},
                               baseline_sha=base,project_id="DEMO01",
                               repo_path=repo,scope_grant=grant_for(issue,base))
            self.assertEqual(next_action(wrong).phase,"BLOCKED")


if __name__=="__main__":
    unittest.main()
