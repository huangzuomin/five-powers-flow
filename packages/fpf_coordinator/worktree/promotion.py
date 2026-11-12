# -*- coding: utf-8 -*-
"""Consume the G4 projection: turn a merge event into ``RECLAIMABLE``.

This module reads the ledger the reducer already writes.  It never calls the
reducer, never touches the network and never guesses: a merge fact that cannot
be tied to *this* marker and a *fresh* projection leaves the worktree exactly
where it was.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import marker as marker_mod

PROMOTING = frozenset({"PR_MERGED", "MAP_PR_MERGED"})
LEDGER_SCHEMA = "fpf.state-ledger/v1"
DEFAULT_FRESHNESS_HOURS = 24

LEDGER_OK = "LEDGER_OK"
LEDGER_MISSING = "LEDGER_MISSING"
LEDGER_STALE = "LEDGER_STALE"


@dataclass(frozen=True)
class Promotion:
    state: str | None
    reason: str
    ledger_status: str
    merge_fact: dict | None = None
    event_id: str | None = None

    @property
    def promotes(self) -> bool:
        return self.state is not None


def _parse(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def ledger_status(ledger: dict | None, *, now: datetime | None = None,
                  freshness_hours: int = DEFAULT_FRESHNESS_HOURS) -> str:
    if not isinstance(ledger, dict):
        return LEDGER_MISSING
    if ledger.get("schema_version") != LEDGER_SCHEMA:
        return LEDGER_STALE
    source = ledger.get("source")
    if not isinstance(source, dict) or source.get("complete") is not True:
        return LEDGER_STALE
    if not source.get("as_of_event_id"):
        return LEDGER_STALE
    as_of = source.get("as_of_occurred_at")
    if not as_of:
        return LEDGER_STALE
    try:
        moment = _parse(as_of)
    except ValueError:
        return LEDGER_STALE
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age = (reference - moment).total_seconds() / 3600.0
    return LEDGER_STALE if age > freshness_hours else LEDGER_OK


def _events(ledger: dict, task_id: str) -> list[dict]:
    out = []
    for task in ledger.get("tasks") or []:
        if not isinstance(task, dict) or task.get("task_id") != task_id:
            continue
        for event in task.get("events") or []:
            if isinstance(event, dict):
                out.append(event)
    return out


def _matches(marker: dict, event: dict, head_sha: str | None) -> bool:
    if event.get("type") not in PROMOTING:
        return False
    if event.get("task_id") != marker["task_id"]:
        return False
    payload = event.get("payload") or {}
    recorded = marker.get("merge_fact")
    if recorded and recorded.get("pr_number") is not None:
        return payload.get("pr_number") == recorded["pr_number"]
    head = head_sha or marker.get("detached_head_sha")
    if head is None:
        return False
    return event.get("sha") == head or payload.get("head_sha") == head


def evaluate(marker: dict, ledger: dict | None, *, head_sha: str | None = None,
             now: datetime | None = None,
             freshness_hours: int = DEFAULT_FRESHNESS_HOURS) -> Promotion:
    status = ledger_status(ledger, now=now, freshness_hours=freshness_hours)
    if status == LEDGER_MISSING:
        return Promotion(None, LEDGER_MISSING, status)
    if status == LEDGER_STALE:
        return Promotion(None, LEDGER_STALE, status)
    if marker["state"] in (marker_mod.RECLAIMABLE, marker_mod.RECLAIMED):
        return Promotion(None, "ALREADY_PROMOTED", status)

    matches = [event for event in _events(ledger, marker["task_id"])
               if _matches(marker, event, head_sha)]
    if not matches:
        return Promotion(None, "NO_MATCHING_MERGE_EVENT", status)
    matches.sort(key=lambda event: (event.get("occurred_at") or "",
                                    event.get("event_id") or ""))
    event = matches[-1]
    payload = event.get("payload") or {}
    merge_commit = payload.get("merge_commit_sha")
    if not merge_commit:
        return Promotion(None, "MERGE_FACT_INCOMPLETE", status)
    fact = {
        "pr_number": payload.get("pr_number"),
        "merge_commit_sha": merge_commit,
        "merged_at": payload.get("merged_at") or event.get("occurred_at"),
        "event_id": event.get("event_id"),
    }
    return Promotion(marker_mod.RECLAIMABLE, "PR_MERGED", status,
                     merge_fact=fact, event_id=event.get("event_id"))


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
