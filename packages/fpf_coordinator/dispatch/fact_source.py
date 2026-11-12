"""Independent fact-source verification for the trusted publish job.

The publish gate must prove two separate things:

1. the candidate projection equals what the *trusted* reducer computes from the
   candidate event log (``reducer`` + ``compare``), and
2. the candidate event log equals what the trusted collector observes on GitHub
   *now* (this module).

Two consecutive, independently paged collections that agree are reported as a
**stable observation**.  That is deliberately weaker than an atomic snapshot:
GitHub offers no cross-endpoint transaction, so we never claim one (R11-C11).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

from .github_source import GitHubSourceError, _request, build_events_from_pr

PAGE_SIZE = 100
MAX_PAGES = 100
RETRY_ROUNDS = 3

EVENT_SOURCE_UNAVAILABLE = "EVENT_SOURCE_UNAVAILABLE"
EVENT_PAGINATION_INCOMPLETE = "EVENT_PAGINATION_INCOMPLETE"
EVENT_SOURCE_SNAPSHOT_DRIFT = "EVENT_SOURCE_SNAPSHOT_DRIFT"
EVENT_ID_CONFLICT = "EVENT_ID_CONFLICT"
EVENT_COUNT_MISMATCH = "EVENT_COUNT_MISMATCH"
EVENT_ID_MISMATCH = "EVENT_ID_MISMATCH"
EVENT_FIELD_MISMATCH = "EVENT_FIELD_MISMATCH"
EVENT_ATTRIBUTION_MISMATCH = "EVENT_ATTRIBUTION_MISMATCH"
PR_SNAPSHOT_DRIFT = "PR_SNAPSHOT_DRIFT"


class FactSourceError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _page(
    repo: str,
    endpoint: str,
    token: str,
    page: int,
    items_key: str | None,
) -> list[dict[str, Any]]:
    separator = "&" if "?" in endpoint else "?"
    try:
        data = _request(repo, f"{endpoint}{separator}per_page={PAGE_SIZE}&page={page}", token)
    except GitHubSourceError as exc:
        raise FactSourceError(EVENT_SOURCE_UNAVAILABLE, f"{endpoint} page {page}: {exc}") from exc
    if items_key is not None:
        if not isinstance(data, dict) or not isinstance(data.get(items_key), list):
            raise FactSourceError(EVENT_SOURCE_UNAVAILABLE, f"{endpoint} envelope")
        data = data[items_key]
    if not isinstance(data, list):
        raise FactSourceError(EVENT_SOURCE_UNAVAILABLE, f"{endpoint} not a list")
    return [item for item in data if isinstance(item, dict)]


def collect_endpoint(
    repo: str,
    endpoint: str,
    token: str,
    *,
    pass_no: int,
    source_object: str,
    items_key: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect one endpoint from page 1, recording per-page forensics (R11-C01/C02)."""
    items: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        batch = _page(repo, endpoint, token, page, items_key)
        records.append({
            "pass": pass_no,
            "endpoint": endpoint,
            "page": page,
            "count": len(batch),
            "first_event_id": "",
            "last_event_id": "",
            "page_sha256": sha256_hex(canonical_bytes(batch)),
            "collected_at": _now(),
            "_object_ids": [f"{source_object}:{item.get('id')}" for item in batch],
        })
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            return items, records
    raise FactSourceError(
        EVENT_PAGINATION_INCOMPLETE, f"{endpoint} still full at page {MAX_PAGES}",
    )


def _pr_snapshot(repo: str, pr_number: int, token: str) -> dict[str, Any]:
    try:
        pr = _request(repo, f"pulls/{int(pr_number)}", token)
    except GitHubSourceError as exc:
        raise FactSourceError(EVENT_SOURCE_UNAVAILABLE, f"pull {pr_number}: {exc}") from exc
    if not isinstance(pr, dict):
        raise FactSourceError(EVENT_SOURCE_UNAVAILABLE, "pull payload")
    snapshot = {
        "head_sha": str((pr.get("head") or {}).get("sha") or "").lower(),
        "base_sha": str((pr.get("base") or {}).get("sha") or "").lower(),
        "state": str(pr.get("state") or ""),
        "merged": bool(pr.get("merged")),
        "updated_at": str(pr.get("updated_at") or ""),
    }
    snapshot["digest"] = sha256_hex(canonical_bytes(snapshot))
    return snapshot


