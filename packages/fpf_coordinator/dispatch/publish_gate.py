"""Trusted publish gate for the event-driven state ledger (F2 v3–v7).

This module runs **only** from a pinned, main-ancestor checkout.  Everything it
consumes from the upstream run is untrusted data: the ZIP is inspected as bytes,
JSON is parsed with duplicate-key rejection, and no code or config from the
artifact is imported or executed.

Gate order (any failure = zero writes, non-zero exit):

STRUCTURE -> ARTIFACT_BINDING -> FACT_SOURCE_VERIFY -> TRUSTED_REPLAY
-> SUBJECT_BINDING -> STALE_BASE -> IDEMPOTENCY -> WRITE
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile
from typing import Any, Iterable, Mapping

from .events import EventBatch, EventValidationError, normalize_event
from .fact_source import (
    FactSourceError,
    canonical_bytes,
    compare_event_log,
    compare_event_sequence,
    sha256_hex,
    stable_observation,
)
from .reducer import projection_tasks_digest, reduce_events

UPSTREAM_IDENTITY = "UPSTREAM_IDENTITY"
RUN_BINDING = "RUN_BINDING"
ARTIFACT_OWNERSHIP = "ARTIFACT_OWNERSHIP"
ARTIFACT_DIGEST = "ARTIFACT_DIGEST"
ZIP_STRUCTURE = "ZIP_STRUCTURE"
ZIP_BOMB = "ZIP_BOMB"
JSON_DUPLICATE_KEY = "JSON_DUPLICATE_KEY"
JSON_SHAPE = "JSON_SHAPE"
MANIFEST_SCHEMA = "MANIFEST_SCHEMA"
CONTENT_DIGEST = "CONTENT_DIGEST"
TRUSTED_REPLAY_MISMATCH = "TRUSTED_REPLAY_MISMATCH"
SUBJECT_BINDING = "SUBJECT_BINDING"
STALE_BASE = "STALE_BASE"
IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"

ALLOWED_MEMBERS = {"manifest.json", "state-ledger.json", "event-log.jsonl"}
MAX_MEMBERS = 8
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
MAX_RATIO = 200
MAX_DEPTH = 32
MANIFEST_FIELDS = {
    "manifest_version", "task_id", "tested_sha", "base_sha", "base_blob_sha",
    "projection_digest", "event_log_digest", "sha256", "authorization_ref",
    "scope_expires_at", "project_id", "pr_number",
}


class GateError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError(JSON_DUPLICATE_KEY, key)
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise GateError(JSON_SHAPE, f"non-finite number {value}")


def _depth(value: Any, level: int = 0) -> int:
    if level > MAX_DEPTH:
        raise GateError(JSON_SHAPE, "depth")
    if isinstance(value, dict):
        return max([_depth(item, level + 1) for item in value.values()] or [level])
    if isinstance(value, list):
        return max([_depth(item, level + 1) for item in value] or [level])
    return level


def strict_json_loads(text: str) -> Any:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except GateError:
        raise
    except json.JSONDecodeError as exc:
        raise GateError(JSON_SHAPE, str(exc)) from exc
    _depth(value)
    return value


def _member_name(info: zipfile.ZipInfo) -> str:
    name = info.filename.replace("\\", "/")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise GateError(ZIP_STRUCTURE, f"absolute {name}")
    parts = [part for part in name.split("/") if part]
    if any(part == ".." for part in parts):
        raise GateError(ZIP_STRUCTURE, f"traversal {name}")
    mode = (info.external_attr >> 16) & 0o170000
    if mode and mode not in (stat.S_IFREG, stat.S_IFDIR):
        raise GateError(ZIP_STRUCTURE, f"non-regular {name}")
    return "/".join(parts)


def read_artifact(path: Path) -> dict[str, Any]:
    """ZIP hardening + JSON parsing + digest self-consistency (steps 5–9)."""
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise GateError(ZIP_STRUCTURE, str(exc)) from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise GateError(ZIP_STRUCTURE, f"{len(infos)} members")
        names: list[str] = []
        total = 0
        for info in infos:
            name = _member_name(info)
            names.append(name)
            if name not in ALLOWED_MEMBERS:
                raise GateError(ZIP_STRUCTURE, f"unexpected {name}")
            if info.file_size > MAX_FILE_BYTES:
                raise GateError(ZIP_BOMB, f"{name} {info.file_size}")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise GateError(ZIP_BOMB, f"total {total}")
            if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
                raise GateError(ZIP_BOMB, f"ratio {name}")
        if len({name.lower() for name in names}) != len(names):
            raise GateError(ZIP_STRUCTURE, "duplicate member")
        if "manifest.json" not in names or "state-ledger.json" not in names:
            raise GateError(ZIP_STRUCTURE, "missing required member")

        def read(name: str) -> bytes:
            with archive.open(name) as handle:
                return handle.read(MAX_FILE_BYTES + 1)

        manifest = strict_json_loads(read("manifest.json").decode("utf-8"))
        ledger = strict_json_loads(read("state-ledger.json").decode("utf-8"))
        raw_log = read("event-log.jsonl").decode("utf-8")

    if not isinstance(manifest, dict) or not isinstance(ledger, dict):
        raise GateError(JSON_SHAPE, "manifest/ledger must be objects")
    unknown = set(manifest) - MANIFEST_FIELDS
    if unknown:
        raise GateError(MANIFEST_SCHEMA, ",".join(sorted(unknown)))
    required = {"manifest_version", "task_id", "tested_sha", "base_sha",
                "base_blob_sha", "projection_digest", "event_log_digest", "sha256",
                "project_id", "pr_number"}
    if required - set(manifest):
        raise GateError(MANIFEST_SCHEMA, ",".join(sorted(required - set(manifest))))
    digests = manifest.get("sha256")
    if not isinstance(digests, dict) or set(digests) != {"state-ledger.json", "event-log.jsonl"}:
        raise GateError(MANIFEST_SCHEMA, "sha256 map")

    ledger_bytes = canonical_bytes(ledger)
    if sha256_hex(ledger_bytes) != str(digests["state-ledger.json"]):
        raise GateError(CONTENT_DIGEST, "state-ledger.json")
    log_lines = [line for line in raw_log.splitlines() if line.strip()]
    events: list[dict[str, Any]] = []
    for line in log_lines:
        parsed = strict_json_loads(line)
        if not isinstance(parsed, dict):
            raise GateError(JSON_SHAPE, "event log item")
        events.append(parsed)
    if sha256_hex(canonical_bytes(events)) != str(digests["event-log.jsonl"]):
        raise GateError(CONTENT_DIGEST, "event-log.jsonl")
    tasks = ledger.get("tasks")
    if not isinstance(tasks, list):
        raise GateError(JSON_SHAPE, "tasks")
    if projection_tasks_digest(tasks) != str(manifest["projection_digest"]):
        raise GateError(CONTENT_DIGEST, "projection_digest")
    return {"manifest": manifest, "ledger": ledger, "events": events}


def verify_artifact_binding(
    upstream: Mapping[str, Any],
    *,
    expected_path: str,
    artifact_digest: str,
) -> None:
    if upstream.get("path") != expected_path:
        raise GateError(UPSTREAM_IDENTITY, f"path {upstream.get('path')}")
    if upstream.get("event") != "workflow_dispatch":
        raise GateError(UPSTREAM_IDENTITY, f"event {upstream.get('event')}")
    if not upstream.get("workflow_id") or not upstream.get("head_sha"):
        raise GateError(RUN_BINDING, "workflow_id/head_sha")
    if str(upstream.get("run_attempt") or "") == "":
        raise GateError(RUN_BINDING, "run_attempt")
    if not artifact_digest.startswith("sha256:"):
        raise GateError(ARTIFACT_DIGEST, artifact_digest)


def verify_artifact_digest(path: Path, artifact_digest: str) -> None:
    actual = "sha256:" + sha256_hex(path.read_bytes())
    if actual != artifact_digest:
        raise GateError(ARTIFACT_DIGEST, f"{actual}!={artifact_digest}")


def trusted_replay(events: list[Mapping[str, Any]], task_id: str, project_id: str) -> dict[str, Any]:
    """Replay the candidate event log with the trusted reducer only."""
    normalized = []
    refusals: list[str] = []
    for raw in events:
        try:
            normalized.append(normalize_event(raw))
        except EventValidationError as exc:
            refusals.append(str(exc))
    if refusals:
        raise GateError(TRUSTED_REPLAY_MISMATCH, ",".join(refusals[:3]))
    batch = EventBatch(events=tuple(normalized), complete=True)
    reduction = reduce_events(batch, task_id=task_id, project_id=project_id)
    if not reduction.complete or reduction.refusals or reduction.reasons:
        raise GateError(
            TRUSTED_REPLAY_MISMATCH,
            ";".join(list(reduction.refusals) + list(reduction.reasons))[:300],
        )
    return {
        "task": dict(reduction.projection),
        "event_ids": list(reduction.event_ids),
        "ordered_ids": [event.event_id for event in reduction.ordered_events],
        "event_log_digest": reduction.event_log_digest,
    }


def _first_diff(left: Any, right: Any, path: str = "") -> str | None:
    if type(left) is not type(right):
        return f"{path or '$'}:type"
    if isinstance(left, dict):
        if set(left) != set(right):
            return f"{path or '$'}:keys"
        for key in sorted(left):
            diff = _first_diff(left[key], right[key], f"{path}.{key}" if path else key)
            if diff:
                return diff
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}:len"
        for index, (a, b) in enumerate(zip(left, right)):
            diff = _first_diff(a, b, f"{path}[{index}]")
            if diff:
                return diff
        return None
    return None if left == right else (path or "$")


def compare_projection(trusted_task: Mapping[str, Any], candidate_ledger: Mapping[str, Any]) -> None:
    tasks = candidate_ledger.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1:
        raise GateError(TRUSTED_REPLAY_MISMATCH, "candidate must hold exactly one task")
    candidate = dict(tasks[0])
    expected = dict(trusted_task)
    for payload in (candidate, expected):
        payload.pop("aggregate_version", None)
    diff = _first_diff(expected, candidate)
    if diff:
        raise GateError(TRUSTED_REPLAY_MISMATCH, diff)


def subject_binding(manifest: Mapping[str, Any], ledger: Mapping[str, Any]) -> str:
    tested_sha = str(manifest.get("tested_sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", tested_sha):
        raise GateError(SUBJECT_BINDING, "tested_sha")
    task_id = str(manifest.get("task_id") or "")
    tasks = ledger.get("tasks") or []
    if len(tasks) != 1 or str(tasks[0].get("task_id") or "") != task_id:
        raise GateError(SUBJECT_BINDING, "task ledger/task mismatch")
    return task_id


def stale_base(manifest: Mapping[str, Any], target: Mapping[str, Any]) -> None:
    if str(target.get("blob_sha") or "") != str(manifest.get("base_blob_sha") or ""):
        raise GateError(STALE_BASE, "ledger blob advanced")


def idempotency(manifest: Mapping[str, Any], probe: Mapping[str, Any]) -> str:
    digest = str(manifest.get("projection_digest") or "")
    branch = f"fpf/state-ledger/{digest[:16]}"
    if probe.get("branch") and str(probe["branch"]) != branch:
        raise GateError(IDEMPOTENCY_CONFLICT, "branch binding")
    if not probe.get("exists"):
        return "PROCEED"
    if str(probe.get("blob_sha") or "") == str(manifest.get("projection_digest") or "") or probe.get("same_content"):
        return "NOOP_ALREADY_PUBLISHED"
    raise GateError(IDEMPOTENCY_CONFLICT, "branch exists with different content")


def _read_json(path: str, code: str) -> dict[str, Any]:
    try:
        value = strict_json_loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise GateError(code, str(exc)) from exc
    if not isinstance(value, dict):
        raise GateError(code, "object required")
    return value


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    upstream = _read_json(args.upstream, RUN_BINDING)
    verify_artifact_binding(
        upstream, expected_path=args.expected_path, artifact_digest=args.artifact_digest,
    )
    verify_artifact_digest(Path(args.zip), args.artifact_digest)
    artifact = read_artifact(Path(args.zip))
    manifest = artifact["manifest"]
    task_id = subject_binding(manifest, artifact["ledger"])

    observation, rounds = stable_observation(
        args.repo, args.pr_number, task_id, args.project_id, args.token,
    )
    compare_event_log(list(observation.events), artifact["events"])

    replay = trusted_replay(artifact["events"], task_id, args.project_id)
    compare_event_sequence(
        replay["ordered_ids"],
        [str(event.get("event_id") or "") for event in artifact["events"]],
    )
    compare_projection(replay["task"], artifact["ledger"])

    stale_base(manifest, _read_json(args.target, STALE_BASE))
    decision = idempotency(manifest, _read_json(args.idempotency, IDEMPOTENCY_CONFLICT))
    return {
        "status": decision,
        "code": "OK",
        "task_id": task_id,
        "tested_sha": manifest["tested_sha"],
        "projection_digest": manifest["projection_digest"],
        "event_count": len(artifact["events"]),
        "fact_source_rounds": rounds,
        "pages": [
            {key: record[key] for key in (
                "pass", "endpoint", "page", "count",
                "first_event_id", "last_event_id", "page_sha256", "collected_at",
            )}
            for record in observation.pages
        ],
        "pr_before": observation.before,
        "pr_after": observation.after,
        "stable_observation": True,
        "atomic_snapshot_claimed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FPF trusted publish gate")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--project-id", default="FPF")
    parser.add_argument("--token-env", default="GH_TOKEN")
    parser.add_argument("--zip", required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--idempotency", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--expected-path", default=".github/workflows/state-project.yml",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.token = os.environ.get(args.token_env, "")
    try:
        decision = run_gate(args)
        code = 0
    except (GateError, FactSourceError) as exc:
        decision = {
            "status": "REJECTED",
            "code": getattr(exc, "code", "GATE_FAILED"),
            "detail": getattr(exc, "detail", str(exc)),
        }
        code = 2
    Path(args.out).write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
