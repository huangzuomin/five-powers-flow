# -*- coding: utf-8 -*-
"""Pure Task Event normalization, identity and deterministic ordering.

This module has no network, filesystem or subprocess access.  It turns an
already-fetched platform event into the canonical FPF envelope used by the
projection reducer.  The GitHub reader lives in ``github_source.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "fpf.task-event/v1"
REPLAY_POLICY = "PROJECTION_ONLY"

HEX64_RE = re.compile(r"^[a-f0-9]{64}$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")

EVENT_TYPES = frozenset({
    "TASK_OPENED",
    "WORK_ORDER_OPENED",
    "SCOPE_GRANTED",
    "SCOPE_REVOKED",
    "SCOPE_EXPIRED",
    "QA_ADMISSION_GRANTED",
    "QA_ADMISSION_REJECTED",
    "DEV_DISPATCHED",
    "DEV_RUN_STARTED",
    "DEV_RUN_FINISHED",
    "DEV_HANDOFF_RECEIVED",
    "POLICY_CHANGE_DELIVERY_RECEIVED",
    "DEV_VALIDATION_PASSED",
    "DEV_VALIDATION_FAILED",
    "REWORK_AUTHORIZED",
    "QA_PLAN_FROZEN",
    "QA_DISPATCHED",
    "QA_RUN_STARTED",
    "QA_RUN_FINISHED",
    "QA_RESULT_RECEIVED",
    "QA_AUTHENTICATED",
    "PR_HEAD_CHANGED",
    "PR_MERGED",
    "CODE_MERGE_SHA_RECORDED",
    "MAP_CARD_RECEIVED",
    "MAP_PR_MERGED",
    "CLOSEOUT_VERIFIED",
    "DELIVERY_REPORT_RECORDED",
    "CHECK_RUN_COMPLETED",
    "WORKFLOW_RUN_COMPLETED",
    "PROJECTION_DRIFT_DETECTED",
    "EVIDENCE_DIGEST_MISMATCH",
    "SCOPE_VIOLATION_DETECTED",
    "TASK_CANCELLED",
    "HUMAN_RESOLUTION_REQUIRED",
})

ENVELOPE_KEYS = frozenset({
    "schema_version", "event_id", "type", "task_id", "project_id",
    "aggregate_id", "actor", "source", "sha", "occurred_at",
    "payload_digest", "payload", "correlation_id", "causation_id",
    "replay_policy",
})
ACTOR_KEYS = frozenset({"login", "kind"})
SOURCE_KEYS = frozenset({"backend", "repo", "object", "object_id", "sequence"})

# Required payload fields are the minimum a producer must supply.  A bounded
# optional set keeps unknown, silently-ignored authority fields out.
PAYLOAD_REQUIRED: dict[str, frozenset[str]] = {
    "TASK_OPENED": frozenset({"task_id", "project_id", "baseline_sha", "max_attempts", "created_at"}),
    "WORK_ORDER_OPENED": frozenset({"work_order_id", "task_id"}),
    "SCOPE_GRANTED": frozenset({"grant_id", "scope", "allowed_paths", "expires_at", "baseline_sha"}),
    "SCOPE_REVOKED": frozenset({"grant_id", "revoked_at"}),
    "SCOPE_EXPIRED": frozenset({"grant_id", "expired_at"}),
    "QA_ADMISSION_GRANTED": frozenset({"verdict", "qa_plan_sha", "reason"}),
    "QA_ADMISSION_REJECTED": frozenset({"verdict", "qa_plan_sha", "reason"}),
    "DEV_HANDOFF_RECEIVED": frozenset({
        "tested_code_sha", "baseline_sha", "grant_id", "author", "checks",
    }),
    "POLICY_CHANGE_DELIVERY_RECEIVED": frozenset({
        "tested_code_sha", "baseline_sha", "grant_id", "author", "checks",
    }),
    "DEV_VALIDATION_PASSED": frozenset({"tested_code_sha", "result", "evidence_digest"}),
    "DEV_VALIDATION_FAILED": frozenset({"tested_code_sha", "result", "evidence_digest"}),
    "REWORK_AUTHORIZED": frozenset({
        "from_sha", "to_sha", "trigger_event_id", "prior_attempt", "grant_id",
    }),
    "QA_PLAN_FROZEN": frozenset({"target_head_sha", "qa_contract_sha", "profile"}),
    "QA_RESULT_RECEIVED": frozenset({
        "verdict", "tested_sha", "task_id", "author", "checks",
        "evidence_manifest_sha256", "qa_run_id", "qa_artifact_id",
    }),
    "QA_AUTHENTICATED": frozenset({
        "review_id", "review_commit_id", "qa_result_digest",
        "artifact_digest", "runner_sha", "qa_contract_sha",
    }),
    "PR_HEAD_CHANGED": frozenset({"pr_number", "from_sha", "to_sha"}),
    "CHECK_RUN_COMPLETED": frozenset({"check_name", "conclusion", "head_sha", "app_id"}),
    "WORKFLOW_RUN_COMPLETED": frozenset({
        "workflow_path", "run_id", "head_sha", "conclusion", "actor", "triggering_actor",
    }),
    "PROJECTION_DRIFT_DETECTED": frozenset({
        "expected_digest", "observed_digest", "first_divergence",
    }),
    "EVIDENCE_DIGEST_MISMATCH": frozenset({
        "expected_digest", "observed_digest", "artifact_id",
    }),
}

PAYLOAD_ALLOWED_EXTRA = frozenset({
    "record_url", "project_id", "baseline_sha", "head_sha", "grant_id",
    "scope", "allowed_paths", "expires_at", "author", "checks", "reason",
    "profile", "verdict", "tested_sha", "task_id", "prior_attempt",
    "from_sha", "to_sha", "trigger_event_id", "pr_number", "merge_commit_sha",
    "workflow_path", "run_id", "actor", "triggering_actor", "artifact_digest",
    "qa_result_digest", "evidence_manifest_sha256", "runner_sha",
    "qa_contract_sha", "qa_run_id", "qa_artifact_id", "review_id",
    "review_commit_id", "review_state", "delivery_kind", "changed_files",
    "risk_acknowledged", "authorization_ref", "authorized_by", "scope_expires_at",
    "check_name", "conclusion", "app_id", "head_sha", "expected_digest",
    "observed_digest", "first_divergence", "artifact_id", "result",
    "evidence_digest", "work_order_id", "max_attempts", "created_at",
    "revoked_at", "expired_at", "map_pr_number", "delivery_report", "merged_by",
})


class EventValidationError(ValueError):
    """An envelope or payload did not satisfy the closed event schema."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__((reason + (": " + detail if detail else "")).strip())