def _canonical_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        (dict(event) for event in events),
        key=lambda item: (
            str(item.get("occurred_at") or ""),
            int((item.get("source") or {}).get("sequence") or 0),
            str(item.get("event_id") or ""),
        ),
    )
    return ordered


def _event_id_conflicts(events: Sequence[Mapping[str, Any]]) -> list[str]:
    """R11-C05: same event_id with a different payload_digest is a hard failure."""
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for event in events:
        event_id = str(event.get("event_id") or "")
        digest = str(event.get("payload_digest") or "")
        prior = seen.get(event_id)
        if prior is None:
            seen[event_id] = digest
        elif prior != digest:
            conflicts.append(f"{event_id}:{prior[:12]}!={digest[:12]}")
    return sorted(conflicts)


def _attribute_pages(
    events: Sequence[Mapping[str, Any]], records: list[dict[str, Any]],
) -> None:
    """Replace raw object keys with the event ids each page actually produced."""
    by_object: dict[str, list[str]] = {}
    for event in events:
        source = event.get("source") or {}
        key = f"{source.get('object')}:{source.get('object_id')}"
        by_object.setdefault(key, []).append(str(event.get("event_id") or ""))
    attributed: set[str] = set()
    for record in records:
        produced = sorted({
            event_id
            for key in record.pop("_object_ids", [])
            for event_id in by_object.get(key, [])
        })
        attributed.update(produced)
        record["first_event_id"] = produced[0] if produced else ""
        record["last_event_id"] = produced[-1] if produced else ""
    unattributed = sorted({
        str(event.get("event_id") or "") for event in events
        if str((event.get("source") or {}).get("object") or "") not in {"pull_request"}
    } - attributed)
    if unattributed:
        raise FactSourceError(
            EVENT_ATTRIBUTION_MISMATCH, ",".join(unattributed[:5]),
        )


@dataclass(frozen=True)
class PassSnapshot:
    pass_no: int
    before: dict[str, Any]
    after: dict[str, Any]
    pages: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...]

    @property
    def event_ids(self) -> list[str]:
        return sorted(str(event["event_id"]) for event in self.events)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.pass_no,
            "before": self.before,
            "after": self.after,
            "pages": list(self.pages),
            "events": list(self.events),
            "event_ids": self.event_ids,
            "event_count": len(self.events),
            "event_log_digest": sha256_hex(canonical_bytes(list(self.events))),
        }


def collect_pass(
    repo: str,
    pr_number: int,
    task_id: str,
    project_id: str,
    token: str,
    pass_no: int,
) -> PassSnapshot:
    before = _pr_snapshot(repo, pr_number, token)
    if not before["head_sha"]:
        raise FactSourceError(EVENT_SOURCE_UNAVAILABLE, "pull head sha")
    pages: list[dict[str, Any]] = []
    for endpoint, source_object, items_key in (
        (f"pulls/{int(pr_number)}/reviews", "review", None),
        (f"issues/{int(pr_number)}/comments", "issue_comment", None),
        (f"actions/runs?head_sha={before['head_sha']}", "workflow_run", "workflow_runs"),
        (f"commits/{before['head_sha']}/check-runs", "check_run", "check_runs"),
    ):
        _, records = collect_endpoint(
            repo, endpoint, token, pass_no=pass_no,
            source_object=source_object, items_key=items_key,
        )
        pages.extend(records)
    try:
        batch = build_events_from_pr(repo, int(pr_number), task_id, project_id, token)
    except GitHubSourceError as exc:
        raise FactSourceError(EVENT_SOURCE_UNAVAILABLE, str(exc)) from exc
    events = _canonical_events([event.to_dict() for event in batch.ordered_events])
    conflicts = _event_id_conflicts(events)
    if conflicts:
        raise FactSourceError(EVENT_ID_CONFLICT, ",".join(conflicts[:5]))
    _attribute_pages(events, pages)
    after = _pr_snapshot(repo, pr_number, token)
    if before["head_sha"] != after["head_sha"] or before["base_sha"] != after["base_sha"]:
        raise FactSourceError(PR_SNAPSHOT_DRIFT, "pr shas changed during collection")
    return PassSnapshot(
        pass_no=pass_no, before=before, after=after,
        pages=tuple(pages), events=tuple(events),
    )


