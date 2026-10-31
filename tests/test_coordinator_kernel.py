# -*- coding: utf-8 -*-
"""Comprehensive unit tests for FPF Autonomous Engineering Coordinator Kernel."""
import sqlite3
import time
import unittest

from packages.fpf_coordinator.dispatch import (
    Phase,
    Decision,
    CanonicalSnapshot,
    Target,
    TaskPacket,
    next_action,
    make_packet,
    make_idempotency_key,
    canonical_url,
    validate_sha,
    StateJournal,
    TaskRecord,
    ConcurrencyConflictError,
    TaskNotFoundError,
)


class TestCoordinatorStateReducer(unittest.TestCase):
    def setUp(self):
        self.base_sha = "d2852c9315f76010a1dcb752229cec54d397eeed"
        self.tested_sha = "0fef95e155b386d6c27dc63dc5fb74d64326e5e8"
        self.merge_sha = "2327ac1f36412fb26c17d291b719930967091200"
        self.record_url = "https://github.com/huangzuomin/five-powers-flow/issues/68"

    def test_scope_authorization_gate(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            scope_authorized=False,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.HUMAN_SCOPE_AUTHORIZATION_PENDING)
        self.assertTrue(dec.requires_human)
        self.assertIsNone(dec.role)

    def test_dev_design_pending_when_missing_work_order(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            scope_authorized=True,
            work_order=None,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.DEV_DESIGN_PENDING)
        self.assertEqual(dec.role, "dev_lead")
        self.assertFalse(dec.requires_human)

    def test_qa_admission_gate(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission=None,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.QA_ADMISSION_PENDING)
        self.assertEqual(dec.role, "qa_lead")

    def test_qa_admission_rejected(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "REJECTED", "reason": "Blast radius too high"},
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BLOCKED_ADMISSION_REJECTED)
        self.assertIsNone(dec.role)

    def test_dev_dispatch_pending(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card=None,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.DEV_DISPATCH_PENDING)
        self.assertEqual(dec.role, "dev_worker")

    def test_dev_validation_failure_bounded_rework(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=False,
            attempt=1,
            max_attempts=3,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BOUNDED_DEV_REWORK)
        self.assertEqual(dec.role, "dev_worker")

    def test_dev_validation_failure_exceeds_max_attempts_blocked(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=False,
            attempt=3,
            max_attempts=3,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BLOCKED)

    def test_dev_tested_sha_drift_blocked(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BLOCKED)

    def test_qa_plan_freeze_pending(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan=None,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.QA_PLAN_FREEZE_PENDING)
        self.assertEqual(dec.role, "qa_lead")

    def test_qa_plan_sha_mismatch_blocked(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.base_sha},
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BLOCKED)

    def test_qa_dispatch_pending(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card=None,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.QA_DISPATCH_PENDING)
        self.assertEqual(dec.role, "qa_worker")

    def test_qa_unauthenticated_blocked(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card={"tested_sha": self.tested_sha, "verdict": "PASS"},
            qa_authenticated=False,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BLOCKED_QA_IDENTITY_UNAVAILABLE)

    def test_qa_tested_sha_mismatch_blocked(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card={"tested_sha": self.base_sha, "verdict": "PASS"},
            qa_authenticated=True,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BLOCKED)

    def test_qa_fail_triggers_bounded_rework(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card={"tested_sha": self.tested_sha, "verdict": "FAIL", "findings": ["bug"]},
            qa_authenticated=True,
            attempt=1,
            max_attempts=3,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BOUNDED_DEV_REWORK)
        self.assertEqual(dec.role, "dev_worker")

    def test_qa_fail_reaches_max_attempts_blocked(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card={"tested_sha": self.tested_sha, "verdict": "FAIL"},
            qa_authenticated=True,
            attempt=3,
            max_attempts=3,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.BLOCKED)

    def test_qa_pass_awaits_human_code_merge(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card={"tested_sha": self.tested_sha, "verdict": "PASS"},
            qa_authenticated=True,
            pr_merged=False,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.HUMAN_GATE_MERGE)
        self.assertTrue(dec.requires_human)

    def test_code_merged_awaits_scribe_dispatch(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card={"tested_sha": self.tested_sha, "verdict": "PASS"},
            qa_authenticated=True,
            pr_merged=True,
            code_merged_sha=self.merge_sha,
            map_card=None,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.SCRIBE_DISPATCH_PENDING)
        self.assertEqual(dec.role, "scribe")

    def test_map_pr_awaits_human_map_merge(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card={"tested_sha": self.tested_sha, "verdict": "PASS"},
            qa_authenticated=True,
            pr_merged=True,
            code_merged_sha=self.merge_sha,
            map_card={"project_map": "docs/PROJECT-MAP.md"},
            map_pr_merged=False,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.HUMAN_GATE_MAP_MERGE)
        self.assertTrue(dec.requires_human)

    def test_full_closeout_closed(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url=self.record_url,
            revision="rev1",
            baseline_sha=self.base_sha,
            pr_head_sha=self.tested_sha,
            scope_authorized=True,
            work_order={"task_id": "TASK-01"},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"tested_code_sha": self.tested_sha},
            dev_validated=True,
            qa_plan={"target_head_sha": self.tested_sha},
            qa_card={"tested_sha": self.tested_sha, "verdict": "PASS"},
            qa_authenticated=True,
            pr_merged=True,
            code_merged_sha=self.merge_sha,
            map_card={"project_map": "docs/PROJECT-MAP.md"},
            map_pr_merged=True,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.CLOSED)


