# -*- coding: utf-8 -*-
"""GitHub adapter for G4.  This is the only module that reads remote events."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Iterable, Mapping
from urllib.parse import quote
from urllib.request import Request, urlopen

import yaml

from packages.fpf_coordinator.coordinator import extract_yaml_block

from .events import (
    EventBatch,
    EventValidationError,
    NormalizedEvent,
    build_event,
    digest_payload,
    normalize_timestamp,
)


API_ROOT = "https://api.github.com"


class GitHubSourceError(RuntimeError):
    pass


def _request(
    repo: str,
    endpoint: str,
    token: str,
    *,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
) -> Any:
    if not token:
        raise GitHubSourceError("GitHub token is required")
    url = endpoint if endpoint.startswith("https://") else f"{API_ROOT}/repos/{repo}/{endpoint.lstrip('/')}"
    body = None
    if payload is not None:
        body = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fpf-g4-state-projector/1",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=45) as response:
            raw = response.read()
    except Exception as exc:
        raise GitHubSourceError(f"GitHub API failed: {method} {url}: {exc}") from exc
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GitHubSourceError(f"GitHub API returned non-JSON for {url}") from exc


def _pages(repo: str, endpoint: str, token: str,
           items_key: str | None = None) -> list[dict]:
    """Page a GitHub collection, unwrapping ``{"<items_key>": [...]}`` envelopes.

    Most REST collections answer with a bare array, but the Actions runs endpoint
    answers with ``{total_count, workflow_runs}``.  Treating the envelope as the
    page itself would silently produce zero events, or raise here.
    """
    separator = "&" if "?" in endpoint else "?"
    result: list[dict] = []
    for page in range(1, 101):
        data = _request(repo, f"{endpoint}{separator}per_page=100&page={page}", token)
        if items_key is not None:
            if not isinstance(data, dict) or not isinstance(data.get(items_key), list):
                raise GitHubSourceError(
                    f"Expected a '{items_key}' list from {endpoint}")
            data = data[items_key]
        if not isinstance(data, list):
            raise GitHubSourceError(f"Expected a list from {endpoint}")
        result.extend(item for item in data if isinstance(item, dict))
        if len(data) < 100:
            return result
    raise GitHubSourceError(f"Pagination exceeded safe bound for {endpoint}")


def _actor(user: Mapping[str, Any] | None) -> dict[str, str]:
    value = dict(user or {})
    login = str(value.get("login") or "unknown")
    kind = "bot" if str(value.get("type") or "").lower() == "bot" or login.endswith("[bot]") else "human"
    return {"login": login, "kind": kind}


def _card(body: str, kind: str) -> dict[str, Any] | None:
    text = extract_yaml_block(body or "", kind)
    if not text:
        return None
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise GitHubSourceError(f"Invalid {kind} card: {exc}") from exc
    if not isinstance(value, dict) or value.get("kind") != kind:
        raise GitHubSourceError(f"Invalid {kind} card")
    return value


def _time(value: Any, fallback: str) -> str:
    return str(value or fallback)


def _grant_payload(
    delivery: Mapping[str, Any],
    head_sha: str,
    base_sha: str,
    pr_number: int,
    task_id: str,
) -> tuple[dict[str, Any] | None, str]:
    """Build an authorization payload from declared facts only.

    A card may state a calendar expiry, or it may bind the grant to the exact
    commit under test.  It may not leave the question open: a missing, null,
    empty or unparseable basis yields no grant at all, and the caller marks the
    event set incomplete.  Nothing here ever invents a date.
    """
    raw_expiry = delivery.get("scope_expires_at")
    binding = str(delivery.get("scope_binding") or "").strip().lower()
    payload: dict[str, Any] = {
        "grant_id": str(delivery.get("scope_grant_id") or f"gr-{pr_number}-{base_sha[:12]}"),
        "scope": str(delivery.get("scope") or task_id),
        "baseline_sha": base_sha,
    }
    allowed_paths = delivery.get("changed_files") or []
    if not isinstance(allowed_paths, list):
        raise GitHubSourceError("changed_files must be a list")
    payload["allowed_paths"] = allowed_paths

    if raw_expiry is not None and str(raw_expiry).strip() != "":
        try:
            payload["expires_at"] = normalize_timestamp(raw_expiry)
        except EventValidationError:
            return None, "AUTHORIZATION_CONTRACT_INVALID"
        payload["expiry_binding"] = "absolute"
        return payload, ""
    if binding in ("tested_code_sha", "head_sha"):
        payload["expires_at"] = None
        payload["expiry_binding"] = "tested_code_sha"
        payload["bound_sha"] = head_sha
        return payload, ""
    return None, "AUTHORIZATION_CONTRACT_MISSING"


def _event(
    events: list[NormalizedEvent],
    *,
    type: str,
    task_id: str,
    project_id: str,
    actor: Mapping[str, Any],
    source_object: str,
    object_id: Any,
    sequence: int,
    occurred_at: Any,
    payload: Mapping[str, Any],
    repo: str,
    sha: str | None = None,
    causation_id: str | None = None,
) -> NormalizedEvent:
    event = build_event(
        type=type,
        task_id=task_id,
        project_id=project_id,
        actor=actor,
        source={
            "backend": "github",
            "repo": repo,
            "object": source_object,
            "object_id": object_id,
            "sequence": sequence,
        },
        occurred_at=occurred_at,
        payload=payload,
        sha=sha,
        correlation_id=f"{repo}#{object_id}",
        causation_id=causation_id,
    )
    events.append(event)
    return event


def fetch_pr_bundle(repo: str, pr_number: int, token: str) -> dict[str, Any]:
    pr = _request(repo, f"pulls/{int(pr_number)}", token)
    if not isinstance(pr, dict):
        raise GitHubSourceError("Pull request response was not an object")
    head_sha = str((pr.get("head") or {}).get("sha") or "").lower()
    if not re.fullmatch(r"[a-f0-9]{40}", head_sha):
        raise GitHubSourceError("Pull request head SHA is missing or invalid")
    reviews = _pages(repo, f"pulls/{int(pr_number)}/reviews", token)
    check_runs: list[dict] = []
    checks = _request(repo, f"commits/{head_sha}/check-runs?per_page=100", token)
    if isinstance(checks, dict) and isinstance(checks.get("check_runs"), list):
        check_runs = [item for item in checks["check_runs"] if isinstance(item, dict)]
    workflows = _pages(repo, f"actions/runs?head_sha={head_sha}", token,
                       items_key="workflow_runs")
    return {
        "pr": pr,
        "reviews": reviews,
        "check_runs": check_runs,
        "workflow_runs": workflows,
    }


def find_pr_for_task(repo: str, task_id: str, token: str) -> int:
    query = quote(f"repo:{repo} is:pr {task_id}")
    data = _request(
        repo,
        f"https://api.github.com/search/issues?q={query}&per_page=20",
        token,
    )
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise GitHubSourceError("GitHub search response was not an item list")
    candidates = [
        item for item in items
        if isinstance(item, dict) and item.get("pull_request") and task_id in str(item.get("body") or "")
    ]
    if not candidates:
        raise GitHubSourceError(f"No pull request found for task {task_id}")
    candidates.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return int(candidates[0]["number"])


def build_events_from_pr(
    repo: str,
    pr_number: int,
    task_id: str,
    project_id: str,
    token: str,
) -> EventBatch:
    """Normalize authenticated GitHub facts into the closed Task Event stream."""
    bundle = fetch_pr_bundle(repo, pr_number, token)
    pr = bundle["pr"]
    head_sha = str((pr.get("head") or {}).get("sha") or "").lower()
    base_sha = str((pr.get("base") or {}).get("sha") or "").lower()
    created_at = _time(pr.get("created_at"), "1970-01-01T00:00:00Z")
    merged_at = pr.get("merged_at")
    body = str(pr.get("body") or "")
    author = _actor(pr.get("user"))
    events: list[NormalizedEvent] = []
    sequence = 0
    complete = True
    refusals: list[str] = []
    causation: str | None = None

    causation = _event(
        events,
        type="TASK_OPENED",
        task_id=task_id,
        project_id=project_id,
        actor=author,
        source_object="pull_request",
        object_id=pr_number,
        sequence=sequence,
        occurred_at=created_at,
        payload={
            "task_id": task_id,
            "project_id": project_id,
            "baseline_sha": base_sha,
            "max_attempts": 3,
            "created_at": created_at,
            "record_url": str(pr.get("html_url") or f"https://github.com/{repo}/pull/{pr_number}"),
        },
        repo=repo,
        sha=base_sha,
    ).event_id
    sequence += 1

    policy = _card(body, "POLICY_CHANGE")
    dev = _card(body, "DEV_HANDOFF")
    delivery = policy or dev
    if delivery and str(delivery.get("task_id") or "") == task_id:
        causation = _event(
            events,
            type="WORK_ORDER_OPENED",
            task_id=task_id,
            project_id=project_id,
            actor=author,
            source_object="pull_request",
            object_id=pr_number,
            sequence=sequence,
            occurred_at=created_at,
            payload={
                "work_order_id": task_id,
                "task_id": task_id,
                "authorization_ref": str(delivery.get("authorization_ref") or ""),
                "authorized_by": str(delivery.get("authorized_by") or ""),
            },
            repo=repo,
            sha=head_sha,
            causation_id=causation,
        ).event_id
        sequence += 1

        grant_id = str(delivery.get("scope_grant_id") or f"gr-{pr_number}-{base_sha[:12]}")
        allowed_paths = delivery.get("changed_files") or []
        if not isinstance(allowed_paths, list):
            raise GitHubSourceError("changed_files must be a list")
        grant_payload, grant_refusal = _grant_payload(delivery, head_sha, base_sha, pr_number, task_id)
        if grant_payload is None:
            refusals.append(grant_refusal)
            complete = False
        else:
            causation = _event(
                events,
                type="SCOPE_GRANTED",
                task_id=task_id,
                project_id=project_id,
                actor=author,
                source_object="pull_request",
                object_id=pr_number,
                sequence=sequence,
                occurred_at=created_at,
                payload=grant_payload,
                repo=repo,
                sha=head_sha,
                causation_id=causation,
            ).event_id
            sequence += 1

        causation = _event(
            events,
            type="POLICY_CHANGE_DELIVERY_RECEIVED" if policy else "DEV_HANDOFF_RECEIVED",
            task_id=task_id,
            project_id=project_id,
            actor=author,
            source_object="pull_request",
            object_id=pr_number,
            sequence=sequence,
            occurred_at=created_at,
            payload={
                "tested_code_sha": head_sha,
                "baseline_sha": base_sha,
                "grant_id": grant_id,
                "author": author["login"],
                "checks": [],
                "delivery_kind": "POLICY_CHANGE" if policy else "DEV_HANDOFF",
                "changed_files": allowed_paths,
            },
            repo=repo,
            sha=head_sha,
            causation_id=causation,
        ).event_id
        sequence += 1

    for review in bundle["reviews"]:
        qa = _card(str(review.get("body") or ""), "QA_RESULT")
        if not qa or str(qa.get("task_id") or "") != task_id:
            continue
        review_actor = _actor(review.get("user"))
        submitted = _time(review.get("submitted_at"), created_at)
        payload = {
            "verdict": str(qa.get("verdict") or ""),
            "tested_sha": str(qa.get("tested_sha") or "").lower(),
            "task_id": task_id,
            "author": str(qa.get("author") or review_actor["login"]),
            "checks": qa.get("checks") if isinstance(qa.get("checks"), list) else [],
            "evidence_manifest_sha256": str(qa.get("evidence_manifest_sha256") or ""),
            "qa_run_id": int(qa.get("qa_run_id") or 0),
            "qa_artifact_id": int(qa.get("qa_artifact_id") or 0),
            "artifact_digest": str(qa.get("artifact_digest") or ""),
            "profile": str(qa.get("profile") or ""),
        }
        causation = _event(
            events,
            type="QA_RESULT_RECEIVED",
            task_id=task_id,
            project_id=project_id,
            actor=review_actor,
            source_object="review",
            object_id=review.get("id"),
            sequence=sequence,
            occurred_at=submitted,
            payload=payload,
            repo=repo,
            sha=head_sha,
            causation_id=causation,
        ).event_id
        sequence += 1
        if (str(review.get("state") or "").upper() == "APPROVED"
                and str(review.get("commit_id") or "").lower() == head_sha
                and payload["artifact_digest"]):
            causation = _event(
                events,
                type="QA_AUTHENTICATED",
                task_id=task_id,
                project_id=project_id,
                actor=review_actor,
                source_object="review",
                object_id=review.get("id"),
                sequence=sequence,
                occurred_at=submitted,
                payload={
                    "review_id": str(review.get("id")),
                    "review_commit_id": head_sha,
                    "qa_result_digest": digest_payload(qa),
                    "artifact_digest": payload["artifact_digest"],
                    "runner_sha": str(qa.get("runner_sha") or ""),
                    "qa_contract_sha": str(qa.get("qa_contract_sha") or ""),
                },
                repo=repo,
                sha=head_sha,
                causation_id=causation,
            ).event_id
            sequence += 1

    for check in bundle["check_runs"]:
        completed_at = _time(check.get("completed_at") or check.get("started_at"), created_at)
        causation = _event(
            events,
            type="CHECK_RUN_COMPLETED",
            task_id=task_id,
            project_id=project_id,
            actor=author,
            source_object="check_run",
            object_id=check.get("id"),
            sequence=sequence,
            occurred_at=completed_at,
            payload={
                "check_name": str(check.get("name") or ""),
                "conclusion": str(check.get("conclusion") or ""),
                "head_sha": str(check.get("head_sha") or "").lower(),
                "app_id": str((check.get("app") or {}).get("id") or ""),
            },
            repo=repo,
            sha=head_sha,
            causation_id=causation,
        ).event_id
        sequence += 1

    for run in bundle["workflow_runs"]:
        path = str(run.get("path") or "")
        if not path.endswith("fpf-independent-qa.yml"):
            continue
        completed_at = _time(run.get("updated_at") or run.get("created_at"), created_at)
        causation = _event(
            events,
            type="WORKFLOW_RUN_COMPLETED",
            task_id=task_id,
            project_id=project_id,
            actor=_actor(run.get("actor")),
            source_object="workflow_run",
            object_id=run.get("id"),
            sequence=sequence,
            occurred_at=completed_at,
            payload={
                "workflow_path": path,
                "run_id": int(run.get("id") or 0),
                "head_sha": str(run.get("head_sha") or "").lower(),
                "conclusion": str(run.get("conclusion") or ""),
                "actor": str((run.get("actor") or {}).get("login") or ""),
                "triggering_actor": str((run.get("triggering_actor") or {}).get("login") or ""),
            },
            repo=repo,
            sha=head_sha,
            causation_id=causation,
        ).event_id
        sequence += 1

    if merged_at:
        causation = _event(
            events,
            type="PR_MERGED",
            task_id=task_id,
            project_id=project_id,
            actor=author,
            source_object="pull_request",
            object_id=pr_number,
            sequence=sequence,
            occurred_at=merged_at,
            payload={
                "pr_number": pr_number,
                "merge_commit_sha": str(pr.get("merge_commit_sha") or ""),
                "merged_by": str((pr.get("merged_by") or {}).get("login") or ""),
            },
            repo=repo,
            sha=str(pr.get("merge_commit_sha") or head_sha),
            causation_id=causation,
        ).event_id
        sequence += 1

    return EventBatch(
        events=tuple(events),
        cursor=f"github:{repo}:pull:{pr_number}:{head_sha}",
        complete=complete and not refusals,
        refusals=tuple(refusals),
    )


def main_tip(repo: str, token: str) -> str:
    data = _request(repo, "git/ref/heads/main", token)
    if not isinstance(data, dict):
        raise GitHubSourceError("main ref response was not an object")
    sha = str((data.get("object") or {}).get("sha") or "").lower()
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise GitHubSourceError("main ref SHA is invalid")
    return sha


def latest_audit_status(repo: str, token: str, check_name: str = "fpf-state-ledger-audit") -> dict[str, Any]:
    tip = main_tip(repo, token)
    data = _request(
        repo,
        f"commits/{tip}/check-runs?check_name={quote(check_name)}&per_page=100",
        token,
    )
    runs = data.get("check_runs") if isinstance(data, dict) else None
    if not isinstance(runs, list) or not runs:
        return {
            "exists": False,
            "main_tip_sha": tip,
            "latest_conclusion": None,
            "latest_completed_at": None,
            "latest_head_sha": None,
            "latest_head_on_main": True,
        }
    ordered = sorted(
        (item for item in runs if isinstance(item, dict)),
        key=lambda item: str(item.get("completed_at") or item.get("started_at") or item.get("created_at") or ""),
        reverse=True,
    )
    latest = ordered[0]
    return {
        "exists": True,
        "main_tip_sha": tip,
        "latest_conclusion": latest.get("conclusion"),
        "latest_completed_at": latest.get("completed_at"),
        "latest_head_sha": str(latest.get("head_sha") or "").lower(),
        "latest_head_on_main": str(latest.get("head_sha") or "").lower() == tip,
        "latest_run_id": latest.get("id"),
    }


def create_check_run(
    repo: str,
    token: str,
    *,
    head_sha: str,
    conclusion: str,
    summary: str,
    check_name: str = "fpf-state-ledger-audit",
) -> dict[str, Any]:
    data = _request(
        repo,
        "check-runs",
        token,
        method="POST",
        payload={
            "name": check_name,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": "FPF state ledger audit",
                "summary": summary[:65000],
            },
        },
    )
    if not isinstance(data, dict):
        raise GitHubSourceError("Check-run creation response was not an object")
    return data
