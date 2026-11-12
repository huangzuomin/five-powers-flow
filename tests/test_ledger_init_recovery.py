# -*- coding: utf-8 -*-
"""C-01 / D-05: controlled INIT, sticky failure, one-shot recovery."""
from __future__ import annotations

import copy
import json
import pathlib

from packages.fpf_coordinator.dispatch.authorization import (
    SCHEMA,
    Verdict,
    authorization_id_for,
    validate_body,
)
from packages.fpf_coordinator.dispatch.claims import InMemoryClaimStore
from packages.fpf_coordinator.dispatch.events import (
    EventBatch,
    normalize_event,
    sha256_hex,
)
from packages.fpf_coordinator.dispatch.ledger import (
    HistoryFacts,
    LedgerRefused,
    evaluate_ledger,
    init_ledger,
    ledger_init_record,
    ledger_recoveries,
)
from packages.fpf_coordinator.dispatch.reconcile import reconcile_projection
from packages.fpf_coordinator.dispatch.reducer import reduce_events

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "g4-event-log-11.jsonl"
FIXTURE_SHA256 = "1043faad495251a38052275d3a4c27c0132464e29f5e5f2114941f2fd8576d36"
# The captured log is byte-identical except for one trailing suppression
# comment, demanded because the real check name is "secret-scan".  Removing
# that comment must reproduce the original capture exactly.
FIXTURE_CAPTURE_SHA256 = "493bfa95780981f23bfa743c7fb7651bdc0f435d167d1a3d422cebfb5ea5d317"
FIXTURE_SCAN_NOTE = "  # fpf-secret-scan: allow — the real workflow check name is secret-scan"
TASK = "FPF2-G4-REDUCER-01"
TIP = "7" * 40
MERGE = "8" * 40


def load_reduction(*, complete: bool = True):
    raw = FIXTURE.read_text(encoding="utf-8")
    assert sha256_hex(raw.encode("utf-8")) == FIXTURE_SHA256
    capture = raw.replace(FIXTURE_SCAN_NOTE, "", 1)
    assert sha256_hex(capture.encode("utf-8")) == FIXTURE_CAPTURE_SHA256
    events = tuple(
        normalize_event(json.loads(line))
        for line in capture.splitlines() if line.strip()
    )
    batch = EventBatch(events=events, complete=complete)
    return reduce_events(batch, task_id=TASK, project_id="FPF")


def genesis_ledger() -> dict:
    return {
        "schema_version": "fpf.state-ledger/v1",
        "source": {
            "as_of_event_id": None, "as_of_occurred_at": None,
            "audit_check_run_id": None, "audit_completed_at": None,
            "audit_run_id": None, "backend": "github", "complete": True,
            "event_count": 0, "event_ids": [],
            "event_log_digest": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
            "generated_by": "fpf-state-projector/v1", "pending_event_count": 0,
            "projection_digest": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
            "repo": "huangzuomin/five-powers-flow",
        },
        "tasks": [],
    }


def init_authorization(**over):
    body = {
        "schema": SCHEMA, "kind": "LEDGER_INIT", "repo": "huangzuomin/five-powers-flow",
        "task_id": TASK, "scope": "first projection", "one_time": True,
        "baseline_sha": TIP, "baseline_ledger_blob_sha": None,
        "expected_history_commits": 0, "reason": "test",
    }
    body.update(over)
    body["authorization_id"] = authorization_id_for(body)
    return validate_body(body)


def recovery_authorization(init_id: str, **over):
    body = {
        "schema": SCHEMA, "kind": "LEDGER_RECOVERY", "repo": "huangzuomin/five-powers-flow",
        "task_id": TASK, "scope": "one shot recovery", "one_time": True,
        "tip_sha": TIP, "failure_check_run_id": 99, "init_id": init_id,
        "reason": "operator authorised",
    }
    body.update(over)
    body["authorization_id"] = authorization_id_for(body)
    return validate_body(body)


def verified() -> Verdict:
    return Verdict("VERIFIED", "AUTHORIZATION_VERIFIED", {"merge_commit_sha": MERGE})


