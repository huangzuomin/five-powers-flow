# -*- coding: utf-8 -*-
"""Independent projection reconciliation for the G4 state ledger."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from .events import canonical_json_bytes, sha256_hex
from .reducer import Reduction, projection_tasks_digest


def _parse_time(value: str) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return moment.astimezone(timezone.utc)


def _first_divergence(expected: Any, observed: Any, path: str = "$") -> str | None:
    if type(expected) is not type(observed):
        return f"{path}: type {type(expected).__name__} != {type(observed).__name__}"
    if isinstance(expected, dict):
        expected_keys = sorted(expected)
        observed_keys = sorted(observed)
        if expected_keys != observed_keys:
            return f"{path}: keys {expected_keys!r} != {observed_keys!r}"
        for key in expected_keys:
            found = _first_divergence(expected[key], observed[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(expected, list):
        if len(expected) != len(observed):
            return f"{path}: length {len(expected)} != {len(observed)}"
        for index, (left, right) in enumerate(zip(expected, observed)):
            found = _first_divergence(left, right, f"{path}[{index}]")
            if found:
                return found
        return None
    if expected != observed:
        return f"{path}: {expected!r} != {observed!r}"
    return None


def _ledger_tasks(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    tasks = ledger.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(item, dict) for item in tasks):
        raise ValueError("state ledger must contain a tasks list")
    return [dict(item) for item in tasks]


def _audit_is_fresh(
    audit: Mapping[str, Any] | None,
    *,
    now: datetime,
    max_age_seconds: int,
) -> tuple[bool, str]:
    if not audit or not audit.get("exists"):
        return False, "AUDIT_MISSING"
    if str(audit.get("latest_conclusion") or "").lower() != "success":
        return False, "AUDIT_LATEST_RUN_NOT_SUCCESS"
    if not audit.get("latest_head_sha") or not audit.get("main_tip_sha"):
        return False, "AUDIT_HEAD_SHA_MISSING"
    if str(audit.get("latest_head_sha")).lower() != str(audit.get("main_tip_sha")).lower():
        return False, "AUDIT_HEAD_NOT_MAIN"
    if audit.get("latest_head_on_main") is False:
        return False, "AUDIT_HEAD_NOT_ON_MAIN"
    completed = str(audit.get("latest_completed_at") or "")
    if not completed:
        return False, "AUDIT_COMPLETION_TIME_MISSING"
    try:
        age = (now - _parse_time(completed)).total_seconds()
    except ValueError:
        return False, "AUDIT_COMPLETION_TIME_INVALID"
    if age < -300 or age > max_age_seconds:
        return False, "LEDGER_STALE"
    return True, ""


def audit_is_fresh(
    audit: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    max_age_seconds: int = 1800,
) -> tuple[bool, str]:
    """Consumer-facing freshness verdict for a committed ledger's audit."""
    return _audit_is_fresh(
        audit,
        now=now or datetime.now(timezone.utc),
        max_age_seconds=max_age_seconds,
    )


def _audit_blocks_replay(audit: Mapping[str, Any] | None) -> tuple[bool, str]:
    """Gate the auditor on its own prior output, without self-deadlock.

    The audit check is produced by the reconciliation run itself, so a missing
    check on a fresh ``main`` tip (or a check that has aged out) must not block
    the run that would create it: the run recomputes the projection from
    authoritative GitHub facts and its verdict becomes the new audit.  Only a
    recorded failure on the current tip is sticky, because a failed audit is
    evidence about this exact ledger and must never be masked by re-running.
    """
    if not audit or not audit.get("exists"):
        return False, ""
    if str(audit.get("latest_conclusion") or "").lower() != "success":
        return True, "AUDIT_LATEST_RUN_NOT_SUCCESS"
    if not audit.get("latest_head_sha") or not audit.get("main_tip_sha"):
        return True, "AUDIT_HEAD_SHA_MISSING"
    if str(audit.get("latest_head_sha")).lower() != str(audit.get("main_tip_sha")).lower():
        return True, "AUDIT_HEAD_NOT_MAIN"
    if audit.get("latest_head_on_main") is False:
        return True, "AUDIT_HEAD_NOT_ON_MAIN"
    return False, ""


