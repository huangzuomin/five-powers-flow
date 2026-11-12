# -*- coding: utf-8 -*-
"""``.fpf-worktree.json``: content-addressed identity for one worktree.

The marker is the only place that says what a worktree is *for*.  Because it
is written by the local tool and readable by anyone, it has to defend itself:
every field is required, unknown fields are rejected (no self-declared
authority), and the whole payload is covered by a digest so a hand edit is
detectable instead of silently trusted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = "fpf.worktree-marker/v1"
MARKER_NAME = ".fpf-worktree.json"
TOOL_VERSION = "fpf-worktree/v1"

ACTIVE = "ACTIVE"
RECLAIMABLE = "RECLAIMABLE"
HOLD = "HOLD"
RECLAIMED = "RECLAIMED"
STATES = (ACTIVE, RECLAIMABLE, HOLD, RECLAIMED)

TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,119}$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

FIELDS = (
    "schema_version", "task_id", "project_id", "work_order_id", "branch",
    "detached_head_sha", "base_sha", "owner", "created_at", "ttl_days",
    "state", "state_history", "merge_fact", "reclaimable_at", "created_by",
    "bootstrap", "digest",
)


class MarkerError(RuntimeError):
    pass


class MissingField(MarkerError):
    """A required field is absent; the message names every missing field."""


class UnknownField(MarkerError):
    """``additionalProperties: false`` -- unknown keys are refused."""


class InvalidMarker(MarkerError):
    """A field is present but violates its declared constraint."""


class MarkerTampered(MarkerError):
    """The digest does not cover the current payload."""


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def compute_digest(payload: dict) -> str:
    body = {key: value for key, value in payload.items() if key != "digest"}
    return hashlib.sha256(canonical(body)).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require(value, field: str) -> None:
    if value is None:
        raise MissingField(f"missing required field: {field}")


def _check_sha40(value, field: str, *, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, str) or not HEX40_RE.fullmatch(value):
        raise InvalidMarker(f"{field} must be a 40-hex sha")


def resolve_station(stations_path, station: str) -> bool:
    """A station is resolvable when the registry declares it as an ``id``.

    H2 deliberately does not keep a second identity table: the only authority
    on "which station is this" is the G2 registry.
    """
    path = Path(stations_path)
    if not path.is_file():
        return False
    pattern = re.compile(rf"^\s*-\s*id:\s*{re.escape(station)}\s*$", re.MULTILINE)
    return bool(pattern.search(path.read_text(encoding="utf-8")))


def validate(marker: dict, *, stations_path=None) -> dict:
    """Return a normalised copy, or raise naming the exact defect."""
    if not isinstance(marker, dict):
        raise InvalidMarker("marker must be an object")
    unknown = sorted(set(marker) - set(FIELDS))
    if unknown:
        raise UnknownField("unknown field(s): " + ", ".join(unknown))
    required = [field for field in FIELDS if field not in ("digest", "bootstrap")]
    missing = [field for field in required if field not in marker]
    if missing:
        raise MissingField("missing required field(s): " + ", ".join(missing))

    if marker["schema_version"] != SCHEMA_VERSION:
        raise InvalidMarker(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(marker["task_id"], str) or not TASK_ID_RE.fullmatch(marker["task_id"]):
        raise InvalidMarker("task_id violates ^[A-Za-z0-9][A-Za-z0-9_.:-]{2,119}$")
    if not isinstance(marker["project_id"], str) or not marker["project_id"]:
        raise InvalidMarker("project_id must be a non-empty string")
    if marker.get("bootstrap") not in (None, True, False):
        raise InvalidMarker("bootstrap must be a boolean")
    if marker["work_order_id"] is None:
        if marker.get("bootstrap") is not True:
            raise InvalidMarker("work_order_id null requires bootstrap: true")
    elif not isinstance(marker["work_order_id"], str) or not marker["work_order_id"]:
        raise InvalidMarker("work_order_id must be a string or null")

    branch = marker["branch"]
    detached = marker["detached_head_sha"]
    if branch is None and detached is None:
        raise InvalidMarker("one of branch / detached_head_sha is required")
    if branch is not None and detached is not None:
        raise InvalidMarker("branch and detached_head_sha are mutually exclusive")
    if branch is not None:
        if not isinstance(branch, str) or not branch.startswith("refs/heads/"):
            raise InvalidMarker("branch must be a refs/heads/... reference")
    if detached is not None:
        _check_sha40(detached, "detached_head_sha")
    _check_sha40(marker["base_sha"], "base_sha")

    owner = marker["owner"]
    if not isinstance(owner, dict) or set(owner) != {"login", "station"}:
        raise InvalidMarker("owner must be exactly {login, station}")
    if not isinstance(owner["login"], str) or not owner["login"].strip():
        raise InvalidMarker("owner.login required")
    if not isinstance(owner["station"], str) or not owner["station"].strip():
        raise InvalidMarker("owner.station required")
    if stations_path is not None and not resolve_station(stations_path, owner["station"]):
        raise InvalidMarker(f"owner.station {owner['station']!r} is not registered")

    if not isinstance(marker["created_at"], str) or not RFC3339_RE.fullmatch(marker["created_at"]):
        raise InvalidMarker("created_at must be RFC3339 UTC (YYYY-MM-DDTHH:MM:SSZ)")
    ttl = marker["ttl_days"]
    if not isinstance(ttl, int) or isinstance(ttl, bool) or not 1 <= ttl <= 30:
        raise InvalidMarker("ttl_days must be an integer in 1..30")

    if marker["state"] not in STATES:
        raise InvalidMarker("state must be one of " + ", ".join(STATES))
    history = marker["state_history"]
    if not isinstance(history, list) or not history:
        raise InvalidMarker("state_history must be a non-empty array")
    if history[0].get("state") != ACTIVE:
        raise InvalidMarker("state_history[0].state must be ACTIVE")
    for entry in history:
        if not isinstance(entry, dict):
            raise InvalidMarker("state_history entries must be objects")
        if entry.get("state") not in STATES:
            raise InvalidMarker("state_history entry has an unknown state")
        if not isinstance(entry.get("at"), str) or not RFC3339_RE.fullmatch(entry["at"]):
            raise InvalidMarker("state_history entry needs an RFC3339 at")
        if not entry.get("reason"):
            raise InvalidMarker("state_history entry needs a reason")
        extra = set(entry) - {"state", "at", "reason", "event_id"}
        if extra:
            raise UnknownField("unknown state_history field(s): " + ", ".join(sorted(extra)))

    merge_fact = marker["merge_fact"]
    if merge_fact is not None:
        if not isinstance(merge_fact, dict):
            raise InvalidMarker("merge_fact must be an object or null")
        want = {"pr_number", "merge_commit_sha", "merged_at", "event_id"}
        if set(merge_fact) != want:
            raise InvalidMarker("merge_fact must be exactly " + ", ".join(sorted(want)))
        _check_sha40(merge_fact["merge_commit_sha"], "merge_fact.merge_commit_sha")

    reclaimable_at = marker["reclaimable_at"]
    if reclaimable_at is not None:
        if not isinstance(reclaimable_at, str) or not RFC3339_RE.fullmatch(reclaimable_at):
            raise InvalidMarker("reclaimable_at must be RFC3339 UTC or null")
        if marker["state"] not in (RECLAIMABLE, RECLAIMED):
            raise InvalidMarker("reclaimable_at is only meaningful in RECLAIMABLE/RECLAIMED")

    if not isinstance(marker["created_by"], str) or not marker["created_by"]:
        raise InvalidMarker("created_by required")

    digest = marker.get("digest")
    if digest is not None:
        if not isinstance(digest, str) or not HEX64_RE.fullmatch(digest):
            raise InvalidMarker("digest must be 64 lowercase hex")
        if digest != compute_digest(marker):
            raise MarkerTampered("marker digest does not match its payload")
    return dict(marker)


def create(*, task_id: str, base_sha: str, owner: dict, branch: str | None = None,
           detached_head_sha: str | None = None, work_order_id: str | None = None,
           project_id: str = "FPF", ttl_days: int = 14,
           created_at: str | None = None, stations_path=None,
           bootstrap: bool = False) -> dict:
    marker = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "project_id": project_id,
        "work_order_id": work_order_id,
        "branch": branch,
        "detached_head_sha": detached_head_sha,
        "base_sha": base_sha,
        "owner": dict(owner),
        "created_at": created_at or now_utc(),
        "ttl_days": ttl_days,
        "state": ACTIVE,
        "state_history": [
            {"state": ACTIVE, "at": created_at or now_utc(), "reason": "create"},
        ],
        "merge_fact": None,
        "reclaimable_at": None,
        "created_by": TOOL_VERSION,
        "bootstrap": bool(bootstrap),
    }
    if not bootstrap:
        marker.pop("bootstrap")
    marker["digest"] = compute_digest(marker)
    return validate(marker, stations_path=stations_path)


def append_history(marker: dict, state: str, reason: str, *,
                   event_id: str | None = None, at: str | None = None) -> dict:
    updated = {key: value for key, value in marker.items() if key != "digest"}
    entry = {"state": state, "at": at or now_utc(), "reason": reason}
    if event_id:
        entry["event_id"] = event_id
    updated["state_history"] = list(updated["state_history"]) + [entry]
    updated["state"] = state
    updated["digest"] = compute_digest(updated)
    return updated


def promote(marker: dict, merge_fact: dict, *, at: str | None = None) -> dict:
    updated = {key: value for key, value in marker.items() if key != "digest"}
    updated["merge_fact"] = dict(merge_fact)
    updated["reclaimable_at"] = at or now_utc()
    updated["state"] = RECLAIMABLE
    updated["state_history"] = list(updated["state_history"]) + [{
        "state": RECLAIMABLE,
        "at": updated["reclaimable_at"],
        "reason": "PR_MERGED",
        "event_id": merge_fact["event_id"],
    }]
    updated["digest"] = compute_digest(updated)
    return updated


def read(path) -> dict:
    target = Path(path)
    if target.is_dir():
        target = target / MARKER_NAME
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarkerTampered("marker is not valid JSON") from exc
    return validate(payload)


def write(path, marker: dict) -> Path:
    target = Path(path)
    if target.is_dir():
        target = target / MARKER_NAME
    validated = validate(marker)
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(json.dumps(validated, sort_keys=True, indent=2,
                                ensure_ascii=False).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    return target


def is_expired(marker: dict, *, now: str | None = None) -> bool:
    created = datetime.strptime(marker["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    moment = datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ") if now else \
        datetime.now(timezone.utc).replace(tzinfo=None)
    return moment > created + timedelta(days=int(marker["ttl_days"]))