FAILURE_AUDIT = {
    "exists": True,
    "latest_conclusion": "failure",
    "latest_check_run_id": 99,
    "latest_head_sha": TIP,
    "main_tip_sha": TIP,
    "latest_head_on_main": True,
    "latest_completed_at": "2026-11-12T00:00:00Z",
}


def test_c_t1_initializes_from_the_real_eleven_event_log() -> None:
    reduction = load_reduction()
    ledger = init_ledger(
        reduction, genesis_ledger(),
        authorization=init_authorization(), verdict=verified(),
        history=HistoryFacts(0, None), local_blob_sha=None,
    )
    assert ledger["source"]["event_count"] == 11
    assert ledger["source"]["init"]["authorization_id"]
    assert reconcile_projection(reduction, ledger, audit=None)["status"] == "PASS"
    twice = init_ledger(
        reduction, genesis_ledger(),
        authorization=init_authorization(), verdict=verified(),
        history=HistoryFacts(0, None), local_blob_sha=None,
    )
    assert json.dumps(ledger, sort_keys=True) == json.dumps(twice, sort_keys=True)


def test_c_t2_a_second_history_commit_blocks_init() -> None:
    try:
        init_ledger(
            load_reduction(), genesis_ledger(),
            authorization=init_authorization(
                expected_history_commits=1, baseline_ledger_blob_sha="b" * 40,
            ),
            verdict=verified(),
            history=HistoryFacts(2, "b" * 40), local_blob_sha="b" * 40,
        )
    except LedgerRefused as exc:
        assert exc.reason == "INIT_HISTORY_NOT_EMPTY"
    else:  # pragma: no cover
        raise AssertionError("INIT should have been refused")


def test_c_t3_local_blob_drift_blocks_init() -> None:
    try:
        init_ledger(
            load_reduction(), genesis_ledger(),
            authorization=init_authorization(
                expected_history_commits=1, baseline_ledger_blob_sha="b" * 40,
            ),
            verdict=verified(),
            history=HistoryFacts(1, "b" * 40), local_blob_sha="c" * 40,
        )
    except LedgerRefused as exc:
        assert exc.reason == "INIT_BASELINE_DRIFT"
    else:  # pragma: no cover
        raise AssertionError("INIT should have been refused")


def test_c_t4_an_incomplete_replay_blocks_init() -> None:
    try:
        init_ledger(
            load_reduction(complete=False), genesis_ledger(),
            authorization=init_authorization(), verdict=verified(),
            history=HistoryFacts(0, None), local_blob_sha=None,
        )
    except LedgerRefused as exc:
        assert exc.reason == "INIT_REPLAY_INCOMPLETE"
    else:  # pragma: no cover
        raise AssertionError("INIT should have been refused")


def test_c_t5_no_authorization_blocks_a_genesis_ledger() -> None:
    decision = evaluate_ledger(
        load_reduction(), genesis_ledger(),
        audit=None, authorization=None, verdict=None, history=None,
        local_blob_sha=None, current_tip=TIP, claim_store=None,
    )
    assert decision["action"] == "BLOCKED"
    assert decision["reason"] == "AUTHORIZATION_MISSING"


def test_c_t6_a_populated_ledger_without_init_record_is_tampering() -> None:
    ledger = genesis_ledger()
    ledger["tasks"] = [{"task_id": TASK}]
    decision = evaluate_ledger(
        load_reduction(), ledger,
        audit=None, authorization=init_authorization(), verdict=verified(),
        history=HistoryFacts(0, None), local_blob_sha=None,
        current_tip=TIP, claim_store=None,
    )
    assert decision["reason"] == "INIT_RECORD_MISSING"


def _initialized_ledger():
    reduction = load_reduction()
    ledger = init_ledger(
        reduction, genesis_ledger(),
        authorization=init_authorization(), verdict=verified(),
        history=HistoryFacts(0, None), local_blob_sha=None,
    )
    return reduction, ledger