class TestIdempotencyAndPackets(unittest.TestCase):
    def test_idempotency_key_generation(self):
        k1 = make_idempotency_key("T1", 1, "d2852c9315f76010a1dcb752229cec54d397eeed", "plan")
        k2 = make_idempotency_key("T1", 1, "d2852c9315f76010a1dcb752229cec54d397eeed", "plan")
        k3 = make_idempotency_key("T1", 2, "d2852c9315f76010a1dcb752229cec54d397eeed", "plan")
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, k3)
        self.assertEqual(len(k1), 32)

    def test_make_packet_success(self):
        base_sha = "d2852c9315f76010a1dcb752229cec54d397eeed"
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url="https://github.com/huangzuomin/five-powers-flow/issues/68",
            revision="rev1",
            baseline_sha=base_sha,
            scope="Implementation slice",
            allowed_paths=("packages/foo/",),
            scope_authorized=True,
            work_order=None,
        )
        target = Target(
            project_id="PROJ-01",
            role="dev_lead",
            transport="chatgpt_web",
            identity="https://chatgpt.com/c/12345678",
            workspace="ws-dev",
            approved=True,
        )
        packet = make_packet(snap, target, request_id="REQ-01", action="plan")
        self.assertEqual(packet.task_id, "TASK-01")
        self.assertEqual(packet.role, "dev_lead")
        self.assertEqual(packet.request_id, "REQ-01")
        self.assertIn("plan", packet.allowed_actions)
        brief = packet.brief()
        self.assertIn("REQ-01", brief)

    def test_make_packet_rejects_human_gate_dispatch(self):
        snap = CanonicalSnapshot(
            task_id="TASK-01",
            project_id="PROJ-01",
            record_url="https://github.com/huangzuomin/five-powers-flow/issues/68",
            revision="rev1",
            baseline_sha="d2852c9315f76010a1dcb752229cec54d397eeed",
            scope_authorized=False,
        )
        target = Target(
            project_id="PROJ-01",
            role="owner_delegate",
            transport="codex_cli",
            identity="agent-01",
            workspace="ws",
            approved=True,
        )
        with self.assertRaises(ValueError):
            make_packet(snap, target, "REQ-01", "orchestrate")


