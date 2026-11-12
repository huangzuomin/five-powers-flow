# -*- coding: utf-8 -*-
"""Ledger lifecycle: genesis INIT, sticky reconcile, and authorised recovery.

The ordering in :func:`evaluate_ledger` *is* the policy:

0. authorization (verified against GitHub facts)
1. structure
2. controlled INIT, only while no ``source.init`` exists
3. replay consistency (permanent block on divergence)
4. sticky failure
5. one-shot authorised recovery
6. bootstrap when the tip has no audit yet
7. normal reconciliation

INIT runs before the replay comparison because a genesis ledger is empty by
construction.  It is not "empty means fresh": the history count, the blob
continuity and a merged authorization must all agree first.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .claims import ClaimConflict, ClaimStore, claim_document, verify_claim
from .events import canonical_json_bytes, sha256_hex
from .reconcile import canonical_ledger, reconcile_projection
from .reducer import Reduction, projection_tasks_digest

LEDGER_SCHEMA = "fpf.state-ledger/v1"


class LedgerRefused(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class HistoryFacts:
    """What the GitHub API says about the ledger file's own history."""

    commit_count: int
    latest_blob_sha: str | None
    baseline_is_ancestor: bool = True


def ledger_tasks(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    tasks = ledger.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(item, dict) for item in tasks):
        raise LedgerRefused("LEDGER_SCHEMA_INVALID", "tasks must be a list of objects")
    return [dict(item) for item in tasks]


def ledger_init_record(ledger: Mapping[str, Any]) -> dict[str, Any] | None:
    source = ledger.get("source")
    if not isinstance(source, Mapping):
        return None
    record = source.get("init")
    return dict(record) if isinstance(record, Mapping) else None


def ledger_recoveries(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = ledger.get("source")
    if not isinstance(source, Mapping):
        return []
    items = source.get("recoveries")
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, Mapping)]


def is_genesis(ledger: Mapping[str, Any]) -> bool:
    source = ledger.get("source")
    if not isinstance(source, Mapping):
        return False
    return (
        ledger.get("tasks") == []
        and list(source.get("event_ids") or []) == []
        and source.get("init") is None
    )


def _expected_tasks(reduction: Reduction) -> list[dict[str, Any]]:
    tasks = [copy.deepcopy(dict(reduction.projection))]
    tasks[0]["aggregate_version"] = 1 + len(reduction.event_ids)
    return tasks


def _init_id(payload: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(dict(payload)))


