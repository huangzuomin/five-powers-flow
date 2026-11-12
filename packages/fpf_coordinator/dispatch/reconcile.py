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


def reconcile_projection(
    reduction: Reduction,
    ledger: Mapping[str, Any],
    *,
    audit: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    max_audit_age_seconds: int = 1800,
    allow_genesis_bootstrap: bool = True,
) -> dict[str, Any]:
    """Compare a reducer result with the committed ledger.

    The ledger is never trusted for its own watermark.  The caller supplies the
    latest authoritative audit check-run facts; a missing/failed/stale audit is
    a failure, never a historical-success fallback.
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

    genesis = not observed_tasks and not source.get("event_ids")
    audit_ok, audit_reason = _audit_is_fresh(
        audit, now=current, max_age_seconds=max_audit_age_seconds,
    )
    if not audit_ok and not (allow_genesis_bootstrap and genesis):
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
