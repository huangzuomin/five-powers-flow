# -*- coding: utf-8 -*-
"""Ledger authorizations anchored in merged, dual-approved pull requests.

An authorization is not a self-declared string.  It is a small file added by a
GATE_PR that was approved by a ``qa-evidence`` station and a distinct
``ruling-carrier`` station; the verifier re-reads those GitHub facts at
consumption time.  Nothing here trusts the file's own claims about identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol
import base64
import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest

import yaml

from .events import canonical_json_bytes, sha256_hex

API_ROOT = "https://api.github.com"

SCHEMA = "fpf.ledger-authorization/v2"
KINDS = ("LEDGER_INIT", "LEDGER_RECOVERY")
AUTH_DIR = ".fpf/ledger-authorizations"
REVOCATION_DIR = ".fpf/revocations"

# Identity must come from GitHub, never from the document itself.
FORBIDDEN_FIELDS = ("authorized_by", "authorized_at", "evidence")

ALLOWED_FIELDS = frozenset({
    "schema", "kind", "authorization_id", "repo", "task_id", "scope",
    "one_time", "reason",
    # LEDGER_INIT
    "baseline_sha", "baseline_ledger_blob_sha", "expected_history_commits",
    # LEDGER_RECOVERY
    "tip_sha", "failure_check_run_id", "init_id",
})

REQUIRED_FIELDS = frozenset({
    "schema", "kind", "authorization_id", "repo", "task_id", "scope", "one_time",
})

HEX40 = r"^[0-9a-f]{40}$"
HEX64 = r"^[0-9a-f]{64}$"


class AuthorizationError(ValueError):
    """A malformed or forbidden authorization document."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def _require_hex(value: Any, field: str, length: int) -> str:
    import re

    text = str(value or "").lower()
    pattern = HEX40 if length == 40 else HEX64
    if not re.fullmatch(pattern, text):
        raise AuthorizationError("AUTHORIZATION_FIELD_INVALID", f"{field} must be {length} hex")
    return text


def canonical_body(body: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in body.items() if k != "authorization_id"}


def authorization_id_for(body: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(canonical_body(body)))


@dataclass(frozen=True)
class Authorization:
    path: str
    body: dict[str, Any]
    authorization_id: str

    @property
    def kind(self) -> str:
        return str(self.body["kind"])

    @property
    def repo(self) -> str:
        return str(self.body["repo"])

    @property
    def task_id(self) -> str:
        return str(self.body["task_id"])

    @property
    def baseline_sha(self) -> str | None:
        value = self.body.get("baseline_sha")
        return str(value).lower() if value else None

    @property
    def baseline_blob_sha(self) -> str | None:
        value = self.body.get("baseline_ledger_blob_sha")
        return str(value).lower() if value else None

    @property
    def expected_history_commits(self) -> int | None:
        value = self.body.get("expected_history_commits")
        return int(value) if value is not None else None

    @property
    def tip_sha(self) -> str | None:
        value = self.body.get("tip_sha")
        return str(value).lower() if value else None

    @property
    def failure_check_run_id(self) -> int | None:
        value = self.body.get("failure_check_run_id")
        return int(value) if value is not None else None

    @property
    def init_id(self) -> str | None:
        value = self.body.get("init_id")
        return str(value).lower() if value else None


