# -*- coding: utf-8 -*-
"""Pure event reducer for the FPF read-only task projection (G4).

The reducer consumes already-fetched, already-normalized events and never
performs I/O.  It does not call ``make_packet``, ``increment_attempt`` or any
daemon scheduler.  The existing ``core.next_action`` remains the sole gate
decision function; the projection simply records its result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .core import CanonicalSnapshot, canonical_url, next_action, validate_sha
from .events import (
    EventBatch, NormalizedEvent, canonical_json, canonical_json_bytes,
    digest_payload, event_log_digest, parse_timestamp, prepare_events, sha256_hex,
)
from .states import Decision, Phase


ADVANCING_EVENTS = frozenset({
    "WORK_ORDER_OPENED",
    "QA_ADMISSION_GRANTED",
    "QA_ADMISSION_REJECTED",
    "DEV_HANDOFF_RECEIVED",
    "POLICY_CHANGE_DELIVERY_RECEIVED",
    "DEV_VALIDATION_PASSED",
    "DEV_VALIDATION_FAILED",
    "QA_PLAN_FROZEN",
    "QA_RESULT_RECEIVED",
    "QA_AUTHENTICATED",
    "PR_MERGED",
})

OBSERVED_PHASE = {
    "DEV_DISPATCHED": Phase.DEV_RUNNING,
    "DEV_RUN_STARTED": Phase.DEV_RUNNING,
    "DEV_RUN_FINISHED": Phase.DEV_HANDOFF_PENDING,
    "DEV_HANDOFF_RECEIVED": Phase.TRUSTED_DEV_VALIDATION,
    "POLICY_CHANGE_DELIVERY_RECEIVED": Phase.TRUSTED_DEV_VALIDATION,
    "QA_DISPATCHED": Phase.QA_RUNNING,
    "QA_RUN_STARTED": Phase.QA_RUNNING,
    "QA_RUN_FINISHED": Phase.QA_EVIDENCE_REVIEW_PENDING,
    "QA_RESULT_RECEIVED": Phase.TRUSTED_QA_VALIDATION,
    "QA_AUTHENTICATED": Phase.QA_PASSED_AWAITING_OWNER_MERGE,
    "MAP_CARD_RECEIVED": Phase.MAP_PR_VALIDATION,
    "MAP_PR_MERGED": Phase.CLOSEOUT_VERIFICATION,
    "CLOSEOUT_VERIFIED": Phase.DELIVERY_REPORT,
}


@dataclass
class FactState:
    task_id: str
    project_id: str
    record_url: str | None = None
    baseline_sha: str | None = None
    max_attempts: int = 3
    scope_authorized: bool = False
    scope_grant_id: str | None = None
    scope: str = ""
    allowed_paths: tuple[str, ...] = ()
    grant_expires_at: str | None = None
    work_order: dict[str, Any] | None = None
    qa_admission: dict[str, Any] | None = None
    dev_card: dict[str, Any] | None = None
    dev_cards_obsolete: list[dict[str, Any]] = field(default_factory=list)
    dev_validated: bool = False
    qa_plan: dict[str, Any] | None = None
    qa_card: dict[str, Any] | None = None
    qa_authenticated: bool = False
    pr_head_sha: str | None = None
    pr_merged: bool = False
    code_merged_sha: str | None = None
    map_card: dict[str, Any] | None = None
    map_pr_merged: bool = False
    attempt: int = 1
    rework_keys: set[str] = field(default_factory=set)
    authorized_transitions: set[tuple[str, str, str]] = field(default_factory=set)
    qa_failures: dict[str, str] = field(default_factory=dict)
    sha_window_open: bool = False
    lifecycle_label: str = "DRAFT_WORK_ORDER"
    observed_phase: str | None = None
    authorization_expired: bool = False

    def snapshot(self, revision: str, reasons: Iterable[str]) -> CanonicalSnapshot | None:
        if not self.record_url or not self.baseline_sha:
            return None
        return CanonicalSnapshot(
            task_id=self.task_id,
            project_id=self.project_id,
            record_url=self.record_url,
            revision=revision,
            baseline_sha=self.baseline_sha,
            pr_head_sha=self.pr_head_sha,
            scope=self.scope,
            allowed_paths=self.allowed_paths,
            scope_authorized=self.scope_authorized,
            work_order=self.work_order,
            qa_admission=self.qa_admission,
            dev_card=self.dev_card,
            dev_validated=self.dev_validated,
            qa_plan=self.qa_plan,
            qa_card=self.qa_card,
            qa_authenticated=self.qa_authenticated,
            pr_merged=self.pr_merged,
            code_merged_sha=self.code_merged_sha,
            map_card=self.map_card,
            map_pr_merged=self.map_pr_merged,
            attempt=self.attempt,
            max_attempts=self.max_attempts,
            last_failure="; ".join(sorted(set(reasons))),
        )

    def facts(self) -> dict[str, Any]:
        return {
            "record_url": self.record_url,
            "baseline_sha": self.baseline_sha,
            "max_attempts": self.max_attempts,
            "scope_grant_id": self.scope_grant_id,
            "scope": self.scope,
            "allowed_paths": list(self.allowed_paths),
            "grant_expires_at": self.grant_expires_at,
            "scope_authorized": self.scope_authorized,
            "work_order": self.work_order is not None,
            "qa_admission_verdict": (
                None if not self.qa_admission else self.qa_admission.get("verdict")
            ),
            "dev_handoff_sha": (
                None if not self.dev_card else self.dev_card.get("tested_code_sha")
            ),
            "dev_validated": self.dev_validated,
            "qa_plan_target_sha": (
                None if not self.qa_plan else self.qa_plan.get("target_head_sha")
            ),
            "qa_verdict": None if not self.qa_card else self.qa_card.get("verdict"),
            "qa_authenticated": self.qa_authenticated,
            "pr_head_sha": self.pr_head_sha,
            "pr_merged": self.pr_merged,
            "code_merged_sha": self.code_merged_sha,
            "map_card": self.map_card is not None,
            "map_pr_merged": self.map_pr_merged,
            "attempt": self.attempt,
            "rework_count": len(self.rework_keys),
            "observed_phase": self.observed_phase,
        }


@dataclass(frozen=True)
class Reduction:
    projection: dict[str, Any]
    projection_digest: str
    event_log_digest: str
    event_ids: tuple[str, ...]
    ordered_events: tuple[NormalizedEvent, ...]
    ignored_events: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection": self.projection,
            "projection_digest": self.projection_digest,
            "event_log_digest": self.event_log_digest,
            "event_ids": list(self.event_ids),
            "ignored_events": list(self.ignored_events),
            "reasons": list(self.reasons),
            "events": [event.to_dict() for event in self.ordered_events],
        }


def _decision_dict(decision: Decision) -> dict[str, Any]:
    return {
        "phase": decision.phase.value,
        "role": decision.role,
        "reason": decision.reason,
        "requires_human": decision.requires_human,
    }


def _blocked(phase: Phase, reason: str, human: bool = False) -> Decision:
    return Decision(phase=phase, role=None, reason=reason, requires_human=human)


def _sha(value: Any) -> str | None:
    if value is None:
        return None
    return validate_sha(str(value))


def _check_qa_card_hash(qa_card: Mapping[str, Any], claimed: str) -> bool:
    expected = digest_payload(dict(qa_card))
    normalized = str(claimed or "").lower().removeprefix("sha256:")
    return bool(normalized) and normalized == expected


def _record_url(repo: str, source: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    explicit = payload.get("record_url")
    if explicit is not None:
        return canonical_url(str(explicit))
    object_id = source.get("object_id")
    if source.get("object") in ("issue", "pull_request") and str(object_id).isdigit():
        return f"https://github.com/{repo}/issues/{int(object_id)}"
    raise ValueError("TASK_OPENED requires a canonical record_url or numeric issue/PR source")


def _fold(facts: FactState, event: NormalizedEvent, reasons: list[str]) -> None:
    payload = event.payload
    event_type = event.type

    if event_type in ADVANCING_EVENTS and facts.scope_authorized and facts.grant_expires_at:
        if parse_timestamp(event.occurred_at) >= parse_timestamp(facts.grant_expires_at):
            facts.authorization_expired = True
            reasons.append("AUTHORIZATION_EXPIRED")

    if event_type == "TASK_OPENED":
        facts.baseline_sha = _sha(payload.get("baseline_sha"))
        facts.max_attempts = int(payload.get("max_attempts", 3))
        facts.record_url = _record_url(str(event.source["repo"]), event.source, payload)
        facts.lifecycle_label = "DRAFT_WORK_ORDER"
        return

    if event_type == "WORK_ORDER_OPENED":
        facts.work_order = dict(payload)
        facts.lifecycle_label = "WORK_ORDER"
        return

    if event_type == "SCOPE_GRANTED":
        grant_id = str(payload["grant_id"])
        expires_at = str(payload["expires_at"])
        if parse_timestamp(expires_at) <= parse_timestamp(event.occurred_at):
            facts.scope_authorized = False
            facts.scope_grant_id = None
            facts.authorization_expired = True
            reasons.append("AUTHORIZATION_EXPIRED")
            return
        if facts.scope_grant_id and facts.scope_grant_id != grant_id:
            facts.dev_card = None
            facts.qa_plan = None
            facts.qa_card = None
            facts.qa_authenticated = False
        facts.scope_grant_id = grant_id
        facts.scope = str(payload.get("scope", ""))
        facts.allowed_paths = tuple(str(item) for item in payload.get("allowed_paths", []))
        facts.grant_expires_at = expires_at
        facts.baseline_sha = _sha(payload.get("baseline_sha"))
        facts.scope_authorized = True
        facts.authorization_expired = False
        return

    if event_type in ("SCOPE_REVOKED", "SCOPE_EXPIRED"):
        if not facts.scope_grant_id or str(payload.get("grant_id")) == facts.scope_grant_id:
            facts.scope_authorized = False
            facts.scope_grant_id = None
            facts.dev_validated = False
            facts.qa_plan = None
            facts.qa_card = None
            facts.qa_authenticated = False
        return

    if event_type == "QA_ADMISSION_GRANTED":
        facts.qa_admission = dict(payload)
        return

    if event_type == "QA_ADMISSION_REJECTED":
        facts.qa_admission = dict(payload)
        return

    if event_type in ("DEV_HANDOFF_RECEIVED", "POLICY_CHANGE_DELIVERY_RECEIVED"):
        if facts.scope_authorized and str(payload.get("grant_id")) != str(facts.scope_grant_id):
            reasons.append("SCOPE_VIOLATION_DETECTED")
        tested = _sha(payload.get("tested_code_sha"))
        if facts.pr_head_sha and tested != facts.pr_head_sha:
            reasons.append("UNAUTHORIZED_SHA_DRIFT")
        if facts.dev_card is not None:
            facts.dev_cards_obsolete.append(dict(facts.dev_card))
        facts.dev_card = dict(payload)
        facts.dev_validated = False
        facts.pr_head_sha = tested
        facts.sha_window_open = True
        facts.lifecycle_label = (
            "POLICY_CHANGE_DELIVERY"
            if event_type == "POLICY_CHANGE_DELIVERY_RECEIVED"
            else "DEV_HANDOFF"
        )
        return

    if event_type in ("DEV_VALIDATION_PASSED", "DEV_VALIDATION_FAILED"):
        tested = _sha(payload.get("tested_code_sha"))
        if tested != facts.pr_head_sha:
            reasons.append("UNAUTHORIZED_SHA_DRIFT")
        if event_type == "DEV_VALIDATION_PASSED" and tested == facts.pr_head_sha:
            facts.dev_validated = True
        elif event_type == "DEV_VALIDATION_FAILED":
            facts.dev_validated = False
        return

    if event_type == "CHECK_RUN_COMPLETED":
        if (str(payload.get("conclusion")) == "success"
                and str(payload.get("check_name")) == "validate"
                and str(payload.get("head_sha")).lower() == str(facts.pr_head_sha)):
            facts.dev_validated = True
        return

    if event_type == "REWORK_AUTHORIZED":
        grant_id = str(payload.get("grant_id"))
        from_sha = _sha(payload.get("from_sha"))
        to_sha = _sha(payload.get("to_sha"))
        trigger = str(payload.get("trigger_event_id"))
        key = "|".join((grant_id, str(from_sha), str(to_sha), trigger))
        if facts.pr_head_sha and from_sha != facts.pr_head_sha:
            reasons.append("UNAUTHORIZED_SHA_DRIFT")
        if int(payload.get("prior_attempt", 0)) != facts.attempt:
            reasons.append("UNAUTHORIZED_SHA_DRIFT")
        if grant_id != str(facts.scope_grant_id):
            reasons.append("SCOPE_VIOLATION_DETECTED")
        if key not in facts.rework_keys:
            facts.rework_keys.add(key)
            facts.attempt = 1 + len(facts.rework_keys)
            facts.authorized_transitions.add((grant_id, str(from_sha), str(to_sha)))
        if facts.dev_card is not None:
            facts.dev_cards_obsolete.append(dict(facts.dev_card))
        facts.dev_card = None
        facts.dev_validated = False
        facts.qa_plan = None
        facts.qa_card = None
        facts.qa_authenticated = False
        facts.sha_window_open = False
        facts.lifecycle_label = "BOUNDED_DEV_REWORK"
        return

    if event_type == "QA_PLAN_FROZEN":
        facts.qa_plan = dict(payload)
        return

    if event_type == "QA_DISPATCHED":
        facts.sha_window_open = True
        facts.lifecycle_label = "QA_RUNNING"
        return

    if event_type == "QA_RESULT_RECEIVED":
        facts.qa_card = dict(payload)
        facts.qa_authenticated = False
        if str(payload.get("verdict")).upper() == "FAIL":
            facts.qa_failures[str(payload.get("tested_sha")).lower()] = event.event_id
        return

    if event_type == "QA_AUTHENTICATED":
        review_sha = _sha(payload.get("review_commit_id"))
        claimed_result_digest = str(payload.get("qa_result_digest") or "")
        artifact_digest = str(payload.get("artifact_digest") or "")
        if (
            facts.qa_card is not None
            and review_sha == facts.pr_head_sha
            and _check_qa_card_hash(facts.qa_card, claimed_result_digest)
            and artifact_digest
        ):
            facts.qa_authenticated = True
        else:
            facts.qa_authenticated = False
            reasons.append("QA_AUTHENTICATION_MISMATCH")
        return

    if event_type == "PR_HEAD_CHANGED":
        from_sha = _sha(payload.get("from_sha"))
        to_sha = _sha(payload.get("to_sha"))
        if facts.sha_window_open:
            if from_sha != facts.pr_head_sha or to_sha != event.sha:
                reasons.append("UNAUTHORIZED_SHA_DRIFT")
                facts.pr_head_sha = to_sha
                return
            grant_id = str(facts.scope_grant_id)
            allowed = (grant_id, str(from_sha), str(to_sha)) in facts.authorized_transitions
            if not allowed and str(from_sha) in facts.qa_failures:
                key = "|".join((
                    grant_id, str(from_sha), str(to_sha),
                    facts.qa_failures[str(from_sha)],
                ))
                allowed = key not in facts.rework_keys
                if allowed:
                    facts.rework_keys.add(key)
                    facts.attempt = 1 + len(facts.rework_keys)
            if not allowed:
                reasons.append("UNAUTHORIZED_SHA_DRIFT")
                facts.pr_head_sha = to_sha
                return
            facts.pr_head_sha = to_sha
            facts.dev_card = None
            facts.dev_validated = False
            facts.qa_plan = None
            facts.qa_card = None
            facts.qa_authenticated = False
            facts.sha_window_open = False
            facts.lifecycle_label = "BOUNDED_DEV_REWORK"
        else:
            facts.pr_head_sha = to_sha
        return

    if event_type == "PR_MERGED":
        facts.pr_merged = True
        facts.code_merged_sha = _sha(payload.get("merge_commit_sha"))
        facts.sha_window_open = False
        facts.lifecycle_label = "MERGED"
        return

    if event_type == "CODE_MERGE_SHA_RECORDED":
        facts.code_merged_sha = _sha(payload.get("merge_commit_sha"))
        return

    if event_type == "MAP_CARD_RECEIVED":
        facts.map_card = dict(payload)
        facts.lifecycle_label = "MAP_CARD"
        return

    if event_type == "MAP_PR_MERGED":
        facts.map_pr_merged = True
        facts.lifecycle_label = "MAP_MERGED"
        return

    if event_type == "CLOSEOUT_VERIFIED":
        facts.lifecycle_label = "CLOSEOUT"
        return

    if event_type == "DELIVERY_REPORT_RECORDED":
        facts.lifecycle_label = "DELIVERY_REPORTED"
        return

    if event_type == "PROJECTION_DRIFT_DETECTED":
        reasons.append("PROJECTION_DRIFT_DETECTED")
        return

    if event_type == "EVIDENCE_DIGEST_MISMATCH":
        reasons.append("EVIDENCE_DIGEST_MISMATCH")
        return

    if event_type == "SCOPE_VIOLATION_DETECTED":
        reasons.append("SCOPE_VIOLATION_DETECTED")
        return

    if event_type == "TASK_CANCELLED":
        reasons.append("TASK_CANCELLED")
        return

    if event_type == "HUMAN_RESOLUTION_REQUIRED":
        reasons.append("HUMAN_RESOLUTION_REQUIRED")
        return


def _final_decision(
    facts: FactState,
    revision: str,
    reasons: list[str],
    complete: bool,
    stale: bool,
) -> Decision:
    reason_set = set(reasons)
    if "EVENT_ENVELOPE_TAMPERED" in reason_set or "EVIDENCE_DIGEST_MISMATCH" in reason_set:
        return _blocked(Phase.BLOCKED_EVIDENCE_TAMPERED, "Event envelope or evidence digest is tampered")
    if "TASK_CANCELLED" in reason_set:
        return _blocked(Phase.CANCELLED, "Task cancelled by authoritative event")
    if (
        facts.authorization_expired
        or "AUTHORIZATION_EXPIRED" in reason_set
        or "SCOPE_VIOLATION_DETECTED" in reason_set
    ):
        return _blocked(Phase.BLOCKED_UNAUTHORIZED_SCOPE, "Scope grant expired, revoked or violated")
    if stale:
        return _blocked(Phase.STALE, "Latest successful audit watermark is stale")
    if "HUMAN_RESOLUTION_REQUIRED" in reason_set:
        return _blocked(Phase.REQUIRES_HUMAN, "A human resolution event was received", human=True)
    if (
        "PROJECTION_DRIFT_DETECTED" in reason_set
        or "UNAUTHORIZED_SHA_DRIFT" in reason_set
        or "CAUSAL_GRAPH_CONFLICT" in reason_set
        or ("ORPHAN_MISSING_PREDECESSOR" in reason_set and complete)
    ):
        return _blocked(Phase.BLOCKED_RECONCILIATION, "Remote facts and event graph require reconciliation")
    if not complete:
        return _blocked(Phase.REQUIRES_HUMAN, "Event set is incomplete; absence is not a fact", human=True)
    snapshot = facts.snapshot(revision, reasons)
    if snapshot is None:
        return Decision(
            phase=Phase.TASK_INTAKE,
            role=None,
            reason="Task intake event has not established a canonical record and baseline",
        )
    return next_action(snapshot)


def reduce_events(
    batch: EventBatch,
    *,
    task_id: str,
    project_id: str,
    complete: bool | None = None,
    stale: bool = False,
) -> Reduction:
    """Fold a batch into a deterministic, read-only task projection."""
    prepared = prepare_events(batch)
    is_complete = batch.complete if complete is None else bool(complete)
    reasons = list(prepared.reasons)
    if not is_complete:
        reasons.append("EVENT_SET_INCOMPLETE")
    facts = FactState(task_id=task_id, project_id=project_id)
    trace: list[dict[str, Any]] = []
    applied: list[str] = []
    conflicts: list[dict[str, Any]] = []

    for event in prepared.ordered:
        if event.task_id != task_id:
            conflicts.append({
                "event_id": event.event_id,
                "reason": "FOREIGN_TASK_EVENT",
            })
            continue
        before = len(reasons)
        _fold(facts, event, reasons)
        if event.type in OBSERVED_PHASE:
            facts.observed_phase = OBSERVED_PHASE[event.type].value
        decision = _final_decision(facts, event.event_id, reasons, is_complete, stale)
        if facts.lifecycle_label == "DRAFT_WORK_ORDER" and event.type == "TASK_OPENED":
            facts.lifecycle_label = "TASK_INTAKE"
        trace.append({
            "event_id": event.event_id,
            "type": event.type,
            "occurred_at": event.occurred_at,
            "observed_phase": facts.observed_phase,
            "decision_phase": decision.phase.value,
            "new_reasons": reasons[before:],
        })
        applied.append(event.event_id)

    decision = _final_decision(
        facts,
        applied[-1] if applied else "genesis",
        reasons,
        is_complete,
        stale,
    )
    if facts.lifecycle_label == "DRAFT_WORK_ORDER" and facts.pr_merged:
        facts.lifecycle_label = "MERGED"
    projection = {
        "task_id": task_id,
        "project_id": project_id,
        "lifecycle_label": facts.lifecycle_label,
        "decision": _decision_dict(decision),
        "facts": facts.facts(),
        "applied_event_ids": applied,
        "conflicts": conflicts,
        "reduction_trace": trace,
    }
    projection_digest = sha256_hex(canonical_json_bytes(projection))
    projection["projection_digest"] = projection_digest
    ordered = prepared.ordered
    return Reduction(
        projection=projection,
        projection_digest=projection_digest,
        event_log_digest=event_log_digest(ordered),
        event_ids=tuple(event.event_id for event in ordered),
        ordered_events=ordered,
        ignored_events=prepared.ignored,
        reasons=tuple(sorted(set(reasons))),
    )


def projection_tasks_digest(tasks: Iterable[Mapping[str, Any]]) -> str:
    return sha256_hex(canonical_json_bytes([dict(task) for task in tasks]))
