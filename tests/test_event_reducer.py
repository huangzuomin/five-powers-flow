# -*- coding: utf-8 -*-
"""Deterministic tests for the G4 event reducer and projection ledger."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from packages.fpf_coordinator.dispatch.events import (
    EventBatch,
    EventValidationError,
    build_event,
    canonical_json_bytes,
    digest_payload,
    normalize_event,
)
from packages.fpf_coordinator.dispatch.journal import (
    ConcurrencyConflictError,
    StateJournal,
)
from packages.fpf_coordinator.dispatch.poller import genesis_ledger, ledger_from_reduction
from packages.fpf_coordinator.dispatch.reconcile import reconcile_projection
from packages.fpf_coordinator.dispatch.reducer import reduce_events
from packages.fpf_coordinator.dispatch.states import TERMINAL_PHASES, Phase
from packages.fpf_policy.pr_gate import classify


BASE = "a" * 40
HEAD = "b" * 40
NEXT = "c" * 40
MERGE = "d" * 40
MAIN = "e" * 40
REPO = "huangzuomin/five-powers-flow"
TASK = "FPF2-G4-TEST-01"
PROJECT = "FPF"
ACTOR = {"login": "dev-a", "kind": "human"}
SOURCE = {
    "backend": "github",
    "repo": REPO,
    "object": "pull_request",
    "object_id": 42,
    "sequence": 0,
}


def event(
    event_type: str,
    payload: dict,
    *,
    sequence: int,
    occurred_at: str = "2026-11-12T00:00:00Z",
    sha: str | None = HEAD,
    causation_id: str | None = None,
):
    source = dict(SOURCE)
    source["sequence"] = sequence
    return build_event(
        type=event_type,
        task_id=TASK,
        project_id=PROJECT,
        actor=ACTOR,
        source=source,
        occurred_at=occurred_at,
        payload=payload,
        sha=sha,
        correlation_id="test-correlation",
        causation_id=causation_id,
    )


def lifecycle_events(
    *,
    expire_at: str = "2030-01-01T00:00:00Z",
    with_merge: bool = True,
):
    sequence = 0
    opened = event(
        "TASK_OPENED",
        {
            "task_id": TASK,
            "project_id": PROJECT,
            "baseline_sha": BASE,
            "max_attempts": 3,
            "created_at": "2026-11-12T00:00:00Z",
            "record_url": "https://github.com/huangzuomin/five-powers-flow/pull/42",
        },
        sequence=sequence,
        sha=BASE,
    )
    sequence += 1
    work = event(
        "WORK_ORDER_OPENED",
        {"work_order_id": "WO-TEST", "task_id": TASK},
        sequence=sequence,
        causation_id=opened.event_id,
    )
    sequence += 1
    scope = event(
        "SCOPE_GRANTED",
        {
            "grant_id": "grant-1",
            "scope": "G4 test",
            "allowed_paths": ["packages/fpf_coordinator/dispatch/"],
            "expires_at": expire_at,
            "baseline_sha": BASE,
        },
        sequence=sequence,
        causation_id=work.event_id,
    )
    sequence += 1
    admission = event(
        "QA_ADMISSION_GRANTED",
        {"verdict": "ADMITTED", "qa_plan_sha": BASE, "reason": "test admission"},
        sequence=sequence,
        causation_id=scope.event_id,
    )
    sequence += 1
    delivery = event(
        "POLICY_CHANGE_DELIVERY_RECEIVED",
        {
            "tested_code_sha": HEAD,
            "baseline_sha": BASE,
            "grant_id": "grant-1",
            "author": "dev-a",
            "checks": [],
            "delivery_kind": "POLICY_CHANGE",
            "changed_files": ["packages/fpf_coordinator/dispatch/state-ledger.json"],
        },
        sequence=sequence,
        causation_id=admission.event_id,
    )
    sequence += 1
    validation = event(
        "DEV_VALIDATION_PASSED",
        {"tested_code_sha": HEAD, "result": "PASS", "evidence_digest": "f" * 64},
        sequence=sequence,
        causation_id=delivery.event_id,
    )
    sequence += 1
    plan = event(
        "QA_PLAN_FROZEN",
        {
            "target_head_sha": HEAD,
            "qa_contract_sha": BASE,
            "profile": "Library",
        },
        sequence=sequence,
        causation_id=validation.event_id,
    )
    sequence += 1
    qa_payload = {
        "verdict": "PASS",
        "tested_sha": HEAD,
        "task_id": TASK,
        "author": "qa-bot[bot]",
        "checks": [{"id": "EVID-01", "exit_code": 0}],
        "evidence_manifest_sha256": "1" * 64,
        "qa_run_id": 123,
        "qa_artifact_id": 456,
        "artifact_digest": "sha256:" + "2" * 64,
        "runner_sha": BASE,
        "qa_contract_sha": BASE,
        "profile": "Library",
    }
    qa = event(
        "QA_RESULT_RECEIVED",
        qa_payload,
        sequence=sequence,
        causation_id=plan.event_id,
    )
    sequence += 1
    authenticated = event(
        "QA_AUTHENTICATED",
        {
            "review_id": "9001",
            "review_commit_id": HEAD,
            "qa_result_digest": digest_payload(qa_payload),
            "artifact_digest": "sha256:" + "2" * 64,
            "runner_sha": BASE,
            "qa_contract_sha": BASE,
        },
        sequence=sequence,
        causation_id=qa.event_id,
    )
    sequence += 1
    values = [opened, work, scope, admission, delivery, validation, plan, qa, authenticated]
    if with_merge:
        merged = event(
            "PR_MERGED",
            {"pr_number": 42, "merge_commit_sha": MERGE, "merged_by": "owner"},
            sequence=sequence,
            sha=MERGE,
            occurred_at="2026-11-12T00:10:00Z",
            causation_id=authenticated.event_id,
        )
        values.append(merged)
    return values


def reduce(values, *, complete=True, stale=False):
    return reduce_events(
        EventBatch(tuple(values), cursor="test", complete=complete),
        task_id=TASK,
        project_id=PROJECT,
        complete=complete,
        stale=stale,
    )


class TestEventIdentityAndDeterminism(unittest.TestCase):
    def test_event_identity_and_payload_digest_are_recomputed(self):
        value = event(
            "TASK_OPENED",
            {
                "task_id": TASK,
                "project_id": PROJECT,
                "baseline_sha": BASE,
                "max_attempts": 3,
                "created_at": "2026-11-12T00:00:00Z",
                "record_url": "https://github.com/huangzuomin/five-powers-flow/pull/42",
            },
            sequence=0,
            sha=BASE,
        )
        raw = value.to_dict()
        raw["payload_digest"] = "0" * 64
        with self.assertRaises(EventValidationError) as ctx:
            normalize_event(raw)
        self.assertEqual(ctx.exception.reason, "EVENT_ENVELOPE_TAMPERED")

    def test_replay_twice_is_byte_identical(self):
        values = lifecycle_events()
        first = reduce(values)
        second = reduce(list(reversed(values)))
        self.assertEqual(
            canonical_json_bytes(first.projection),
            canonical_json_bytes(second.projection),
        )
        self.assertEqual(first.projection_digest, second.projection_digest)
        self.assertEqual(first.event_log_digest, second.event_log_digest)

    def test_exact_duplicate_is_ignored_without_projection_change(self):
        values = lifecycle_events()
        first = reduce(values)
        second = reduce(values + [values[3]])
        self.assertEqual(first.projection_digest, second.projection_digest)
        self.assertTrue(any(item["reason"] == "DUPLICATE" for item in second.ignored_events))

    def test_duplicate_fact_keeps_lexicographically_first_event(self):
        opened = lifecycle_events()[0]
        later = event(
            "TASK_OPENED",
            {
                "task_id": TASK,
                "project_id": PROJECT,
                "baseline_sha": BASE,
                "max_attempts": 3,
                "created_at": "2026-11-12T00:00:00Z",
                "record_url": "https://github.com/huangzuomin/five-powers-flow/pull/42",
            },
            sequence=1,
            occurred_at="2026-11-12T00:01:00Z",
            sha=BASE,
        )
        result = reduce([later, opened])
        self.assertIn(opened.event_id, result.event_ids)
        self.assertNotIn(later.event_id, result.event_ids)
        self.assertTrue(any(item["reason"] == "DUPLICATE_FACT" for item in result.ignored_events))

    def test_out_of_order_input_is_topologically_sorted(self):
        values = lifecycle_events(with_merge=False)
        result = reduce(list(reversed(values)))
        self.assertEqual(result.ordered_events[0].type, "TASK_OPENED")
        self.assertEqual(result.ordered_events[-1].type, "QA_AUTHENTICATED")
        self.assertEqual(result.projection["decision"]["phase"], "HUMAN_GATE_MERGE")


class TestDeterministicConflictRules(unittest.TestCase):
    def test_expired_scope_blocks_progress(self):
        result = reduce(lifecycle_events(expire_at="2026-11-11T00:00:00Z"))
        self.assertIn("AUTHORIZATION_EXPIRED", result.reasons)
        self.assertEqual(result.projection["decision"]["phase"], "BLOCKED_UNAUTHORIZED_SCOPE")

    def test_scope_expiring_before_later_advance_blocks(self):
        values = lifecycle_events(expire_at="2026-11-12T00:05:00Z", with_merge=True)
        result = reduce(values)
        self.assertIn("AUTHORIZATION_EXPIRED", result.reasons)
        self.assertEqual(result.projection["decision"]["phase"], "BLOCKED_UNAUTHORIZED_SCOPE")

    def test_unauthorized_sha_drift_blocks(self):
        values = lifecycle_events(with_merge=False)
        changed = event(
            "PR_HEAD_CHANGED",
            {"pr_number": 42, "from_sha": HEAD, "to_sha": NEXT},
            sequence=100,
            sha=NEXT,
            occurred_at="2026-11-12T00:05:00Z",
        )
        result = reduce(values + [changed])
        self.assertIn("UNAUTHORIZED_SHA_DRIFT", result.reasons)
        self.assertEqual(result.projection["decision"]["phase"], "BLOCKED_RECONCILIATION")

    def test_authorized_rework_advances_attempt_without_side_effect(self):
        values = lifecycle_events(with_merge=False)
        trigger = "trigger-" + HEAD
        authorized = event(
            "REWORK_AUTHORIZED",
            {
                "from_sha": HEAD,
                "to_sha": NEXT,
                "trigger_event_id": trigger,
                "prior_attempt": 1,
                "grant_id": "grant-1",
            },
            sequence=100,
            occurred_at="2026-11-12T00:05:00Z",
        )
        changed = event(
            "PR_HEAD_CHANGED",
            {"pr_number": 42, "from_sha": HEAD, "to_sha": NEXT},
            sequence=101,
            sha=NEXT,
            occurred_at="2026-11-12T00:06:00Z",
            causation_id=authorized.event_id,
        )
        result = reduce(values + [authorized, changed])
        self.assertNotIn("UNAUTHORIZED_SHA_DRIFT", result.reasons)
        self.assertEqual(result.projection["facts"]["attempt"], 2)
        self.assertEqual(result.projection["facts"]["pr_head_sha"], NEXT)

    def test_qa_authentication_requires_current_head_and_digest(self):
        values = lifecycle_events(with_merge=False)
        qa_event = next(item for item in values if item.type == "QA_RESULT_RECEIVED")
        changed = event(
            "QA_AUTHENTICATED",
            {
                "review_id": "9002",
                "review_commit_id": NEXT,
                "qa_result_digest": digest_payload(qa_event.payload),
                "artifact_digest": "sha256:" + "2" * 64,
                "runner_sha": BASE,
                "qa_contract_sha": BASE,
            },
            sequence=100,
            occurred_at="2026-11-12T00:05:00Z",
        )
        result = reduce(values + [changed])
        self.assertIn("QA_AUTHENTICATION_MISMATCH", result.reasons)
        self.assertFalse(result.projection["facts"]["qa_authenticated"])


class TestProjectionAndReconciliation(unittest.TestCase):
    def test_projection_tamper_is_detected_once(self):
        values = lifecycle_events()
        result = reduce(values)
        ledger = ledger_from_reduction(result, REPO, None)
        ledger["tasks"][0]["decision"]["reason"] = "forged"
        now = datetime.now(timezone.utc)
        audit = {
            "exists": True,
            "latest_conclusion": "success",
            "latest_completed_at": now.isoformat(),
            "latest_head_sha": MAIN,
            "main_tip_sha": MAIN,
            "latest_head_on_main": True,
        }
        report = reconcile_projection(result, ledger, audit=audit, now=now)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "BLOCKED_RECONCILIATION")
        self.assertTrue(report["first_divergence"].startswith("$.tasks[0]"))

    def test_latest_failed_audit_never_falls_back_to_old_success(self):
        values = lifecycle_events()
        result = reduce(values)
        ledger = ledger_from_reduction(result, REPO, None)
        now = datetime.now(timezone.utc)
        audit = {
            "exists": True,
            "latest_conclusion": "failure",
            "latest_completed_at": now.isoformat(),
            "latest_head_sha": MAIN,
            "main_tip_sha": MAIN,
            "latest_head_on_main": True,
        }
        report = reconcile_projection(result, ledger, audit=audit, now=now)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "AUDIT_LATEST_RUN_NOT_SUCCESS")

    def test_genesis_ledger_is_deterministic(self):
        first = genesis_ledger(REPO)
        second = genesis_ledger(REPO)
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        self.assertEqual(first["source"]["event_count"], 0)
        self.assertEqual(first["source"]["projection_digest"], hashlib.sha256(b"[]\n").hexdigest())

    def test_incomplete_event_set_requires_human(self):
        result = reduce(lifecycle_events()[:2], complete=False)
        self.assertEqual(result.projection["decision"]["phase"], "REQUIRES_HUMAN")
        self.assertIsNone(result.projection["decision"]["role"])

    def test_stale_is_projection_only_and_not_terminal(self):
        result = reduce(lifecycle_events(), stale=True)
        self.assertEqual(result.projection["decision"]["phase"], "STALE")
        self.assertIsNone(result.projection["decision"]["role"])
        self.assertNotIn(Phase.STALE, TERMINAL_PHASES)
        self.assertNotIn(Phase.REQUIRES_HUMAN, TERMINAL_PHASES)


class TestJournalAggregateCAS(unittest.TestCase):
    def test_first_append_and_idempotent_replay(self):
        journal = StateJournal(":memory:")
        result = reduce(lifecycle_events())
        events = list(result.ordered_events)
        version = journal.append_projection(
            TASK,
            0,
            events,
            result.projection,
            projection_digest=result.projection_digest,
            event_log_digest=result.event_log_digest,
        )
        self.assertEqual(version, len(events))
        stored = journal.get_projection(TASK)
        self.assertEqual(stored["projection_digest"], result.projection_digest)
        version2 = journal.append_projection(
            TASK,
            version,
            events,
            result.projection,
            projection_digest=result.projection_digest,
            event_log_digest=result.event_log_digest,
        )
        self.assertEqual(version2, version)
        self.assertEqual(len(journal.get_events(TASK)), len(events))

    def test_wrong_expected_version_rolls_back(self):
        journal = StateJournal(":memory:")
        result = reduce(lifecycle_events())
        journal.append_projection(
            TASK,
            0,
            list(result.ordered_events),
            result.projection,
            projection_digest=result.projection_digest,
            event_log_digest=result.event_log_digest,
        )
        with self.assertRaises(ConcurrencyConflictError):
            journal.append_projection(
                TASK,
                1,
                [],
                result.projection,
                projection_digest=result.projection_digest,
                event_log_digest=result.event_log_digest,
            )


class TestStaticAndRoutingBoundaries(unittest.TestCase):
    def test_reducer_has_no_io_imports_or_side_effect_calls(self):
        path = Path("packages/fpf_coordinator/dispatch/reducer.py")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden_modules = {
            "urllib", "requests", "subprocess", "socket", "pathlib",
            "os", "http", "sqlite3", "github_source",
        }
        imported = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        self.assertFalse(imported & forbidden_modules)
        self.assertNotIn("make_packet", calls)
        self.assertNotIn("increment_attempt", calls)
        self.assertNotIn("open", calls)

    def test_state_ledger_is_gate_pr_for_modify_rename_and_delete(self):
        path = "packages/fpf_coordinator/dispatch/state-ledger.json"
        self.assertEqual(
            classify([path], "POLICY_CHANGE", {path}, "fpf/test"),
            "GATE_PR",
        )
        self.assertEqual(
            classify([path], "POLICY_CHANGE", set(), "fpf/test"),
            "GATE_PR",
        )
        self.assertEqual(
            classify(
                [path, "docs/coordination/project-map.md"],
                "POLICY_CHANGE",
                set(),
                "fpf/test",
            ),
            "GATE_PR",
        )


if __name__ == "__main__":
    unittest.main()