@dataclass(frozen=True)
class EventBatch:
    events: tuple["NormalizedEvent", ...]
    cursor: str | None = None
    complete: bool = True


@dataclass(frozen=True)
class NormalizedEvent:
    schema_version: str
    event_id: str
    type: str
    task_id: str
    project_id: str
    aggregate_id: str
    actor: dict[str, str]
    source: dict[str, Any]
    sha: str | None
    occurred_at: str
    payload_digest: str
    payload: dict[str, Any]
    correlation_id: str | None
    causation_id: str | None
    replay_policy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "type": self.type,
            "task_id": self.task_id,
            "project_id": self.project_id,
            "aggregate_id": self.aggregate_id,
            "actor": dict(self.actor),
            "source": dict(self.source),
            "sha": self.sha,
            "occurred_at": self.occurred_at,
            "payload_digest": self.payload_digest,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "replay_policy": self.replay_policy,
        }

    @property
    def fact_key(self) -> tuple[Any, ...]:
        return (
            self.type,
            self.source.get("object"),
            str(self.source.get("object_id")),
            self.sha or "",
            self.payload_digest,
        )

    @property
    def order_key(self) -> tuple[str, int, str]:
        return (self.occurred_at, int(self.source.get("sequence") or 0), self.event_id)


@dataclass(frozen=True)
class PreparedEvents:
    ordered: tuple[NormalizedEvent, ...]
    ignored: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]