def validate_body(body: Mapping[str, Any], *, filename_id: str | None = None) -> Authorization:
    if not isinstance(body, Mapping):
        raise AuthorizationError("AUTHORIZATION_SCHEMA_INVALID", "body must be a mapping")
    forbidden = [f for f in FORBIDDEN_FIELDS if f in body]
    if forbidden:
        raise AuthorizationError(
            "AUTHORIZATION_FIELD_FORBIDDEN",
            "identity and evidence are derived from GitHub, not declared: "
            + ", ".join(sorted(forbidden)),
        )
    unknown = sorted(set(body) - ALLOWED_FIELDS)
    if unknown:
        raise AuthorizationError("AUTHORIZATION_FIELD_UNKNOWN", ", ".join(unknown))
    missing = sorted(REQUIRED_FIELDS - set(body))
    if missing:
        raise AuthorizationError("AUTHORIZATION_FIELD_MISSING", ", ".join(missing))
    if str(body.get("schema")) != SCHEMA:
        raise AuthorizationError("AUTHORIZATION_SCHEMA_INVALID", f"schema must be {SCHEMA}")
    kind = str(body.get("kind"))
    if kind not in KINDS:
        raise AuthorizationError("AUTHORIZATION_KIND_INVALID", kind)
    if body.get("one_time") is not True:
        raise AuthorizationError("AUTHORIZATION_NOT_ONE_TIME", "one_time must be true")
    repo = str(body.get("repo") or "")
    if repo.count("/") != 1:
        raise AuthorizationError("AUTHORIZATION_REPO_INVALID", repo)
    if not str(body.get("task_id") or "").strip():
        raise AuthorizationError("AUTHORIZATION_TASK_MISSING", "task_id is required")
    if not str(body.get("scope") or "").strip():
        raise AuthorizationError("AUTHORIZATION_SCOPE_MISSING", "scope is required")

    computed = authorization_id_for(body)
    declared = _require_hex(body.get("authorization_id"), "authorization_id", 64)
    if computed != declared:
        raise AuthorizationError(
            "AUTHORIZATION_ID_MISMATCH",
            f"declared {declared} != recomputed {computed}",
        )
    if filename_id is not None and filename_id.lower() != declared:
        raise AuthorizationError(
            "AUTHORIZATION_FILENAME_MISMATCH",
            f"file name {filename_id} != authorization_id {declared}",
        )

    if kind == "LEDGER_INIT":
        _require_hex(body.get("baseline_sha"), "baseline_sha", 40)
        blob = body.get("baseline_ledger_blob_sha")
        if blob is not None:
            _require_hex(blob, "baseline_ledger_blob_sha", 40)
        if "expected_history_commits" not in body:
            raise AuthorizationError("AUTHORIZATION_FIELD_MISSING", "expected_history_commits")
        commits = body.get("expected_history_commits")
        if not isinstance(commits, int) or commits not in (0, 1):
            raise AuthorizationError(
                "AUTHORIZATION_HISTORY_HINT_INVALID",
                "expected_history_commits must be 0 or 1",
            )
        if commits == 0 and blob is not None:
            raise AuthorizationError(
                "AUTHORIZATION_HISTORY_HINT_INVALID",
                "a file that never existed cannot have a blob",
            )
    else:
        _require_hex(body.get("tip_sha"), "tip_sha", 40)
        _require_hex(body.get("init_id"), "init_id", 64)
        run_id = body.get("failure_check_run_id")
        if not isinstance(run_id, int) or run_id <= 0:
            raise AuthorizationError(
                "AUTHORIZATION_FAILURE_BINDING_INVALID",
                "failure_check_run_id must be a positive integer",
            )

    return Authorization(
        path=f"{AUTH_DIR}/{declared}.yaml",
        body={str(k): v for k, v in body.items()},
        authorization_id=declared,
    )


def load_authorization(path: Path | str) -> Authorization:
    file_path = Path(path)
    try:
        body = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuthorizationError("AUTHORIZATION_NOT_FOUND", str(file_path)) from exc
    except yaml.YAMLError as exc:
        raise AuthorizationError("AUTHORIZATION_YAML_INVALID", str(exc)) from exc
    return validate_body(body, filename_id=file_path.stem)


# ---------------------------------------------------------------------------
# Verification against GitHub facts
# ---------------------------------------------------------------------------


class GitHubFacts(Protocol):
    """The slice of the GitHub API the verifier needs (injectable for tests)."""

    def commits_for_path(self, path: str) -> list[dict[str, Any]]: ...

    def pulls_for_commit(self, sha: str) -> list[dict[str, Any]]: ...

    def reviews_for_pull(self, number: int) -> list[dict[str, Any]]: ...

    def pr_files(self, number: int) -> list[str]: ...

    def content_blob_sha(self, path: str, ref: str) -> str | None: ...

    def stations(self, ref: str) -> dict[str, str]: ...


@dataclass(frozen=True)
class Verdict:
    status: str
    reason: str
    evidence: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == "VERIFIED"


