# -*- coding: utf-8 -*-
"""Atomic, cross-run consumption claims for ledger recoveries.

Check runs carry no uniqueness constraint, and a SQLite journal only
arbitrates within one runner.  Git refs do: the server accepts exactly one
creator per name.  A claim is therefore a tag ref keyed by the authorization,
pointing at an annotated tag whose message is the canonical claim record.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest

from .events import canonical_json, canonical_json_bytes, sha256_hex
from .authorization import (
    AUTH_DIR,
    AuthorizationVerifier,
    GitHubFactsClient,
    load_authorization,
)

CLAIM_SCHEMA = "fpf.ledger-claim/v1"
CLAIM_REF_PREFIX = "refs/tags/fpf-ledger-claim/"
PROBE_REF_PREFIX = "refs/tags/fpf-claim-probe/"
API_ROOT = "https://api.github.com"


class ClaimError(RuntimeError):
    pass


class ClaimConflict(ClaimError):
    """Another writer already holds this authorization."""


class ClaimFailed(ClaimError):
    """The claim could not be recorded; nothing was consumed."""


def consumption_id(
    authorization_id: str,
    tip_sha: str,
    failure_run_id: int,
    projection_digest: str,
) -> str:
    return sha256_hex(canonical_json_bytes({
        "authorization_id": str(authorization_id).lower(),
        "tip_sha": str(tip_sha).lower(),
        "failure_run_id": int(failure_run_id),
        "projection_digest": str(projection_digest).lower(),
    }))


def claim_document(
    *,
    authorization_id: str,
    tip_sha: str,
    failure_run_id: int,
    projection_digest: str,
    claimant_run_id: str | None = None,
    claimed_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": CLAIM_SCHEMA,
        "authorization_id": str(authorization_id).lower(),
        "tip_sha": str(tip_sha).lower(),
        "failure_run_id": int(failure_run_id),
        "projection_digest": str(projection_digest).lower(),
        "consumption_id": consumption_id(
            authorization_id, tip_sha, failure_run_id, projection_digest,
        ),
        "claimant_run_id": str(claimant_run_id or ""),
        "claimed_at": str(claimed_at or ""),
    }


def claim_message(document: Mapping[str, Any]) -> str:
    return canonical_json(dict(document)) + "\n"


class ClaimStore(Protocol):
    def create(self, document: Mapping[str, Any]) -> None: ...

    def read(self, authorization_id: str) -> dict[str, Any] | None: ...


class InMemoryClaimStore:
    """Atomic store used by tests and by single-run probes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}

    def create(self, document: Mapping[str, Any]) -> None:
        key = str(document["authorization_id"]).lower()
        with self._lock:
            if key in self._items:
                raise ClaimConflict(f"authorization {key} is already consumed")
            self._items[key] = dict(document)

    def read(self, authorization_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._items.get(str(authorization_id).lower())
            return dict(value) if value is not None else None


def verify_claim(
    stored: Mapping[str, Any] | None,
    expected: Mapping[str, Any],
) -> tuple[bool, str]:
    if stored is None:
        return False, "CLAIM_REF_MISSING"
    for field in (
        "schema", "authorization_id", "tip_sha", "failure_run_id",
        "projection_digest", "consumption_id",
    ):
        if stored.get(field) != expected.get(field):
            return False, f"CLAIM_FIELD_MISMATCH:{field}"
    return True, ""


def verify_recovery_claim(
    *,
    verdict: Any,
    authorization: Any,
    tip_sha: str,
    failure_run_id: int,
    projection_digest: str,
    replay_digest: str,
    failure_facts: Mapping[str, Any],
) -> tuple[bool, str]:
    """Gate a claim on facts the job derived itself (D-03).

    The claim job must not write because a caller *said* an authorization,
    a failure and a projection exist.  It re-reads all four and only then
    creates the ref.
    """
    if not getattr(verdict, "ok", False):
        return False, str(getattr(verdict, "reason", "") or "AUTHORIZATION_UNVERIFIABLE")
    if getattr(authorization, "kind", "") != "LEDGER_RECOVERY":
        return False, "AUTHORIZATION_KIND_MISMATCH"
    expected_tip = str(getattr(authorization, "tip_sha", "") or "").lower()
    if expected_tip != str(tip_sha).lower():
        return False, "AUTHORIZATION_TIP_MISMATCH"
    expected_failure = int(getattr(authorization, "failure_check_run_id", 0) or 0)
    if expected_failure != int(failure_run_id):
        return False, "AUTHORIZATION_FAILURE_MISMATCH"
    if int(failure_facts.get("id") or 0) != int(failure_run_id):
        return False, "FAILURE_RUN_UNVERIFIED"
    if str(failure_facts.get("conclusion") or "").lower() != "failure":
        return False, "FAILURE_RUN_NOT_FAILED"
    if str(failure_facts.get("head_sha") or "").lower() != str(tip_sha).lower():
        return False, "FAILURE_RUN_HEAD_DRIFT"
    if str(projection_digest).lower() != str(replay_digest).lower():
        return False, "PROJECTION_DIGEST_MISMATCH"
    return True, ""


def git_blob_sha(path: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "hash-object", path],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = completed.stdout.strip().lower()
    return value or None


class GitHubRefClaimStore:
    """Tag-ref claim store backed by the GitHub API.

    Only HTTP 201 on ref creation counts as a won claim.  A tag object that was
    created before a failed ref creation is *not* a consumption: the ref is the
    reservation.
    """

    def __init__(
        self,
        *,
        repo: str,
        token: str,
        base_sha: str,
        timeout: int = 30,
    ) -> None:
        if not token:
            raise ClaimFailed("a token is required for ref claims")
        self._repo = repo
        self._token = token
        self._base_sha = base_sha
        self._timeout = timeout

    # -- plumbing ---------------------------------------------------------
    def _call(self, method: str, path: str, payload: dict | None = None) -> tuple[int, Any]:
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            API_ROOT + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "fpf-ledger-claim/1",
            },
        )
        try:
            with urlrequest.urlopen(req, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8") or "{}"
                return int(response.status), json.loads(raw)
        except urlerror.HTTPError as exc:
            raw = exc.read().decode("utf-8") or "{}"
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"message": raw}
            return int(exc.code), body

    # -- protocol ---------------------------------------------------------
    def create(self, document: Mapping[str, Any]) -> None:
        authorization_id = str(document["authorization_id"]).lower()
        tag_name = f"fpf-ledger-claim/{authorization_id}"
        status, tag = self._call(
            "POST",
            f"/repos/{self._repo}/git/tags",
            {
                "tag": tag_name,
                "message": claim_message(document),
                "object": self._base_sha,
                "type": "commit",
                "tagger": {
                    "name": "FPF Ledger Claim",
                    "email": "fpf-claim@users.noreply.github.com",
                    "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            },
        )
        if status != 201:
            raise ClaimFailed(f"tag object creation failed: HTTP {status} {tag}")
        tag_sha = str(tag.get("sha") or "")
        if not tag_sha:
            raise ClaimFailed("tag object response has no sha")

        status, body = self._call(
            "POST",
            f"/repos/{self._repo}/git/refs",
            {"ref": CLAIM_REF_PREFIX + authorization_id, "sha": tag_sha},
        )
        if status == 201:
            return
        if status in (409, 422):
            raise ClaimConflict(
                f"authorization {authorization_id} is already consumed (HTTP {status})"
            )
        raise ClaimFailed(f"ref creation failed: HTTP {status} {body}")

    def read(self, authorization_id: str) -> dict[str, Any] | None:
        status, ref = self._call(
            "GET", f"/repos/{self._repo}/git/ref/{CLAIM_REF_PREFIX}{authorization_id}",
        )
        if status == 404:
            return None
        if status != 200:
            raise ClaimFailed(f"ref read failed: HTTP {status} {ref}")
        obj = ref.get("object") or {}
        if str(obj.get("type")) != "tag":
            raise ClaimFailed("claim ref does not point at a tag object")
        tag_sha = str(obj.get("sha") or "")
        status, tag = self._call("GET", f"/repos/{self._repo}/git/tags/{tag_sha}")
        if status != 200:
            raise ClaimFailed(f"tag read failed: HTTP {status} {tag}")
        message = str(tag.get("message") or "")
        try:
            parsed = json.loads(message)
        except json.JSONDecodeError as exc:
            raise ClaimFailed("claim tag message is not JSON") from exc
        if not isinstance(parsed, dict):
            raise ClaimFailed("claim tag message is not an object")
        return parsed


@dataclass(frozen=True)
class ProbeResult:
    attempts: int
    successes: int
    statuses: tuple[int, ...]

    @property
    def atomic(self) -> bool:
        return self.successes == 1


def probe_atomicity(
    *,
    repo: str,
    token: str,
    base_sha: str,
    attempts: int = 2,
) -> ProbeResult:
    """Fire concurrent ref creations at the *same* name against real GitHub.

    This is the D-06 acceptance probe: the server must accept exactly one.
    Probe refs live in their own namespace and are removed afterwards; claim
    refs are never touched here.
    """
    if attempts < 2:
        raise ValueError("attempts must be at least 2")
    store = GitHubRefClaimStore(repo=repo, token=token, base_sha=base_sha)
    probe = f"fpf-claim-probe/{uuid.uuid4().hex}"
    tag_status, tag = store._call(
        "POST",
        f"/repos/{repo}/git/tags",
        {
            "tag": probe,
            "message": "fpf claim atomicity probe\n",
            "object": base_sha,
            "type": "commit",
            "tagger": {
                "name": "FPF Ledger Claim",
                "email": "fpf-claim@users.noreply.github.com",
                "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        },
    )
    if tag_status != 201:
        raise ClaimFailed(f"probe tag creation failed: HTTP {tag_status} {tag}")
    tag_sha = str(tag.get("sha") or "")
    statuses: list[int] = []
    lock = threading.Lock()

    def attempt() -> None:
        status, _ = store._call(
            "POST",
            f"/repos/{repo}/git/refs",
            {"ref": PROBE_REF_PREFIX + probe.split("/", 1)[1], "sha": tag_sha},
        )
        with lock:
            statuses.append(status)

    threads = [threading.Thread(target=attempt) for _ in range(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    # Probe cleanup only; claim refs are permanent by design.
    store._call("DELETE", f"/repos/{repo}/git/ref/{PROBE_REF_PREFIX}{probe.split('/', 1)[1]}")
    return ProbeResult(
        attempts=attempts,
        successes=sum(1 for status in statuses if status == 201),
        statuses=tuple(statuses),
    )


def _token_from_env() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fpf-ledger-claims")
    sub = parser.add_subparsers(dest="command", required=True)

    claim = sub.add_parser("claim")
    claim.add_argument("--repo", required=True)
    claim.add_argument("--authorization-id", required=True)
    claim.add_argument("--tip-sha", required=True)
    claim.add_argument("--failure-run-id", type=int, required=True)
    claim.add_argument("--projection-digest", required=True)
    claim.add_argument("--base-sha", required=True)
    claim.add_argument("--claimant-run-id", default=os.environ.get("GITHUB_RUN_ID", ""))

    read = sub.add_parser("read")
    read.add_argument("--repo", required=True)
    read.add_argument("--authorization-id", required=True)
    read.add_argument("--base-sha", required=True)

    probe = sub.add_parser("probe")
    probe.add_argument("--repo", required=True)
    probe.add_argument("--base-sha", required=True)
    probe.add_argument("--attempts", type=int, default=2)

    verified = sub.add_parser(
        "claim-verified",
        help="re-derive authorization, failure and projection facts, then claim",
    )
    verified.add_argument("--repo", required=True)
    verified.add_argument("--base-sha", required=True)
    verified.add_argument("--authorization-id", required=True)
    verified.add_argument("--tip-sha", required=True)
    verified.add_argument("--failure-run-id", type=int, required=True)
    verified.add_argument("--projection-digest", required=True)
    verified.add_argument("--task-id", required=True)
    verified.add_argument("--project-id", required=True)
    verified.add_argument("--pr-number", type=int, required=True)
    verified.add_argument("--claimant-run-id", default=os.environ.get("GITHUB_RUN_ID", ""))

    args = parser.parse_args(argv)
    token = _token_from_env()
    if not token:
        print(json.dumps({"status": "FAILED", "reason": "TOKEN_MISSING"}))
        return 2
    if args.command == "probe":
        result = probe_atomicity(
            repo=args.repo, token=token, base_sha=args.base_sha, attempts=args.attempts,
        )
        print(json.dumps({
            "attempts": result.attempts,
            "successes": result.successes,
            "statuses": list(result.statuses),
            "atomic": result.atomic,
        }))
        return 0 if result.atomic else 1
    store = GitHubRefClaimStore(repo=args.repo, token=token, base_sha=args.base_sha)
    if args.command == "read":
        print(json.dumps(store.read(args.authorization_id), ensure_ascii=False))
        return 0
    if args.command == "claim-verified":
        authorization = load_authorization(f"{AUTH_DIR}/{args.authorization_id}.yaml")
        if authorization.authorization_id != str(args.authorization_id).lower():
            print(json.dumps({"status": "BLOCKED", "reason": "AUTHORIZATION_ID_MISMATCH"}))
            return 1
        facts = GitHubFactsClient(repo=args.repo, token=token)
        verdict = AuthorizationVerifier(facts, args.repo).verify(
            authorization,
            local_blob_sha=git_blob_sha(authorization.path),
        )
        failure = facts.check_run(args.failure_run_id)
        from .poller import _reduce_from_github

        reduction, _ = _reduce_from_github(argparse.Namespace(
            repo=args.repo,
            task_id=args.task_id,
            project_id=args.project_id,
            pr_number=args.pr_number,
            token_env="GH_TOKEN",
        ))
        ok, reason = verify_recovery_claim(
            verdict=verdict,
            authorization=authorization,
            tip_sha=args.tip_sha,
            failure_run_id=args.failure_run_id,
            projection_digest=args.projection_digest,
            replay_digest=reduction.projection_digest,
            failure_facts=failure,
        )
        if not ok:
            print(json.dumps({
                "status": "BLOCKED",
                "reason": reason,
                "authorization_reason": getattr(verdict, "reason", ""),
            }))
            return 1
    document = claim_document(
        authorization_id=args.authorization_id,
        tip_sha=args.tip_sha,
        failure_run_id=args.failure_run_id,
        projection_digest=args.projection_digest,
        claimant_run_id=args.claimant_run_id,
        claimed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    try:
        store.create(document)
    except ClaimConflict as exc:
        print(json.dumps({"status": "BLOCKED", "reason": "AUTHORIZATION_ALREADY_CONSUMED",
                          "detail": str(exc)}))
        return 1
    except ClaimFailed as exc:
        print(json.dumps({"status": "BLOCKED", "reason": "CLAIM_FAILED", "detail": str(exc)}))
        return 1
    stored = store.read(args.authorization_id)
    ok, reason = verify_claim(stored, document)
    print(json.dumps({
        "status": "CLAIMED" if ok else "BLOCKED",
        "reason": reason or "CLAIM_VERIFIED",
        "consumption_id": document["consumption_id"],
    }))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