def init_ledger(
    reduction: Reduction,
    ledger: Mapping[str, Any],
    *,
    authorization: Any,
    verdict: Any,
    history: HistoryFacts,
    local_blob_sha: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write the first full projection, but only under a verified authorization."""
    if not getattr(verdict, "ok", False):
        raise LedgerRefused("AUTHORIZATION_MISSING", str(getattr(verdict, "reason", "")))
    if authorization.kind != "LEDGER_INIT":
        raise LedgerRefused("AUTHORIZATION_KIND_MISMATCH", authorization.kind)
    if not history.baseline_is_ancestor:
        raise LedgerRefused("INIT_BASELINE_NOT_ANCESTOR", str(authorization.baseline_sha or ""))
    if not is_genesis(ledger):
        raise LedgerRefused("INIT_LEDGER_NOT_GENESIS", "source.init already exists or ledger is populated")
    expected_commits = authorization.expected_history_commits
    if expected_commits is None or history.commit_count != expected_commits:
        raise LedgerRefused(
            "INIT_HISTORY_NOT_EMPTY",
            f"expected {expected_commits} history commits, saw {history.commit_count}",
        )
    if expected_commits == 0:
        if history.latest_blob_sha is not None or local_blob_sha is not None:
            raise LedgerRefused("INIT_HISTORY_NOT_EMPTY", "a never-existing ledger cannot have a blob")
    else:
        expected_blob = authorization.baseline_blob_sha
        if not expected_blob or history.latest_blob_sha != expected_blob:
            raise LedgerRefused(
                "INIT_BASELINE_DRIFT",
                f"history blob {history.latest_blob_sha} != authorised {expected_blob}",
            )
        if local_blob_sha != expected_blob:
            raise LedgerRefused("INIT_BASELINE_DRIFT", "working ledger differs from the authorised blob")
    if "EVENT_SET_INCOMPLETE" in set(reduction.reasons) or not reduction.event_ids:
        raise LedgerRefused("INIT_REPLAY_INCOMPLETE", "; ".join(reduction.reasons) or "no events")

    tasks = _expected_tasks(reduction)
    projection_digest = projection_tasks_digest(tasks)
    moment = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    init_payload = {
        "authorization_id": authorization.authorization_id,
        "authorization_merge_commit_sha": (verdict.evidence or {}).get("merge_commit_sha"),
        "baseline_sha": authorization.baseline_sha,
        "baseline_ledger_blob_sha": authorization.baseline_blob_sha,
        "event_log_digest": reduction.event_log_digest,
        "projection_digest": projection_digest,
        "initialized_at": moment,
    }
    new_ledger = {
        "schema_version": LEDGER_SCHEMA,
        "source": {
            "as_of_event_id": reduction.event_ids[-1] if reduction.event_ids else None,
            "as_of_occurred_at": None,
            "audit_check_run_id": None,
            "audit_completed_at": None,
            "audit_run_id": None,
            "backend": "github",
            "complete": "EVENT_SET_INCOMPLETE" not in set(reduction.reasons),
            "event_count": len(reduction.event_ids),
            "event_ids": list(reduction.event_ids),
            "event_log_digest": reduction.event_log_digest,
            "generated_by": "fpf-state-projector/v1",
            "pending_event_count": 0,
            "projection_digest": projection_digest,
            "repo": "huangzuomin/five-powers-flow",
            "init": {
                "init_id": _init_id(init_payload),
                **init_payload,
                "init_projection_digest": projection_digest,
            },
        },
        "tasks": tasks,
    }
    check = reconcile_projection(reduction, new_ledger, audit=None)
    if check.get("status") != "PASS":
        raise LedgerRefused("INIT_SELF_CHECK_FAILED", str(check.get("reason")))
    return new_ledger


def recover_ledger(
    reduction: Reduction,
    ledger: Mapping[str, Any],
    *,
    authorization: Any,
    verdict: Any,
    audit: Mapping[str, Any] | None,
    current_tip: str,
    claim_store: ClaimStore,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not getattr(verdict, "ok", False):
        raise LedgerRefused("AUTHORIZATION_MISSING", str(getattr(verdict, "reason", "")))
    if authorization.kind != "LEDGER_RECOVERY":
        raise LedgerRefused("AUTHORIZATION_KIND_MISMATCH", authorization.kind)
    init = ledger_init_record(ledger)
    if init is None:
        raise LedgerRefused("INIT_RECORD_MISSING", "recovery requires a prior INIT")
    if authorization.init_id != init.get("init_id"):
        raise LedgerRefused("INIT_RECORD_MISSING", "authorization targets a different INIT")
    if str(authorization.tip_sha or "").lower() != str(current_tip).lower():
        raise LedgerRefused("AUTHORIZATION_STALE", "authorization tip is not the current tip")
    latest_failure = int((audit or {}).get("latest_check_run_id") or 0)
    if not latest_failure or int(authorization.failure_check_run_id or 0) != latest_failure:
        raise LedgerRefused("AUTHORIZATION_STALE", "authorization does not bind the current failure")

    replay_check = reconcile_projection(reduction, ledger, audit=None)
    if replay_check.get("status") != "PASS":
        raise LedgerRefused("BLOCKED_RECONCILIATION", str(replay_check.get("reason")))

    projection_digest = str((ledger.get("source") or {}).get("projection_digest") or "")
    document = claim_document(
        authorization_id=authorization.authorization_id,
        tip_sha=current_tip,
        failure_run_id=int(authorization.failure_check_run_id or 0),
        projection_digest=projection_digest,
        claimant_run_id=str((audit or {}).get("audit_run_id") or ""),
        claimed_at=(now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    try:
        claim_store.create(document)
    except ClaimConflict as exc:
        raise LedgerRefused("AUTHORIZATION_ALREADY_CONSUMED", str(exc)) from exc
    ok, reason = verify_claim(claim_store.read(authorization.authorization_id), document)
    if not ok:
        raise LedgerRefused(reason, "claim read-back differs from what was written")

    new_ledger = copy.deepcopy(dict(ledger))
    source = new_ledger.setdefault("source", {})
    recoveries = list(source.get("recoveries") or [])
    recoveries.append({
        "consumption_id": document["consumption_id"],
        "authorization_id": document["authorization_id"],
        "failure_check_run_id": document["failure_run_id"],
        "tip_sha": document["tip_sha"],
        "projection_digest": document["projection_digest"],
        "recovered_at": document["claimed_at"],
        "authorization_merge_commit_sha": (verdict.evidence or {}).get("merge_commit_sha"),
    })
    source["recoveries"] = recoveries
    source["last_audit"] = {
        "check_run_id": None,
        "conclusion": "success",
        "recovered_from": latest_failure,
        "at": document["claimed_at"],
        "tip_sha": current_tip,
    }
    return new_ledger


def evaluate_ledger(
    reduction: Reduction,
    ledger: Mapping[str, Any],
    *,
    audit: Mapping[str, Any] | None,
    authorization: Any | None,
    verdict: Any | None,
    history: HistoryFacts | None,
    local_blob_sha: str | None,
    current_tip: str,
    claim_store: ClaimStore | None,
    now: datetime | None = None,
    require_fresh_audit: bool = False,
) -> dict[str, Any]:
    """Apply the decision order and return the action plus any new ledger."""
    try:
        ledger_tasks(ledger)
    except LedgerRefused as exc:
        return {"action": "BLOCKED", "reason": exc.reason, "detail": exc.detail}

    source = ledger.get("source")
    if not isinstance(source, Mapping):
        return {"action": "BLOCKED", "reason": "LEDGER_SCHEMA_INVALID", "detail": "source"}

    # 2. Controlled INIT, only while no init record exists.
    if ledger_init_record(ledger) is None:
        if not is_genesis(ledger):
            return {
                "action": "BLOCKED",
                "reason": "INIT_RECORD_MISSING",
                "detail": "a populated ledger without source.init is tampering, not genesis",
            }
        if authorization is None or verdict is None or not getattr(verdict, "ok", False):
            reason = (
                str(getattr(verdict, "reason", ""))
                if verdict is not None and getattr(verdict, "reason", "")
                else "AUTHORIZATION_MISSING"
            )
            return {
                "action": "BLOCKED",
                "reason": reason,
                "detail": "a genesis ledger needs a merged LEDGER_INIT authorization",
            }
        else:
            try:
                new_ledger = init_ledger(
                    reduction, ledger,
                    authorization=authorization, verdict=verdict,
                    history=history or HistoryFacts(0, None),
                    local_blob_sha=local_blob_sha, now=now,
                )
                return {
                    "action": "INIT",
                    "reason": "INITIALIZED",
                    "ledger": new_ledger,
                    "evidence": {"init_id": new_ledger["source"]["init"]["init_id"]},
                }
            except LedgerRefused as exc:
                return {"action": "BLOCKED", "reason": exc.reason, "detail": exc.detail}

    # 3-7. Replay comparison owns the rest of the order.
    report = reconcile_projection(
        reduction, ledger, audit=audit, now=now, require_fresh_audit=require_fresh_audit,
    )
    if report.get("status") == "PASS":
        return {"action": "PASS", "reason": "RECONCILED", "report": report}

    if (
        report.get("reason") == "AUDIT_LATEST_RUN_NOT_SUCCESS"
        and authorization is not None
        and verdict is not None
        and getattr(verdict, "ok", False)
        and authorization.kind == "LEDGER_RECOVERY"
        and claim_store is not None
    ):
        try:
            new_ledger = recover_ledger(
                reduction, ledger,
                authorization=authorization, verdict=verdict,
                audit=audit, current_tip=current_tip,
                claim_store=claim_store, now=now,
            )
            return {
                "action": "RECOVERY",
                "reason": "RECOVERED",
                "ledger": new_ledger,
                "evidence": {
                    "recovered_from": int((audit or {}).get("latest_check_run_id") or 0),
                },
            }
        except LedgerRefused as exc:
            return {"action": "BLOCKED", "reason": exc.reason, "detail": exc.detail}

    return {
        "action": "BLOCKED",
        "reason": str(report.get("reason")),
        "detail": str(report.get("detail") or ""),
        "report": report,
    }


def load_ledger(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_ledger(path: Path | str, ledger: Mapping[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(dict(ledger), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ledger_bytes(ledger: Mapping[str, Any]) -> bytes:
    return canonical_ledger(ledger)