def normalize_login(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text


class AuthorizationVerifier:
    """Re-derive authorization identity from merged GitHub facts."""

    def __init__(self, facts: GitHubFacts, repo: str) -> None:
        self._facts = facts
        self._repo = repo

    def verify(
        self,
        authorization: Authorization,
        *,
        local_blob_sha: str | None,
        revoked: bool = False,
    ) -> Verdict:
        try:
            return self._verify(
                authorization, local_blob_sha=local_blob_sha, revoked=revoked,
            )
        except Exception as exc:  # API down, malformed payload, anything
            return Verdict(
                "BLOCKED",
                "AUTHORIZATION_UNVERIFIABLE",
                {"error": f"{type(exc).__name__}: {exc}"},
            )

    def _verify(
        self,
        authorization: Authorization,
        *,
        local_blob_sha: str | None,
        revoked: bool,
    ) -> Verdict:
        if revoked:
            return Verdict("BLOCKED", "AUTHORIZATION_REVOKED", {"path": authorization.path})
        if authorization.repo.lower() != self._repo.lower():
            return Verdict(
                "BLOCKED", "AUTHORIZATION_REPO_MISMATCH",
                {"authorization_repo": authorization.repo, "repo": self._repo},
            )

        commits = self._facts.commits_for_path(authorization.path)
        if not commits:
            return Verdict("BLOCKED", "AUTHORIZATION_NOT_MERGED", {"path": authorization.path})
        if len(commits) > 1:
            return Verdict(
                "BLOCKED", "AUTHORIZATION_HISTORY_INVALID",
                {"path": authorization.path, "commits": len(commits)},
            )
        commit_sha = str(commits[0].get("sha") or "").lower()
        pulls = self._facts.pulls_for_commit(commit_sha)
        if len(pulls) != 1:
            return Verdict(
                "BLOCKED", "AUTHORIZATION_NOT_MERGED",
                {"commit": commit_sha, "pulls": len(pulls)},
            )
        pull = pulls[0]
        if pull.get("merged") is not True:
            return Verdict("BLOCKED", "AUTHORIZATION_NOT_MERGED", {"pr": pull.get("number")})
        base_ref = str((pull.get("base") or {}).get("ref") or "")
        if base_ref != "main":
            return Verdict(
                "BLOCKED", "AUTHORIZATION_BASE_NOT_MAIN", {"base": base_ref},
            )

        merge_sha = str(pull.get("merge_commit_sha") or "").lower()
        pr_head = str((pull.get("head") or {}).get("sha") or "").lower()
        remote_blob = self._facts.content_blob_sha(authorization.path, merge_sha)
        if not remote_blob:
            return Verdict(
                "BLOCKED", "AUTHORIZATION_CONTENT_DRIFT",
                {"path": authorization.path, "ref": merge_sha},
            )
        if local_blob_sha and str(local_blob_sha).lower() != str(remote_blob).lower():
            return Verdict(
                "BLOCKED", "AUTHORIZATION_CONTENT_DRIFT",
                {"local": local_blob_sha, "remote": remote_blob},
            )

        allowed_prefixes = (AUTH_DIR + "/", REVOCATION_DIR + "/")
        stray = [
            path for path in self._facts.pr_files(int(pull["number"]))
            if not str(path).startswith(allowed_prefixes)
        ]
        if stray:
            return Verdict(
                "BLOCKED", "AUTHORIZATION_SCOPE_VIOLATION",
                {"paths": sorted(stray)},
            )

        registry = self._facts.stations("main")
        author = normalize_login((pull.get("user") or {}).get("login"))
        latest: dict[str, dict[str, Any]] = {}
        for review in self._facts.reviews_for_pull(int(pull["number"])):
            login = normalize_login((review.get("user") or {}).get("login"))
            submitted = str(review.get("submitted_at") or "")
            if login and submitted >= str(latest.get(login, {}).get("submitted_at") or ""):
                latest[login] = review
        approved = [
            review for login, review in latest.items()
            if str(review.get("state") or "").upper() == "APPROVED"
            and login != author
            and str(review.get("commit_id") or "").lower() == pr_head
        ]

        def station_kind(login: str) -> str:
            return str(registry.get(login, "")).lower()

        qa = [r for r in approved if station_kind(normalize_login((r.get("user") or {}).get("login"))) == "qa-evidence"]
        carrier = [
            r for r in approved
            if station_kind(normalize_login((r.get("user") or {}).get("login"))) == "ruling-carrier"
        ]
        if not qa:
            return Verdict("BLOCKED", "AUTHORIZATION_QA_APPROVAL_MISSING", {"pr": pull["number"]})
        if not carrier:
            return Verdict(
                "BLOCKED", "AUTHORIZATION_RULING_APPROVAL_MISSING", {"pr": pull["number"]},
            )
        qa_login = normalize_login((qa[0].get("user") or {}).get("login"))
        carrier_login = normalize_login((carrier[0].get("user") or {}).get("login"))
        if qa_login == carrier_login:
            return Verdict(
                "BLOCKED", "AUTHORIZATION_IDENTITY_NOT_SEPARATED",
                {"login": qa_login},
            )

        return Verdict(
            "VERIFIED",
            "AUTHORIZATION_VERIFIED",
            {
                "authorization_id": authorization.authorization_id,
                "kind": authorization.kind,
                "pr": int(pull["number"]),
                "pr_head_sha": pr_head,
                "merge_commit_sha": merge_sha,
                "merged_at": pull.get("merged_at"),
                "blob_sha": remote_blob,
                "qa_reviewer": qa_login,
                "ruling_reviewer": carrier_login,
            },
        )


class GitHubFactsError(RuntimeError):
    """A read-only GitHub fact could not be established."""


class GitHubFactsClient:
    """Read-only GitHub facts, used to re-derive an authorization at use time.

    Every fact the verifier consumes comes from this client, never from the
    authorization document.  Any non-200 answer raises, and the verifier turns
    that into ``AUTHORIZATION_UNVERIFIABLE`` (fail-closed).
    """

    def __init__(
        self,
        *,
        repo: str,
        token: str | None = None,
        api_root: str = API_ROOT,
        timeout: int = 30,
    ) -> None:
        if not repo or repo.count("/") != 1:
            raise GitHubFactsError(f"invalid repo {repo!r}")
        self._repo = repo
        self._token = token if token is not None else (
            os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        )
        if not self._token:
            raise GitHubFactsError("a token is required for GitHub facts")
        self._api_root = api_root.rstrip("/")
        self._timeout = timeout

    # -- plumbing ---------------------------------------------------------
    def _get(self, path: str) -> Any:
        req = urlrequest.Request(
            self._api_root + path,
            method="GET",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "fpf-ledger-authorization/1",
            },
        )
        try:
            with urlrequest.urlopen(req, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8") or "null")
        except urlerror.HTTPError as exc:
            raw = exc.read().decode("utf-8") or "{}"
            raise GitHubFactsError(f"GET {path} failed: HTTP {exc.code} {raw}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise GitHubFactsError(f"GET {path} failed: {type(exc).__name__}: {exc}") from exc

    def _list(self, path: str) -> list[dict[str, Any]]:
        separator = "&" if "?" in path else "?"
        items: list[dict[str, Any]] = []
        for page in range(1, 101):
            chunk = self._get(f"{path}{separator}per_page=100&page={page}")
            if not isinstance(chunk, list):
                raise GitHubFactsError(f"GET {path} returned a non-list payload")
            items.extend(chunk)
            if len(chunk) < 100:
                return items
        raise GitHubFactsError(f"GET {path} exceeded 100 pages")

    # -- GitHubFacts ------------------------------------------------------
    def commits_for_path(self, path: str) -> list[dict[str, Any]]:
        quoted = path.lstrip("/")
        return self._list(f"/repos/{self._repo}/commits?path={quoted}")

    def pulls_for_commit(self, sha: str) -> list[dict[str, Any]]:
        return self._list(f"/repos/{self._repo}/commits/{sha}/pulls")

    def reviews_for_pull(self, number: int) -> list[dict[str, Any]]:
        return self._list(f"/repos/{self._repo}/pulls/{int(number)}/reviews")

    def pr_files(self, number: int) -> list[str]:
        return [
            str(item.get("filename") or "")
            for item in self._list(f"/repos/{self._repo}/pulls/{int(number)}/files")
        ]

    def content_blob_sha(self, path: str, ref: str) -> str | None:
        payload = self._get(f"/repos/{self._repo}/contents/{path.lstrip('/')}?ref={ref}")
        if not isinstance(payload, dict):
            return None
        value = payload.get("sha")
        return str(value).lower() if value else None

    def stations(self, ref: str) -> dict[str, str]:
        payload = self._get(f"/repos/{self._repo}/contents/.fpf/stations.yaml?ref={ref}")
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise GitHubFactsError(".fpf/stations.yaml is not a base64 file payload")
        raw = base64.b64decode(str(payload.get("content") or ""))
        from packages.fpf_policy.stations import parse as parse_stations

        registry = parse_stations(raw.decode("utf-8"))
        resolved: dict[str, str] = {}
        for station in registry.stations:
            for carrier in station.carriers:
                resolved[normalize_login(carrier)] = str(station.kind).lower()
        return resolved

    def check_run(self, check_run_id: int) -> dict[str, Any]:
        payload = self._get(f"/repos/{self._repo}/check-runs/{int(check_run_id)}")
        if not isinstance(payload, dict):
            raise GitHubFactsError(f"check run {check_run_id} returned a non-object payload")
        return payload