class TestStateJournalCASAndLease(unittest.TestCase):
    def setUp(self):
        self.journal = StateJournal(":memory:")

    def test_task_creation_and_cas_update(self):
        task = self.journal.create_task(
            task_id="T-100",
            project_id="P-100",
            baseline_sha="d2852c9315f76010a1dcb752229cec54d397eeed",
            max_attempts=3,
        )
        self.assertEqual(task.version, 1)
        self.assertEqual(task.attempt, 1)
        self.assertEqual(task.phase, Phase.TASK_INTAKE)

        # Successful CAS update
        v2 = self.journal.update_phase(
            task_id="T-100",
            expected_version=1,
            new_phase=Phase.DEV_DESIGN_PENDING,
        )
        self.assertEqual(v2, 2)
        updated = self.journal.get_task("T-100")
        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.phase, Phase.DEV_DESIGN_PENDING)

        # Conflicting CAS update (expected_version is still 1)
        with self.assertRaises(ConcurrencyConflictError):
            self.journal.update_phase(
                task_id="T-100",
                expected_version=1,
                new_phase=Phase.QA_ADMISSION_PENDING,
            )

    def test_attempt_monotonic_increment(self):
        self.journal.create_task("T-200", "P-100", "d2852c9315f76010a1dcb752229cec54d397eeed", max_attempts=2)
        # Attempt 1 -> 2
        v2 = self.journal.increment_attempt("T-200", 1, last_failure="Bug 1")
        self.assertEqual(v2, 2)
        t = self.journal.get_task("T-200")
        self.assertEqual(t.attempt, 2)
        self.assertEqual(t.last_failure, "Bug 1")

        # Attempt 2 -> reached max_attempts (2) -> transitions to BLOCKED
        v3 = self.journal.increment_attempt("T-200", 2, last_failure="Bug 2")
        self.assertEqual(v3, 3)
        t_blocked = self.journal.get_task("T-200")
        self.assertEqual(t_blocked.phase, Phase.BLOCKED)
        self.assertIn("Max attempts", t_blocked.last_failure)

    def test_lease_lifecycle(self):
        ok, token = self.journal.acquire_lease("T-300", "worker-A", ttl_seconds=2)
        self.assertTrue(ok)
        self.assertIsNotNone(token)

        # Worker B tries to acquire while A's lease is active
        ok2, token2 = self.journal.acquire_lease("T-300", "worker-B", ttl_seconds=2)
        self.assertFalse(ok2)
        self.assertIsNone(token2)

        # Worker A renews lease
        renewed = self.journal.renew_lease("T-300", "worker-A", token, ttl_seconds=5)
        self.assertTrue(renewed)

        # Worker A releases lease
        released = self.journal.release_lease("T-300", "worker-A", token)
        self.assertTrue(released)

        # Now Worker B can acquire
        ok3, token3 = self.journal.acquire_lease("T-300", "worker-B", ttl_seconds=2)
        self.assertTrue(ok3)

    def test_intent_logging_and_idempotency(self):
        self.journal.create_task("T-400", "P-100", "d2852c9315f76010a1dcb752229cec54d397eeed")
        self.journal.record_intent(
            task_id="T-400",
            request_id="REQ-401",
            idempotency_key="IDEM-401",
            role="dev_worker",
            action="edit_feature_branch",
            phase=Phase.DEV_DISPATCH_PENDING,
            payload={"brief": "edit"},
        )
        intent = self.journal.get_intent("REQ-401")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.status, "PENDING")

        # Duplicate idempotency_key raises sqlite3.IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            self.journal.record_intent(
                task_id="T-400",
                request_id="REQ-402",
                idempotency_key="IDEM-401",
                role="dev_worker",
                action="edit_feature_branch",
                phase=Phase.DEV_DISPATCH_PENDING,
                payload={"brief": "edit2"},
            )

        # Mark dispatched
        self.journal.mark_intent_dispatched("REQ-401", {"receipt_id": "RC-01"})
        intent_disp = self.journal.get_intent("REQ-401")
        self.assertEqual(intent_disp.status, "DISPATCHED")
        self.assertEqual(intent_disp.receipt["receipt_id"], "RC-01")

        # Mark settled
        self.journal.mark_intent_settled("REQ-401")
        intent_settled = self.journal.get_intent("REQ-401")
        self.assertEqual(intent_settled.status, "SETTLED")

    def test_checkpoints(self):
        self.journal.create_task("T-500", "P-100", "d2852c9315f76010a1dcb752229cec54d397eeed")
        self.journal.save_checkpoint("T-500", Phase.DEV_RUNNING, 3, {"sha": "abc"})
        res = self.journal.get_latest_checkpoint("T-500")
        self.assertIsNotNone(res)
        phase, version, snap = res
        self.assertEqual(phase, Phase.DEV_RUNNING)
        self.assertEqual(version, 3)
        self.assertEqual(snap["sha"], "abc")


if __name__ == "__main__":
    unittest.main()
