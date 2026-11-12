# -*- coding: utf-8 -*-
"""Governed concurrency probe for ledger ref claims.

This is a *separate* repository-level ``contents: write`` carrier, not part of
the R4 claim exception.  Authorisation lives in
``.fpf/probe-authorizations.yaml``; every run consumes one fixed slot; probe
refs are retained as server-side evidence and never auto-deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib import error as urlerror
from urllib import request as urlrequest

import yaml

AUTH_SCHEMA = "fpf-probe-auth/v1"
REQUEST_SCHEMA = "fpf-probe-request/v1"
SLOT_SCHEMA = "fpf-probe-slot/v1"
# GitHub accepts 201 for arbitrary ref namespaces such as ``refs/fpf-probe/``
# but does not persist them.  Only refs/heads and refs/tags are durable, so the
# probe namespace lives under refs/tags/ (the same primitive used by claims).
PROBE_REF_PREFIX = "refs/tags/fpf-probe/"
API_ROOT = "https://api.github.com"

PROBE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{7,39}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

MAX_RUNS_CAP = 8
MAX_ATTEMPTS_CAP = 6
MAX_WINDOW_SECONDS = 120


def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        return {_nfc(key): _nfc(item) for key, item in value.items()}
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _nfc(value), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )


def canonical_json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ProbeError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class TransportUncertain(RuntimeError):
    """Timeout, connection error or 5xx: the outcome is unknown."""


@dataclass(frozen=True)
class ProbeAuthorization:
    authorization_id: str
    probe_id: str
    task_id: str
    work_order: str
    authorized_actors: tuple[str, ...]
    max_runs: int
    max_attempts: int
    max_window_seconds: int
    expires_at: str

    def constraints(self) -> dict[str, Any]:
        return {
            "schema_version": AUTH_SCHEMA,
            "probe_id": self.probe_id,
            "task_id": self.task_id,
            "work_order": self.work_order,
            "authorized_actors": list(self.authorized_actors),
            "max_runs": self.max_runs,
            "expires_at": self.expires_at,
        }

    def canonical_sha256(self) -> str:
        return sha256_hex(canonical_json_bytes(self.constraints()))


def authorization_id_for(
    *,
    probe_id: str,
    task_id: str,
    work_order: str,
    authorized_actors: Iterable[str],
    max_runs: int,
    expires_at: str,
) -> str:
    payload = {
        "schema_version": AUTH_SCHEMA,
        "probe_id": probe_id,
        "task_id": task_id,
        "work_order": work_order,
        "authorized_actors": list(sorted(set(authorized_actors))),
        "max_runs": int(max_runs),
        "expires_at": expires_at,
    }
    return "PA-" + sha256_hex(canonical_json_bytes(payload))


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise ProbeError(code, detail)


def _parse_utc(value: Any, code: str) -> str:
    if isinstance(value, datetime):
        text = value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        text = str(value or "")
    _require(bool(UTC_RE.match(text)), code, text)
    try:
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ProbeError(code, text) from exc
    return text


def load_registry(text: str) -> list[ProbeAuthorization]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProbeError("PROBE_REGISTRY_INVALID", str(exc)) from exc
    _require(isinstance(data, dict), "PROBE_REGISTRY_INVALID", "root")
    entries = data.get("probe_authorizations")
    _require(isinstance(entries, list) and entries, "PROBE_REGISTRY_INVALID", "entries")
    result: list[ProbeAuthorization] = []
    seen: set[str] = set()
    for raw in entries:
        _require(isinstance(raw, dict), "PROBE_REGISTRY_INVALID", "entry")
        probe_id = str(raw.get("probe_id") or "")
        _require(bool(PROBE_ID_RE.match(probe_id)), "PROBE_ID_INVALID", probe_id)
        actors_raw = raw.get("authorized_actors")
        _require(isinstance(actors_raw, list) and actors_raw, "PROBE_ACTORS_INVALID", probe_id)
        actors = [str(actor) for actor in actors_raw]
        _require(len(actors) == len(set(actors)), "PROBE_ACTORS_DUPLICATE", probe_id)
        _require(actors == sorted(actors), "PROBE_ACTORS_UNSORTED", probe_id)
        max_runs = raw.get("max_runs")
        _require(
            isinstance(max_runs, int) and 1 <= max_runs <= MAX_RUNS_CAP,
            "PROBE_MAX_RUNS_INVALID", str(max_runs),
        )
        max_attempts = int(raw.get("max_attempts") or 4)
        _require(2 <= max_attempts <= MAX_ATTEMPTS_CAP, "PROBE_ATTEMPTS_INVALID", str(max_attempts))
        max_window = int(raw.get("max_window_seconds") or 90)
        _require(30 <= max_window <= MAX_WINDOW_SECONDS, "PROBE_WINDOW_INVALID", str(max_window))
        expires_at = _parse_utc(raw.get("expires_at"), "PROBE_EXPIRY_INVALID")
        declared = str(raw.get("authorization_id") or "")
        computed = authorization_id_for(
            probe_id=probe_id,
            task_id=str(raw.get("task_id") or ""),
            work_order=str(raw.get("work_order") or ""),
            authorized_actors=actors,
            max_runs=max_runs,
            expires_at=expires_at,
        )
        _require(declared == computed, "PROBE_AUTH_ID_MISMATCH", declared)
        _require(
            raw.get("inherits_r4_claim_exception") is False,
            "PROBE_EXCEPTION_INHERITANCE_FORBIDDEN", probe_id,
        )
        _require(declared not in seen, "PROBE_AUTH_ID_DUPLICATE", declared)
        seen.add(declared)
        result.append(ProbeAuthorization(
            authorization_id=declared,
            probe_id=probe_id,
            task_id=str(raw.get("task_id") or ""),
            work_order=str(raw.get("work_order") or ""),
            authorized_actors=tuple(actors),
            max_runs=max_runs,
            max_attempts=max_attempts,
            max_window_seconds=max_window,
            expires_at=expires_at,
        ))
    return result


def select_authorization(
    registry: Iterable[ProbeAuthorization],
    *,
    probe_id: str,
    actor: str,
    triggering_actor: str,
    now: datetime | None = None,
) -> ProbeAuthorization:
    _require(actor == triggering_actor, "PROBE_ACTOR_MISMATCH", f"{actor} != {triggering_actor}")
    for entry in registry:
        if entry.probe_id != probe_id:
            continue
        _require(actor in entry.authorized_actors, "PROBE_NOT_AUTHORIZED", actor)
        moment = now or datetime.now(timezone.utc)
        expiry = datetime.strptime(entry.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        _require(moment <= expiry, "PROBE_AUTH_EXPIRED", entry.expires_at)
        return entry
    raise ProbeError("PROBE_NOT_AUTHORIZED", probe_id)


@dataclass(frozen=True)
class ProbeRequest:
    probe_id: str
    attempts: int
    window_seconds: int


def validate_request(data: Mapping[str, Any], authorization: ProbeAuthorization) -> ProbeRequest:
    _require(data.get("schema") == REQUEST_SCHEMA, "PROBE_REQUEST_SCHEMA", str(data.get("schema")))
    probe_id = str(data.get("probe_id") or "")
    _require(bool(PROBE_ID_RE.match(probe_id)), "PROBE_ID_INVALID", probe_id)
    _require(probe_id == authorization.probe_id, "PROBE_ID_MISMATCH", probe_id)
    attempts = data.get("attempts")
    _require(isinstance(attempts, int), "PROBE_ATTEMPTS_INVALID", str(attempts))
    _require(2 <= attempts <= authorization.max_attempts, "PROBE_ATTEMPTS_INVALID", str(attempts))
    window = data.get("window_seconds")
    _require(isinstance(window, int), "PROBE_WINDOW_INVALID", str(window))
    _require(30 <= window <= authorization.max_window_seconds, "PROBE_WINDOW_INVALID", str(window))
    return ProbeRequest(probe_id=probe_id, attempts=int(attempts), window_seconds=int(window))


class GitHubClient:
    def __init__(self, repo: str, token: str, timeout: int = 30) -> None:
        _require(bool(token), "TOKEN_MISSING")
        self.repo = repo
        self._token = token
        self._timeout = timeout

    def call(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> tuple[int, Any]:
        data = None
        if payload is not None:
            data = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        request = urlrequest.Request(
            API_ROOT + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "fpf-probe/1",
            },
        )
        try:
            with urlrequest.urlopen(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8") or "{}"
                return int(response.status), json.loads(raw)
        except urlerror.HTTPError as exc:
            raw = exc.read().decode("utf-8") or "{}"
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"message": raw}
            return int(exc.code), body
        except (urlerror.URLError, TimeoutError, OSError) as exc:
            raise TransportUncertain(str(exc)) from exc
        except json.JSONDecodeError as exc:
            raise TransportUncertain("non-JSON response") from exc


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class SlotOutcome:
    state: str
    slot: str = ""
    log: list[dict[str, Any]] = field(default_factory=list)


class SlotConsumer:
    """Fixed slots; ref creation is the atomic admission ticket."""

    def __init__(
        self,
        client: GitHubClient,
        authorization: ProbeAuthorization,
        *,
        run_id: str,
        run_attempt: str,
        actor: str,
        pinned_sha: str,
        base_sha: str,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._auth = authorization
        self._run_id = str(run_id)
        self._run_attempt = str(run_attempt)
        self._actor = actor
        self._pinned_sha = pinned_sha
        self._base_sha = base_sha
        self._sleep = sleep

    def _prefix(self) -> str:
        return f"{PROBE_REF_PREFIX}consumption/{self._auth.authorization_id}/"

    def _name(self, index: int) -> str:
        return f"slot-{index:03d}"

    def _record(self, name: str) -> dict[str, Any]:
        return {
            "schema": SLOT_SCHEMA,
            "authorization_id": self._auth.authorization_id,
            "slot": name,
            "run_id": self._run_id,
            "run_attempt": self._run_attempt,
            "actor": self._actor,
            "pinned_sha": self._pinned_sha,
            "created_at": _now(),
        }

    def read_slot(self, name: str) -> dict[str, Any] | None:
        # The Get-a-reference endpoint expects the short form without "refs/".
        short = f"{self._prefix()}{name}".removeprefix("refs/")
        status, ref = self._client.call(
            "GET", f"/repos/{self._client.repo}/git/ref/{short}",
        )
        if status == 404:
            return None
        _require(status == 200, "PROBE_SLOT_READ_FAILED", f"{name} HTTP {status}")
        obj = ref.get("object") or {}
        _require(str(obj.get("type")) == "tag", "PROBE_SLOT_CORRUPT", f"{name} type")
        status, tag = self._client.call(
            "GET", f"/repos/{self._client.repo}/git/tags/{obj.get('sha')}",
        )
        _require(status == 200, "PROBE_SLOT_CORRUPT", f"{name} tag HTTP {status}")
        try:
            record = json.loads(str(tag.get("message") or ""))
        except json.JSONDecodeError as exc:
            raise ProbeError("PROBE_SLOT_CORRUPT", f"{name} message") from exc
        _require(isinstance(record, dict), "PROBE_SLOT_CORRUPT", f"{name} message type")
        _require(record.get("schema") == SLOT_SCHEMA, "PROBE_SLOT_CORRUPT", f"{name} schema")
        return record

    def _verify(self, name: str, record: Mapping[str, Any]) -> None:
        ok = (
            str(record.get("run_id")) == self._run_id
            and str(record.get("authorization_id")) == self._auth.authorization_id
            and str(record.get("actor")) == self._actor
            and str(record.get("pinned_sha")) == self._pinned_sha
        )
        _require(ok, "PROBE_SLOT_SUBJECT_MISMATCH", name)

    def _create(self, name: str) -> int | None:
        record = self._record(name)
        try:
            status, tag = self._client.call(
                "POST",
                f"/repos/{self._client.repo}/git/tags",
                {
                    "tag": f"fpf-probe-slot/{name}",
                    "message": canonical_json(record) + "\n",
                    "object": self._base_sha,
                    "type": "commit",
                    "tagger": {
                        "name": "FPF Probe Slot",
                        "email": "fpf-probe@users.noreply.github.com",
                        "date": record["created_at"],
                    },
                },
            )
            if status != 201:
                return status
            status, _ = self._client.call(
                "POST",
                f"/repos/{self._client.repo}/git/refs",
                {"ref": f"{self._prefix()}{name}", "sha": tag.get("sha")},
            )
            return status
        except TransportUncertain:
            return None

    def claim(self) -> SlotOutcome:
        log: list[dict[str, Any]] = []
        existing: dict[str, dict[str, Any]] = {}
        for index in range(1, self._auth.max_runs + 1):
            name = self._name(index)
            record = self.read_slot(name)
            if record is None:
                continue
            existing[name] = record
            if str(record.get("run_id")) == self._run_id:
                self._verify(name, record)
                log.append({"at": _now(), "event": "resume", "slot": name})
                return SlotOutcome("BOUND", name, log)

        for index in range(1, self._auth.max_runs + 1):
            name = self._name(index)
            if name in existing:
                continue
            status = self._create(name)
            if status == 201:
                stored = self.read_slot(name)
                _require(stored is not None, "PROBE_SLOT_CORRUPT", f"{name} vanished")
                self._verify(name, stored)
                log.append({"at": _now(), "event": "create", "slot": name, "status": 201})
                return SlotOutcome("BOUND", name, log)
            if status in (409, 422):
                stored = self.read_slot(name)
                _require(stored is not None, "PROBE_SLOT_CORRUPT", f"{name} conflict without ref")
                if str(stored.get("run_id")) == self._run_id:
                    self._verify(name, stored)
                    return SlotOutcome("BOUND", name, log)
                log.append({"at": _now(), "event": "occupied", "slot": name, "status": status})
                continue
            for delay in (2, 5, 10):
                self._sleep(delay)
                stored = self.read_slot(name)
                log.append({"at": _now(), "event": "readback", "slot": name,
                            "found": stored is not None, "delay": delay})
                if stored is None:
                    continue
                if str(stored.get("run_id")) == self._run_id:
                    self._verify(name, stored)
                    return SlotOutcome("BOUND", name, log)
                # Confirmed occupied by another run: move on, this is not uncertain.
                break
            else:
                return SlotOutcome("CLAIM_OUTCOME_UNKNOWN", name, log)
            if status is None and stored is None:
                return SlotOutcome("CLAIM_OUTCOME_UNKNOWN", name, log)
            continue
        return SlotOutcome("PROBE_SLOTS_EXHAUSTED", "", log)


@dataclass
class ProbeRun:
    winners: int = 0
    conflicts: int = 0
    other_422: int = 0
    failures: int = 0
    waves: int = 0
    window_start: str = ""
    window_end: str = ""
    winner_sha: str = ""
    final_unique: bool = False

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class ProbeLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.write_text("", encoding="utf-8")

    def write(self, record: Mapping[str, Any]) -> None:
        line = canonical_json(dict(record)) + "\n"
        for secret in ("ghs_", "github_pat_", "ghp_"):
            if secret in line:
                line = line.replace(secret, "[REDACTED]")
        with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line)


def matching_refs(client: GitHubClient, probe_id: str) -> list[dict[str, Any]]:
    status, body = client.call(
        "GET", f"/repos/{client.repo}/git/matching-refs/{PROBE_REF_PREFIX}{probe_id}",
    )
    _require(status == 200 and isinstance(body, list), "PROBE_VERIFY_FAILED", f"HTTP {status}")
    return [item for item in body if isinstance(item, dict)]


def conflict_confirmed(
    client: GitHubClient,
    probe_id: str,
    message: str,
    winner_sha: str,
) -> bool:
    if message != "Reference already exists":
        return False
    if not winner_sha:
        return False
    matches = matching_refs(client, probe_id)
    if len(matches) != 1:
        return False
    item = matches[0]
    return (
        str(item.get("ref")) == f"{PROBE_REF_PREFIX}{probe_id}"
        and str((item.get("object") or {}).get("sha") or "") == winner_sha
    )


def run_probe(
    *,
    client: GitHubClient,
    probe_id: str,
    attempts: int,
    window_seconds: int,
    run_id: str,
    run_attempt: str,
    base_sha: str,
    log_path: Path,
    sleep: Callable[[float], None] = time.sleep,
) -> ProbeRun:
    _require(bool(PROBE_ID_RE.match(probe_id)), "PROBE_ID_INVALID", probe_id)
    _require(2 <= attempts <= MAX_ATTEMPTS_CAP, "PROBE_ATTEMPTS_INVALID", str(attempts))
    waves = max(2, int(window_seconds) // 15)
    log = ProbeLog(log_path)
    ref = f"{PROBE_REF_PREFIX}{probe_id}"
    status, tag = client.call(
        "POST",
        f"/repos/{client.repo}/git/tags",
        {
            "tag": f"fpf-probe/{probe_id}",
            "message": canonical_json({
                "schema": "fpf-probe-target/v1",
                "probe_id": probe_id,
                "run_id": run_id,
                "run_attempt": run_attempt,
                "created_at": _now(),
            }) + "\n",
            "object": base_sha,
            "type": "commit",
            "tagger": {"name": "FPF Claim Probe", "email": "fpf-probe@users.noreply.github.com", "date": _now()},
        },
    )
    _require(status == 201, "PROBE_TAG_FAILED", f"HTTP {status}")
    tag_sha = str(tag.get("sha") or "")
    _require(bool(tag_sha), "PROBE_TAG_FAILED", "no sha")

    result = ProbeRun(waves=waves)
    starts: list[str] = []
    ends: list[str] = []
    responses: list[dict[str, Any]] = []
    lock = threading.Lock()

    def fire(wave: int, index: int) -> None:
        started = _now()
        try:
            code, body = client.call(
                "POST", f"/repos/{client.repo}/git/refs", {"ref": ref, "sha": tag_sha},
            )
            error = ""
        except TransportUncertain as exc:
            code, body, error = None, {}, str(exc)
        finished = _now()
        record = {
            "ts_start": started,
            "ts_end": finished,
            "attempt": index,
            "wave": wave,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "method": "POST",
            "path": f"/repos/{client.repo}/git/refs",
            "ref": ref,
            "status": code,
            "response_message": str(body.get("message") or ""),
            "object_sha": str((body.get("object") or {}).get("sha") or ""),
            "error": error,
        }
        with lock:
            starts.append(started)
            ends.append(finished)
            responses.append(record)

    for wave in range(1, waves + 1):
        threads = [threading.Thread(target=fire, args=(wave, i)) for i in range(1, attempts + 1)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if wave < waves:
            sleep(15)

    for record in responses:
        if record["status"] == 201:
            result.winners += 1
            result.winner_sha = record["object_sha"] or result.winner_sha
            log.write({**record, "classified": "created"})

    # A concurrent run may be the winner.  The winner SHA is then the object of
    # the single existing ref; conflict classification still needs it.
    if result.winners == 0:
        matches = matching_refs(client, probe_id)
        if len(matches) == 1:
            result.winner_sha = str((matches[0].get("object") or {}).get("sha") or "")

    for record in responses:
        if record["status"] == 422:
            if conflict_confirmed(client, probe_id, record["response_message"], result.winner_sha):
                result.conflicts += 1
                log.write({**record, "classified": "conflict"})
            else:
                result.other_422 += 1
                log.write({**record, "classified": "other_422"})
        elif record["status"] != 201:
            result.failures += 1
            log.write({**record, "classified": "error"})

    matches = matching_refs(client, probe_id)
    result.final_unique = (
        len(matches) == 1
        and str(matches[0].get("ref")) == ref
        and str((matches[0].get("object") or {}).get("sha") or "") == result.winner_sha
    )
    result.window_start = min(starts) if starts else ""
    result.window_end = max(ends) if ends else ""
    return result


def _token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def command_run(args: argparse.Namespace) -> int:
    registry = load_registry(Path(args.registry).read_text(encoding="utf-8"))
    authorization = select_authorization(
        registry,
        probe_id=args.probe_id,
        actor=args.actor,
        triggering_actor=args.triggering_actor,
    )
    request = validate_request(
        {"schema": REQUEST_SCHEMA, "probe_id": args.probe_id,
         "attempts": args.attempts, "window_seconds": args.window},
        authorization,
    )
    client = GitHubClient(args.repo, _token())
    slot = SlotConsumer(
        client, authorization,
        run_id=args.run_id, run_attempt=args.run_attempt, actor=args.actor,
        pinned_sha=args.pinned_sha, base_sha=args.base_sha,
    ).claim()
    if slot.state != "BOUND":
        print(json.dumps({"status": slot.state, "slot": slot.slot, "log": slot.log}))
        return 1
    result = run_probe(
        client=client,
        probe_id=request.probe_id,
        attempts=request.attempts,
        window_seconds=request.window_seconds,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        base_sha=args.base_sha,
        log_path=Path(args.log),
    )
    passed = (
        result.winners <= 1 and result.conflicts > 0 and bool(result.winner_sha)
        and result.other_422 == 0 and result.failures == 0 and result.final_unique
    )
    summary = {
        "status": "PASS" if passed else "FAIL",
        "authorization_id": authorization.authorization_id,
        "slot": slot.slot,
        "pinned_sha": args.pinned_sha,
        "probe": result.as_dict(),
    }
    Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpf-probe")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repo", required=True)
    run.add_argument("--registry", default=".fpf/probe-authorizations.yaml")
    run.add_argument("--probe-id", required=True)
    run.add_argument("--attempts", type=int, required=True)
    run.add_argument("--window", type=int, required=True)
    run.add_argument("--actor", required=True)
    run.add_argument("--triggering-actor", required=True)
    run.add_argument("--pinned-sha", required=True)
    run.add_argument("--base-sha", required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--run-attempt", required=True)
    run.add_argument("--log", required=True)
    run.add_argument("--summary", required=True)
    run.set_defaults(func=command_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ProbeError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": exc.code, "detail": exc.detail}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