def reconcile_projection(
    reduction: Reduction,
    ledger: Mapping[str, Any],
    *,
    audit: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    max_audit_age_seconds: int = 1800,
    require_fresh_audit: bool = False,
) -> dict[str, Any]:
    """Compare a reducer result with the committed ledger.

    The ledger is never trusted for its own watermark.  The caller supplies the
    latest authoritative audit check-run facts.

    ``require_fresh_audit=False`` (the auditor's own mode) recomputes and
    publishes the audit, so it only refuses when a failure is already recorded
    against this tip.  ``require_fresh_audit=True`` is the consumer mode: the
    caller is about to trust the ledger without replaying it, so the audit must
    exist, be recent, and belong to the current ``main`` tip.  Neither mode ever
    falls back to a historical success.
    """
    current = now or datetime.now(timezone.utc)
    expected_tasks = [copy.deepcopy(dict(reduction.projection))]
    expected_tasks[0]["aggregate_version"] = 1 + len(reduction.event_ids)
    expected_digest = projection_tasks_digest(expected_tasks)
    try:
        observed_tasks = _ledger_tasks(ledger)
    except ValueError as exc:
        return {
            "status": "BLOCKED",
            "reason": "LEDGER_SCHEMA_INVALID",
            "detail": str(exc),
            "expected_projection_digest": expected_digest,
            "observed_projection_digest": None,
            "first_divergence": "$.tasks",
            "event_log_digest": reduction.event_log_digest,
        }

    source = ledger.get("source")
    if not isinstance(source, Mapping):
        return {
            "status": "BLOCKED",
            "reason": "LEDGER_SCHEMA_INVALID",
            "detail": "source is required",
            "expected_projection_digest": expected_digest,
            "observed_projection_digest": None,
            "first_divergence": "$.source",
            "event_log_digest": reduction.event_log_digest,
        }

    if require_fresh_audit:
        fresh, audit_reason = _audit_is_fresh(
            audit, now=current, max_age_seconds=max_audit_age_seconds,
        )
        audit_blocked = not fresh
    else:
        audit_blocked, audit_reason = _audit_blocks_replay(audit)
    if audit_blocked:
        return {
            "status": "BLOCKED",
            "reason": audit_reason,
            "expected_projection_digest": expected_digest,
            "observed_projection_digest": projection_tasks_digest(observed_tasks),
            "first_divergence": "$.source",
            "event_log_digest": reduction.event_log_digest,
        }

    if list(source.get("event_ids") or []) != list(reduction.event_ids):
        return {
            "status": "BLOCKED",
            "reason": "BLOCKED_RECONCILIATION",
            "detail": "ledger event watermark differs from the complete remote event set",
            "expected_projection_digest": expected_digest,
            "observed_projection_digest": projection_tasks_digest(observed_tasks),
            "first_divergence": "$.source.event_ids",
            "event_log_digest": reduction.event_log_digest,
        }
    if int(source.get("event_count") or 0) != len(reduction.event_ids):
        return {
            "status": "BLOCKED",
            "reason": "BLOCKED_RECONCILIATION",
            "detail": "ledger event_count differs from the reducer event set",
            "expected_projection_digest": expected_digest,
            "observed_projection_digest": projection_tasks_digest(observed_tasks),
            "first_divergence": "$.source.event_count",
            "event_log_digest": reduction.event_log_digest,
        }
    if str(source.get("event_log_digest") or "") != reduction.event_log_digest:
        return {
            "status": "BLOCKED",
            "reason": "BLOCKED_RECONCILIATION",
            "detail": "event log digest differs from the complete remote event set",
            "expected_projection_digest": expected_digest,
            "observed_projection_digest": projection_tasks_digest(observed_tasks),
            "first_divergence": "$.source.event_log_digest",
            "event_log_digest": reduction.event_log_digest,
        }
    if source.get("complete") is not True:
        return {
            "status": "BLOCKED",
            "reason": "EVENT_SET_INCOMPLETE",
            "expected_projection_digest": expected_digest,
            "observed_projection_digest": projection_tasks_digest(observed_tasks),
            "first_divergence": "$.source.complete",
            "event_log_digest": reduction.event_log_digest,
        }

    observed_digest = projection_tasks_digest(observed_tasks)
    divergence = _first_divergence(expected_tasks, observed_tasks, path="$.tasks")
    if divergence or observed_digest != expected_digest:
        return {
            "status": "BLOCKED",
            "reason": "BLOCKED_RECONCILIATION",
            "detail": "projection bytes differ from an independent replay",
            "expected_projection_digest": expected_digest,
            "observed_projection_digest": observed_digest,
            "first_divergence": divergence or "$",
            "event_log_digest": reduction.event_log_digest,
        }

    return {
        "status": "PASS",
        "reason": "RECONCILED",
        "expected_projection_digest": expected_digest,
        "observed_projection_digest": observed_digest,
        "first_divergence": None,
        "event_log_digest": reduction.event_log_digest,
    }


def canonical_ledger(ledger: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(dict(ledger))


def ledger_digest(ledger: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_ledger(ledger))


def write_report(path: Path | str, report: Mapping[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