def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise EventValidationError("INVALID_PAYLOAD", "object keys must be strings")
            out[_nfc(key)] = _nfc(item)
        return out
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise EventValidationError("INVALID_PAYLOAD", f"non-JSON scalar {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Canonical JSON: sorted keys, compact separators, UTF-8 safe, no NaN."""
    return json.dumps(
        _nfc(value), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )


def canonical_json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def normalize_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            moment = datetime.fromisoformat(text)
        except ValueError as exc:
            raise EventValidationError("INVALID_TIMESTAMP", str(value)) from exc
    else:
        raise EventValidationError("INVALID_TIMESTAMP", repr(value))
    if moment.tzinfo is None:
        raise EventValidationError("INVALID_TIMESTAMP", "timezone is required")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_timestamp(value: str) -> datetime:
    normalized = normalize_timestamp(value)
    return datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_payload(payload: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(dict(payload)))


def _validate_sha_or_null(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not SHA_RE.fullmatch(value.lower()):
        raise EventValidationError("INVALID_SHA", f"{field}={value!r}")
    return value.lower()


def _validate_payload(event_type: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise EventValidationError("INVALID_PAYLOAD", "payload must be an object")
    normalized = _nfc(payload)
    required = PAYLOAD_REQUIRED.get(event_type, frozenset())
    missing = required - set(normalized)
    if missing:
        raise EventValidationError("MISSING_PAYLOAD_FIELD", ", ".join(sorted(missing)))
    unknown = set(normalized) - required - PAYLOAD_ALLOWED_EXTRA
    if unknown:
        raise EventValidationError("UNKNOWN_PAYLOAD_FIELD", ", ".join(sorted(unknown)))
    if "max_attempts" in normalized:
        if not isinstance(normalized["max_attempts"], int) or not (1 <= normalized["max_attempts"] <= 10):
            raise EventValidationError("INVALID_PAYLOAD", "max_attempts must be 1..10")
    for key in ("baseline_sha", "tested_code_sha", "head_sha", "from_sha", "to_sha",
                "tested_sha", "runner_sha", "qa_contract_sha", "review_commit_id"):
        if key in normalized:
            _validate_sha_or_null(normalized[key], key)
    return normalized


def _event_identity_fields(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": envelope["schema_version"],
        "type": envelope["type"],
        "task_id": envelope["task_id"],
        "project_id": envelope["project_id"],
        "aggregate_id": envelope["aggregate_id"],
        "actor": envelope["actor"],
        "source": envelope["source"],
        "sha": envelope["sha"],
        "occurred_at": envelope["occurred_at"],
        "payload_digest": envelope["payload_digest"],
        "correlation_id": envelope["correlation_id"],
        "causation_id": envelope["causation_id"],
    }


def compute_event_id(envelope: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(_event_identity_fields(envelope)))


def build_event(
    *,
    type: str,
    task_id: str,
    project_id: str,
    actor: Mapping[str, Any],
    source: Mapping[str, Any],
    occurred_at: Any,
    payload: Mapping[str, Any],
    sha: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> NormalizedEvent:
    """Construct and validate a canonical event from an authenticated source."""
    if type not in EVENT_TYPES:
        raise EventValidationError("UNKNOWN_EVENT_TYPE", type)
    actor_obj = _nfc(dict(actor))
    source_obj = _nfc(dict(source))
    payload_obj = _validate_payload(type, dict(payload))
    raw = {
        "schema_version": SCHEMA_VERSION,
        "event_id": "0" * 64,
        "type": type,
        "task_id": str(task_id),
        "project_id": str(project_id),
        "aggregate_id": str(task_id),
        "actor": actor_obj,
        "source": source_obj,
        "sha": _validate_sha_or_null(sha, "sha"),
        "occurred_at": normalize_timestamp(occurred_at),
        "payload_digest": digest_payload(payload_obj),
        "payload": payload_obj,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "replay_policy": REPLAY_POLICY,
    }
    raw["event_id"] = compute_event_id(raw)
    return normalize_event(raw)


def normalize_event(raw: Mapping[str, Any]) -> NormalizedEvent:
    """Validate an envelope and recompute both identity digests at the entrance."""
    if not isinstance(raw, Mapping):
        raise EventValidationError("INVALID_ENVELOPE")
    unknown = set(raw) - ENVELOPE_KEYS
    if unknown:
        raise EventValidationError("UNKNOWN_ENVELOPE_FIELD", ", ".join(sorted(unknown)))
    missing = ENVELOPE_KEYS - set(raw)
    if missing:
        raise EventValidationError("MISSING_ENVELOPE_FIELD", ", ".join(sorted(missing)))
    if raw["schema_version"] != SCHEMA_VERSION:
        raise EventValidationError("INVALID_SCHEMA_VERSION", str(raw["schema_version"]))
    event_type = raw["type"]
    if event_type not in EVENT_TYPES:
        raise EventValidationError("UNKNOWN_EVENT_TYPE", str(event_type))
    for field in ("task_id", "project_id", "aggregate_id"):
        if not isinstance(raw[field], str) or not ID_RE.fullmatch(raw[field]):
            raise EventValidationError("INVALID_ID", f"{field}={raw[field]!r}")
    if raw["aggregate_id"] != raw["task_id"]:
        raise EventValidationError("INVALID_AGGREGATE", "aggregate_id must equal task_id")
    if not isinstance(raw["actor"], Mapping):
        raise EventValidationError("INVALID_ACTOR")
    if set(raw["actor"]) != ACTOR_KEYS:
        raise EventValidationError("INVALID_ACTOR", "actor must contain login and kind only")
    if not isinstance(raw["actor"]["login"], str) or not raw["actor"]["login"].strip():
        raise EventValidationError("INVALID_ACTOR", "actor.login required")
    if raw["actor"]["kind"] not in ("human", "bot", "service"):
        raise EventValidationError("INVALID_ACTOR", "actor.kind invalid")
    if not isinstance(raw["source"], Mapping):
        raise EventValidationError("INVALID_SOURCE")
    if set(raw["source"]) != SOURCE_KEYS:
        raise EventValidationError("INVALID_SOURCE", "source fields are closed")
    if raw["source"]["backend"] != "github" or not isinstance(raw["source"]["repo"], str):
        raise EventValidationError("INVALID_SOURCE", "GitHub backend required")
    if not isinstance(raw["source"]["object_id"], (str, int)):
        raise EventValidationError("INVALID_SOURCE", "object_id required")
    if not isinstance(raw["source"]["sequence"], int) or raw["source"]["sequence"] < 0:
        raise EventValidationError("INVALID_SOURCE", "sequence must be non-negative")
    sha = _validate_sha_or_null(raw["sha"], "sha")
    occurred_at = normalize_timestamp(raw["occurred_at"])
    payload = _validate_payload(event_type, raw["payload"])
    payload_digest = digest_payload(payload)
    if str(raw["payload_digest"]).lower() != payload_digest:
        raise EventValidationError("EVENT_ENVELOPE_TAMPERED", "payload_digest mismatch")
    if raw["replay_policy"] != REPLAY_POLICY:
        raise EventValidationError("INVALID_REPLAY_POLICY", str(raw["replay_policy"]))
    envelope = {
        "schema_version": raw["schema_version"],
        "event_id": str(raw["event_id"]).lower(),
        "type": event_type,
        "task_id": raw["task_id"],
        "project_id": raw["project_id"],
        "aggregate_id": raw["aggregate_id"],
        "actor": {
            "login": _nfc(raw["actor"]["login"].strip()),
            "kind": raw["actor"]["kind"],
        },
        "source": {
            "backend": "github",
            "repo": _nfc(raw["source"]["repo"]),
            "object": _nfc(str(raw["source"]["object"])),
            "object_id": raw["source"]["object_id"],
            "sequence": raw["source"]["sequence"],
        },
        "sha": sha,
        "occurred_at": occurred_at,
        "payload_digest": payload_digest,
        "payload": payload,
        "correlation_id": None if raw["correlation_id"] is None else _nfc(str(raw["correlation_id"])),
        "causation_id": None if raw["causation_id"] is None else str(raw["causation_id"]).lower(),
        "replay_policy": raw["replay_policy"],
    }
    expected = compute_event_id(envelope)
    if envelope["event_id"] != expected:
        raise EventValidationError("EVENT_ENVELOPE_TAMPERED", "event_id mismatch")
    return NormalizedEvent(**envelope)


def event_log_digest(events: Iterable[NormalizedEvent]) -> str:
    return sha256_hex(canonical_json_bytes([e.to_dict() for e in events]))


def _duplicate_record(event: NormalizedEvent, reason: str) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "type": event.type,
        "reason": reason,
    }


def deduplicate_events(events: Iterable[NormalizedEvent]) -> tuple[list[NormalizedEvent], list[dict[str, Any]], list[str]]:
    """Remove exact duplicates and duplicate facts, keeping the lexicographically first fact."""
    by_id: dict[str, NormalizedEvent] = {}
    ignored: list[dict[str, Any]] = []
    reasons: list[str] = []
    for event in events:
        previous = by_id.get(event.event_id)
        if previous is None:
            by_id[event.event_id] = event
            continue
        if previous.payload_digest != event.payload_digest:
            reasons.append("EVENT_ENVELOPE_TAMPERED")
            ignored.append(_duplicate_record(event, "EVENT_ENVELOPE_TAMPERED"))
            continue
        ignored.append(_duplicate_record(event, "DUPLICATE"))

    groups: dict[tuple[Any, ...], list[NormalizedEvent]] = {}
    for event in by_id.values():
        groups.setdefault(event.fact_key, []).append(event)
    kept: list[NormalizedEvent] = []
    for candidates in groups.values():
        candidates.sort(key=lambda item: item.order_key)
        kept.append(candidates[0])
        for duplicate in candidates[1:]:
            ignored.append(_duplicate_record(duplicate, "DUPLICATE_FACT"))
    kept.sort(key=lambda item: item.order_key)
    ignored.sort(key=lambda item: (item["reason"], item["event_id"]))
    return kept, ignored, reasons


def causal_sort(events: Iterable[NormalizedEvent]) -> tuple[list[NormalizedEvent], list[str]]:
    """Stable topological sort; malformed graphs fail closed with a reason code."""
    items = list(events)
    by_id = {event.event_id: event for event in items}
    reasons: list[str] = []
    children: dict[str, list[str]] = {event.event_id: [] for event in items}
    indegree: dict[str, int] = {event.event_id: 0 for event in items}
    for event in items:
        pred = event.causation_id
        if pred is None:
            continue
        pred = pred.lower()
        if pred not in by_id:
            reasons.append("ORPHAN_MISSING_PREDECESSOR")
            continue
        children[pred].append(event.event_id)
        indegree[event.event_id] += 1
    if any(len(out) > 1 for out in children.values()):
        reasons.append("CAUSAL_GRAPH_CONFLICT")

    ready = sorted(
        (event for event in items if indegree[event.event_id] == 0),
        key=lambda item: item.order_key,
    )
    ordered: list[NormalizedEvent] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for child_id in sorted(children[current.event_id]):
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                ready.append(by_id[child_id])
        ready.sort(key=lambda item: item.order_key)
    if len(ordered) != len(items):
        reasons.append("CAUSAL_GRAPH_CONFLICT")
        # Deterministic fallback for audit visibility; the projection is blocked.
        ordered = sorted(items, key=lambda item: item.order_key)
    return ordered, sorted(set(reasons))


def prepare_events(batch: EventBatch) -> PreparedEvents:
    normalized: list[NormalizedEvent] = []
    reasons: list[str] = []
    for raw in batch.events:
        try:
            normalized.append(raw if isinstance(raw, NormalizedEvent) else normalize_event(raw))
        except EventValidationError as exc:
            reasons.append(exc.reason)
    kept, ignored, duplicate_reasons = deduplicate_events(normalized)
    reasons.extend(duplicate_reasons)
    ordered, graph_reasons = causal_sort(kept)
    reasons.extend(graph_reasons)
    return PreparedEvents(
        ordered=tuple(ordered),
        ignored=tuple(ignored),
        reasons=tuple(sorted(set(reasons))),
    )
