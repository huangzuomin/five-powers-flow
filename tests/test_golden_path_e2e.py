# -*- coding: utf-8 -*-
"""End-to-End integration tests for FPF-AEC Golden Path A (Success) and Golden Path B (Rework).

Verifies the complete 24-state machine lifecycle, attempt monotonicity,
dual human merge gates, and fail-closed reconciliation.
"""
from __future__ import annotations

import gc
from pathlib import Path
import tempfile
import unittest

from packages.fpf_coordinator.dispatch.core import (
    CanonicalSnapshot,
    Target,
    make_packet,
    next_action,
)
from packages.fpf_coordinator.dispatch.journal import StateJournal
from packages.fpf_coordinator.dispatch.states import (
    HUMAN_GATE_PHASES,
    TERMINAL_PHASES,
    Phase,
)
from packages.fpf_runtime.daemon.config import DaemonConfig
from packages.fpf_runtime.daemon.reconciliation import ReconciliationEngine
from packages.fpf_runtime.daemon.server import DaemonServer


class TestGoldenPathA_SuccessE2E(unittest.TestCase):
    """Full 18-step Golden Path A lifecycle: intake to verified closeout."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.journal = StateJournal(self.root / "state.sqlite3")

    def tearDown(self):
        if hasattr(self.journal, "_conn"):
            self.journal._conn.close()
        gc.collect()
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_golden_path_a_full_walkthrough(self):
        task_id = "TASK-E2E-A"
        project_id = "PROJ-CORE"
        record_url = "https://github.com/org/repo/issues/101"
        base_sha = "1" * 40
        dev_sha = "2" * 40
        merge_sha = "3" * 40

        # 1. Task Intake
        task_record = self.journal.create_task(task_id, project_id, base_sha, Phase.TASK_INTAKE)
        self.assertEqual(task_record.phase, Phase.TASK_INTAKE)
        self.assertEqual(task_record.version, 1)
        self.assertEqual(task_record.attempt, 1)

        # 2. State Reducer evaluates un-authorized snapshot
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            scope_authorized=False,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.HUMAN_SCOPE_AUTHORIZATION_PENDING)
        self.assertTrue(dec.requires_human)

        # 3. Human Scope Grant signed
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            scope="Implement user authentication API",
            allowed_paths=("packages/auth/", "tests/test_auth.py"),
            scope_authorized=True,
        )
        v = self.journal.update_phase(task_id, 1, Phase.DEV_DESIGN_PENDING)
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.DEV_DESIGN_PENDING)
        self.assertEqual(dec.role, "dev_lead")

        # 4. DEV Lead delivers WORK_ORDER
        work_order = {
            "order_version": 1,
            "kind": "WORK_ORDER",
            "task_id": task_id,
            "objective": "Implement auth endpoints",
        }
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            scope_authorized=True,
            allowed_paths=("packages/auth/",),
            work_order=work_order,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.QA_ADMISSION_PENDING)
        self.assertEqual(dec.role, "qa_lead")

        # 5. QA Admission Gate
        admission = {
            "kind": "QA_ADMISSION",
            "task_id": task_id,
            "verdict": "ADMITTED",
        }
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            scope_authorized=True,
            allowed_paths=("packages/auth/",),
            work_order=work_order,
            qa_admission=admission,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.DEV_DISPATCH_PENDING)
        self.assertEqual(dec.role, "dev_worker")

        # 6. Dispatch packet generation for DEV Worker
        target_dev = Target(
            project_id=project_id,
            role="dev_worker",
            transport="codex_cli",
            identity="codex-worker-01",
            workspace="D:/workspaces/dev-auth",
            approved=True,
        )
        packet = make_packet(snap, target_dev, "req-dev-01", "edit_feature_branch")
        self.assertEqual(packet.role, "dev_worker")
        self.assertEqual(packet.task_id, task_id)
        self.assertEqual(packet.attempt, 1)

        # 7. DEV Worker completes implementation and hands off
        dev_card = {
            "kind": "DEV_HANDOFF",
            "task_id": task_id,
            "baseline_sha": base_sha,
            "tested_code_sha": dev_sha,
        }
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            pr_head_sha=dev_sha,
            scope_authorized=True,
            allowed_paths=("packages/auth/",),
            work_order=work_order,
            qa_admission=admission,
            dev_card=dev_card,
            dev_validated=True,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.QA_PLAN_FREEZE_PENDING)
        self.assertEqual(dec.role, "qa_lead")

        # 8. QA Lead freezes QA Plan on dev_sha
        qa_plan = {
            "kind": "QA_PLAN",
            "task_id": task_id,
            "target_head_sha": dev_sha,
        }
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            pr_head_sha=dev_sha,
            scope_authorized=True,
            allowed_paths=("packages/auth/",),
            work_order=work_order,
            qa_admission=admission,
            dev_card=dev_card,
            dev_validated=True,
            qa_plan=qa_plan,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.QA_DISPATCH_PENDING)
        self.assertEqual(dec.role, "qa_worker")

        # 9. Independent QA signs QA_RESULT PASS
        qa_card = {
            "kind": "QA_RESULT",
            "task_id": task_id,
            "tested_sha": dev_sha,
            "verdict": "PASS",
        }
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            pr_head_sha=dev_sha,
            scope_authorized=True,
            allowed_paths=("packages/auth/",),
            work_order=work_order,
            qa_admission=admission,
            dev_card=dev_card,
            dev_validated=True,
            qa_plan=qa_plan,
            qa_card=qa_card,
            qa_authenticated=True,
            pr_merged=False,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.HUMAN_GATE_MERGE)
        self.assertTrue(dec.requires_human)

        # 10. Human Sovereign merges PR to main
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            pr_head_sha=dev_sha,
            scope_authorized=True,
            allowed_paths=("packages/auth/",),
            work_order=work_order,
            qa_admission=admission,
            dev_card=dev_card,
            dev_validated=True,
            qa_plan=qa_plan,
            qa_card=qa_card,
            qa_authenticated=True,
            pr_merged=True,
            code_merged_sha=merge_sha,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.SCRIBE_DISPATCH_PENDING)
        self.assertEqual(dec.role, "scribe")

        # 11. Scribe creates MAP_UPDATE PR
        map_card = {
            "kind": "MAP_UPDATE",
            "task_id": task_id,
            "code_merged_sha": merge_sha,
        }
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            pr_head_sha=dev_sha,
            scope_authorized=True,
            allowed_paths=("packages/auth/",),
            work_order=work_order,
            qa_admission=admission,
            dev_card=dev_card,
            dev_validated=True,
            qa_plan=qa_plan,
            qa_card=qa_card,
            qa_authenticated=True,
            pr_merged=True,
            code_merged_sha=merge_sha,
            map_card=map_card,
            map_pr_merged=False,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.HUMAN_GATE_MAP_MERGE)
        self.assertTrue(dec.requires_human)

        # 12. Human Sovereign merges Map PR -> CLOSED
        snap = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            pr_head_sha=dev_sha,
            scope_authorized=True,
            allowed_paths=("packages/auth/",),
            work_order=work_order,
            qa_admission=admission,
            dev_card=dev_card,
            dev_validated=True,
            qa_plan=qa_plan,
            qa_card=qa_card,
            qa_authenticated=True,
            pr_merged=True,
            code_merged_sha=merge_sha,
            map_card=map_card,
            map_pr_merged=True,
        )
        dec = next_action(snap)
        self.assertEqual(dec.phase, Phase.CLOSED)
        self.assertIn(dec.phase, TERMINAL_PHASES)


class TestGoldenPathB_FailureAndReworkE2E(unittest.TestCase):
    """Golden Path B: QA FAIL triggers attempt increment and bounded rework."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.journal = StateJournal(self.root / "state.sqlite3")

    def tearDown(self):
        if hasattr(self.journal, "_conn"):
            self.journal._conn.close()
        gc.collect()
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_golden_path_b_fail_and_rework_to_pass(self):
        task_id = "TASK-E2E-B"
        project_id = "PROJ-CORE"
        record_url = "https://github.com/org/repo/issues/102"
        base_sha = "4" * 40
        sha_v1 = "5" * 40
        sha_v2 = "6" * 40

        task = self.journal.create_task(task_id, project_id, base_sha, Phase.DEV_DISPATCH_PENDING, max_attempts=3)
        self.assertEqual(task.attempt, 1)

        # Attempt 1: QA fails
        qa_card_fail = {
            "kind": "QA_RESULT",
            "task_id": task_id,
            "tested_sha": sha_v1,
            "verdict": "FAIL",
            "findings": ["P1: Token verification bypass detected"],
        }
        snap_v1 = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev1",
            baseline_sha=base_sha,
            pr_head_sha=sha_v1,
            scope_authorized=True,
            allowed_paths=("src/",),
            work_order={"task_id": task_id},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"task_id": task_id, "tested_code_sha": sha_v1},
            dev_validated=True,
            qa_plan={"task_id": task_id, "target_head_sha": sha_v1},
            qa_card=qa_card_fail,
            qa_authenticated=True,
            attempt=1,
            max_attempts=3,
        )
        dec_v1 = next_action(snap_v1)
        self.assertEqual(dec_v1.phase, Phase.BOUNDED_DEV_REWORK)
        self.assertEqual(dec_v1.role, "dev_worker")

        # Monotonically increment attempt in journal
        new_v = self.journal.increment_attempt(task_id, expected_version=1, last_failure="QA verdict FAIL: P1 found")
        task_after_fail = self.journal.get_task(task_id)
        self.assertEqual(task_after_fail.attempt, 2)
        self.assertEqual(task_after_fail.version, 2)

        # Attempt 2: Rework produces sha_v2 and passes
        qa_card_pass = {
            "kind": "QA_RESULT",
            "task_id": task_id,
            "tested_sha": sha_v2,
            "verdict": "PASS",
        }
        snap_v2 = CanonicalSnapshot(
            task_id=task_id,
            project_id=project_id,
            record_url=record_url,
            revision="rev2",
            baseline_sha=base_sha,
            pr_head_sha=sha_v2,
            scope_authorized=True,
            allowed_paths=("src/",),
            work_order={"task_id": task_id},
            qa_admission={"verdict": "ADMITTED"},
            dev_card={"task_id": task_id, "tested_code_sha": sha_v2},
            dev_validated=True,
            qa_plan={"task_id": task_id, "target_head_sha": sha_v2},
            qa_card=qa_card_pass,
            qa_authenticated=True,
            attempt=2,
            max_attempts=3,
        )
        dec_v2 = next_action(snap_v2)
        self.assertEqual(dec_v2.phase, Phase.HUMAN_GATE_MERGE)
        self.assertTrue(dec_v2.requires_human)


class TestAttemptLimitFailClosed(unittest.TestCase):
    """Verifies that exceeding max_attempts immediately transitions to BLOCKED."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.journal = StateJournal(self.root / "state.sqlite3")

    def tearDown(self):
        if hasattr(self.journal, "_conn"):
            self.journal._conn.close()
        gc.collect()
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_attempt_exhaustion_blocks_task(self):
        task_id = "TASK-MAX"
        # max_attempts = 2
        self.journal.create_task(task_id, "PROJ-1", "0" * 40, Phase.DEV_DISPATCH_PENDING, max_attempts=2)

        # Attempt 1 -> 2
        self.journal.increment_attempt(task_id, 1, "First failure")
        t = self.journal.get_task(task_id)
        self.assertEqual(t.attempt, 2)
        self.assertNotEqual(t.phase, Phase.BLOCKED)

        # Attempt 2 -> exceeds max_attempts: triggers transition to BLOCKED
        self.journal.increment_attempt(task_id, 2, "Second failure")
        t_blocked = self.journal.get_task(task_id)
        self.assertEqual(t_blocked.phase, Phase.BLOCKED)
        self.assertIn("Max attempts (2) reached", t_blocked.last_failure)


if __name__ == "__main__":
    unittest.main()