def test_sticky_failure_survives_without_an_authorization() -> None:
    reduction, ledger = _initialized_ledger()
    decision = evaluate_ledger(
        reduction, ledger, audit=FAILURE_AUDIT, authorization=None, verdict=None,
        history=None, local_blob_sha=None, current_tip=TIP,
        claim_store=InMemoryClaimStore(),
    )
    assert decision["action"] == "BLOCKED"
    assert decision["reason"] == "AUDIT_LATEST_RUN_NOT_SUCCESS"


def test_d_7_3_recovery_is_consumed_even_when_the_submit_never_lands() -> None:
    reduction, ledger = _initialized_ledger()
    store = InMemoryClaimStore()
    init_id = ledger_init_record(ledger)["init_id"]
    first = evaluate_ledger(
        reduction, ledger, audit=FAILURE_AUDIT,
        authorization=recovery_authorization(init_id), verdict=verified(),
        history=None, local_blob_sha=None, current_tip=TIP, claim_store=store,
    )
    assert first["action"] == "RECOVERY"
    second = evaluate_ledger(
        reduction, ledger, audit=FAILURE_AUDIT,
        authorization=recovery_authorization(init_id), verdict=verified(),
        history=None, local_blob_sha=None, current_tip=TIP, claim_store=store,
    )
    assert second["reason"] == "AUTHORIZATION_ALREADY_CONSUMED"


def test_a_recovery_authorization_for_another_tip_is_stale() -> None:
    reduction, ledger = _initialized_ledger()
    init_id = ledger_init_record(ledger)["init_id"]
    decision = evaluate_ledger(
        reduction, ledger, audit=FAILURE_AUDIT,
        authorization=recovery_authorization(init_id, tip_sha="9" * 40),
        verdict=verified(),
        history=None, local_blob_sha=None, current_tip=TIP,
        claim_store=InMemoryClaimStore(),
    )
    assert decision["reason"] == "AUTHORIZATION_STALE"


def test_d_7_5_tampering_after_recovery_blocks_again() -> None:
    reduction, ledger = _initialized_ledger()
    store = InMemoryClaimStore()
    init_id = ledger_init_record(ledger)["init_id"]
    recovered = evaluate_ledger(
        reduction, ledger, audit=FAILURE_AUDIT,
        authorization=recovery_authorization(init_id), verdict=verified(),
        history=None, local_blob_sha=None, current_tip=TIP, claim_store=store,
    )["ledger"]
    assert ledger_recoveries(recovered)
    tampered = copy.deepcopy(recovered)
    tampered["tasks"][0]["phase"] = "DELIVERY_REPORT"
    decision = evaluate_ledger(
        reduction, tampered, audit=None, authorization=None, verdict=None,
        history=None, local_blob_sha=None, current_tip=TIP, claim_store=store,
    )
    assert decision["reason"] == "BLOCKED_RECONCILIATION"


def test_d_7_4_a_claim_that_reads_back_differently_is_refused() -> None:
    reduction, ledger = _initialized_ledger()
    init_id = ledger_init_record(ledger)["init_id"]

    class DriftingStore(InMemoryClaimStore):
        def create(self, document):
            tampered = dict(document)
            tampered["tip_sha"] = "9" * 40
            super().create(tampered)

    decision = evaluate_ledger(
        reduction, ledger, audit=FAILURE_AUDIT,
        authorization=recovery_authorization(init_id), verdict=verified(),
        history=None, local_blob_sha=None, current_tip=TIP,
        claim_store=DriftingStore(),
    )
    assert decision["reason"] == "CLAIM_FIELD_MISMATCH:tip_sha"


def test_a_healthy_ledger_reconciles_without_touching_anything() -> None:
    reduction, ledger = _initialized_ledger()
    healthy = dict(FAILURE_AUDIT)
    healthy["latest_conclusion"] = "success"
    decision = evaluate_ledger(
        reduction, ledger, audit=healthy, authorization=None, verdict=None,
        history=None, local_blob_sha=None, current_tip=TIP, claim_store=None,
    )
    assert decision["action"] == "PASS"