def _page_diff(left: PassSnapshot, right: PassSnapshot) -> str:
    if len(left.pages) != len(right.pages):
        return f"page_count {len(left.pages)}!={len(right.pages)}"
    for a, b in zip(left.pages, right.pages):
        for field in ("endpoint", "page", "count", "page_sha256", "first_event_id", "last_event_id"):
            if a.get(field) != b.get(field):
                return f"{a.get('endpoint')}#{a.get('page')}:{field}"
    return "content"


def _comparable_pages(snapshot: PassSnapshot) -> list[dict[str, Any]]:
    """Strip the fields that legitimately differ between two passes."""
    return [
        {key: record.get(key) for key in (
            "endpoint", "page", "count", "page_sha256", "first_event_id", "last_event_id",
        )}
        for record in snapshot.pages
    ]


def compare_passes(left: PassSnapshot, right: PassSnapshot) -> None:
    """R11-C04: pages, counts, first/last ids, id sets and canonical content must agree."""
    if len(left.events) != len(right.events):
        raise FactSourceError(
            EVENT_SOURCE_SNAPSHOT_DRIFT, f"event_count {len(left.events)}!={len(right.events)}",
        )
    if left.event_ids != right.event_ids:
        raise FactSourceError(EVENT_SOURCE_SNAPSHOT_DRIFT, "event_id set")
    if canonical_bytes(list(left.events)) != canonical_bytes(list(right.events)):
        raise FactSourceError(EVENT_SOURCE_SNAPSHOT_DRIFT, _page_diff(left, right))
    if canonical_bytes(_comparable_pages(left)) != canonical_bytes(_comparable_pages(right)):
        raise FactSourceError(EVENT_SOURCE_SNAPSHOT_DRIFT, _page_diff(left, right))


def stable_observation(
    repo: str,
    pr_number: int,
    task_id: str,
    project_id: str,
    token: str,
    *,
    rounds: int = RETRY_ROUNDS,
) -> tuple[PassSnapshot, list[dict[str, Any]]]:
    """Return a stable observation, retrying the whole double collection (R11-C07)."""
    attempts: list[dict[str, Any]] = []
    for round_no in range(1, rounds + 1):
        first = collect_pass(repo, pr_number, task_id, project_id, token, 1)
        second = collect_pass(repo, pr_number, task_id, project_id, token, 2)
        try:
            compare_passes(first, second)
        except FactSourceError as exc:
            attempts.append({
                "round": round_no,
                "status": "DRIFT",
                "reason": exc.detail or exc.code,
                "pass1_digest": sha256_hex(canonical_bytes(first.as_dict()["events"])),
                "pass2_digest": sha256_hex(canonical_bytes(second.as_dict()["events"])),
            })
            continue
        attempts.append({"round": round_no, "status": "STABLE"})
        return first, attempts
    raise FactSourceError(
        EVENT_SOURCE_SNAPSHOT_DRIFT, f"{rounds} rounds without a stable observation",
    )


def compare_event_log(
    trusted: Sequence[Mapping[str, Any]], candidate_log: Sequence[Mapping[str, Any]],
) -> None:
    """Compare the candidate event log against the trusted observation."""
    if len(trusted) != len(candidate_log):
        raise FactSourceError(
            EVENT_COUNT_MISMATCH, f"{len(trusted)}!={len(candidate_log)}",
        )
    trusted_ids = {str(event.get("event_id") or "") for event in trusted}
    candidate_ids = {str(event.get("event_id") or "") for event in candidate_log}
    if trusted_ids != candidate_ids:
        missing = sorted(trusted_ids - candidate_ids)[:3]
        extra = sorted(candidate_ids - trusted_ids)[:3]
        raise FactSourceError(EVENT_ID_MISMATCH, f"missing={missing} extra={extra}")
    index = {str(event.get("event_id") or ""): event for event in trusted}
    for event in candidate_log:
        event_id = str(event.get("event_id") or "")
        if canonical_bytes(index[event_id]) != canonical_bytes(dict(event)):
            raise FactSourceError(EVENT_FIELD_MISMATCH, event_id)
