"""Trusted publish gate tests: ZIP hardening, JSON shape, digests, replay, idempotency."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from packages.fpf_coordinator.dispatch import publish_gate
from packages.fpf_coordinator.dispatch.publish_gate import (
    GateError,
    ARTIFACT_DIGEST,
    CONTENT_DIGEST,
    IDEMPOTENCY_CONFLICT,
    JSON_DUPLICATE_KEY,
    JSON_SHAPE,
    MANIFEST_SCHEMA,
    STALE_BASE,
    TRUSTED_REPLAY_MISMATCH,
    ZIP_STRUCTURE,
    compare_projection,
    idempotency,
    read_artifact,
    stale_base,
    strict_json_loads,
    verify_artifact_digest,
)
from packages.fpf_coordinator.dispatch.reducer import projection_tasks_digest

TASK = {"task_id": "FPF2-G4-EVDEMO-01", "project_id": "FPF", "lifecycle_label": "MERGED"}


def canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def build_zip(path: Path, *, extra: dict[str, bytes] | None = None) -> dict:
    ledger = {"schema_version": "fpf.state-ledger/v1", "source": {"repo": "o/r"}, "tasks": [TASK]}
    events = [{"event_id": "a" * 64, "type": "TASK_OPENED"}]
    manifest = {
        "manifest_version": 1,
        "task_id": TASK["task_id"],
        "project_id": "FPF",
        "pr_number": 1,
        "tested_sha": "a" * 40,
        "base_sha": "b" * 40,
        "base_blob_sha": "c" * 40,
        "projection_digest": projection_tasks_digest([TASK]),
        "event_log_digest": "d" * 64,
        "sha256": {
            "state-ledger.json": hashlib.sha256(canonical(ledger)).hexdigest(),
            "event-log.jsonl": hashlib.sha256(canonical(events)).hexdigest(),
        },
        "authorization_ref": "WO-TEST",
        "scope_expires_at": "2026-12-12T00:00:00Z",
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("state-ledger.json", json.dumps(ledger))
        archive.writestr("event-log.jsonl", "\n".join(json.dumps(item) for item in events) + "\n")
        for name, payload in (extra or {}).items():
            archive.writestr(name, payload)
    return manifest


class JsonShapeTests(unittest.TestCase):
    def test_nested_duplicate_keys_are_rejected(self) -> None:
        with self.assertRaises(GateError) as ctx:
            strict_json_loads('{"a": {"b": 1, "b": 2}}')
        self.assertEqual(ctx.exception.code, JSON_DUPLICATE_KEY)

    def test_nan_is_rejected(self) -> None:
        with self.assertRaises(GateError) as ctx:
            strict_json_loads('{"a": NaN}')
        self.assertEqual(ctx.exception.code, JSON_SHAPE)

    def test_depth_is_bounded(self) -> None:
        with self.assertRaises(GateError) as ctx:
            strict_json_loads("[" * 40 + "]" * 40)
        self.assertEqual(ctx.exception.code, JSON_SHAPE)


class ZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "candidate.zip"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_well_formed_artifact_is_accepted(self) -> None:
        build_zip(self.path)
        artifact = read_artifact(self.path)
        self.assertEqual(artifact["manifest"]["task_id"], TASK["task_id"])
        self.assertEqual(len(artifact["events"]), 1)

    def test_path_traversal_is_rejected(self) -> None:
        build_zip(self.path, extra={"../evil.json": b"{}"})
        with self.assertRaises(GateError) as ctx:
            read_artifact(self.path)
        self.assertEqual(ctx.exception.code, ZIP_STRUCTURE)

    def test_unexpected_member_is_rejected(self) -> None:
        build_zip(self.path, extra={"run.py": b"print(1)"})
        with self.assertRaises(GateError) as ctx:
            read_artifact(self.path)
        self.assertEqual(ctx.exception.code, ZIP_STRUCTURE)

    def test_ledger_digest_mismatch_is_rejected(self) -> None:
        build_zip(self.path)
        data = {}
        with zipfile.ZipFile(self.path) as archive:
            for name in archive.namelist():
                data[name] = archive.read(name)
        manifest = json.loads(data["manifest.json"])
        manifest["sha256"]["state-ledger.json"] = "0" * 64
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, payload in data.items():
                archive.writestr(name, json.dumps(manifest) if name == "manifest.json" else payload)
        with self.assertRaises(GateError) as ctx:
            read_artifact(self.path)
        self.assertEqual(ctx.exception.code, CONTENT_DIGEST)

    def test_unknown_manifest_field_is_rejected(self) -> None:
        build_zip(self.path)
        data = {}
        with zipfile.ZipFile(self.path) as archive:
            for name in archive.namelist():
                data[name] = archive.read(name)
        manifest = json.loads(data["manifest.json"])
        manifest["surprise"] = True
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, payload in data.items():
                archive.writestr(name, json.dumps(manifest) if name == "manifest.json" else payload)
        with self.assertRaises(GateError) as ctx:
            read_artifact(self.path)
        self.assertEqual(ctx.exception.code, MANIFEST_SCHEMA)

    def test_artifact_digest_must_match(self) -> None:
        build_zip(self.path)
        with self.assertRaises(GateError) as ctx:
            verify_artifact_digest(self.path, "sha256:" + "0" * 64)
        self.assertEqual(ctx.exception.code, ARTIFACT_DIGEST)


class ReplayCompareTests(unittest.TestCase):
    def test_identical_projection_passes(self) -> None:
        compare_projection(TASK, {"tasks": [dict(TASK)]})

    def test_field_difference_names_the_path(self) -> None:
        candidate = dict(TASK, lifecycle_label="DRAFT_WORK_ORDER")
        with self.assertRaises(GateError) as ctx:
            compare_projection(TASK, {"tasks": [candidate]})
        self.assertEqual(ctx.exception.code, TRUSTED_REPLAY_MISMATCH)
        self.assertIn("lifecycle_label", ctx.exception.detail)

    def test_multiple_tasks_are_rejected(self) -> None:
        with self.assertRaises(GateError) as ctx:
            compare_projection(TASK, {"tasks": [dict(TASK), dict(TASK)]})
        self.assertEqual(ctx.exception.code, TRUSTED_REPLAY_MISMATCH)


class StaleAndIdempotencyTests(unittest.TestCase):
    def test_stale_base_is_rejected(self) -> None:
        with self.assertRaises(GateError) as ctx:
            stale_base({"base_blob_sha": "a"}, {"blob_sha": "b"})
        self.assertEqual(ctx.exception.code, STALE_BASE)

    def test_matching_base_passes(self) -> None:
        stale_base({"base_blob_sha": "a"}, {"blob_sha": "a"})

    def test_fresh_branch_proceeds(self) -> None:
        manifest = {"projection_digest": "f" * 64}
        self.assertEqual(
            idempotency(manifest, {"branch": "", "exists": False}), "PROCEED",
        )

    def test_same_content_is_a_noop(self) -> None:
        manifest = {"projection_digest": "f" * 64}
        self.assertEqual(
            idempotency(
                manifest,
                {"branch": "fpf/state-ledger/" + "f" * 16, "exists": True, "same_content": True},
            ),
            "NOOP_ALREADY_PUBLISHED",
        )

    def test_conflicting_branch_is_rejected(self) -> None:
        manifest = {"projection_digest": "f" * 64}
        with self.assertRaises(GateError) as ctx:
            idempotency(
                manifest,
                {"branch": "fpf/state-ledger/" + "f" * 16, "exists": True, "blob_sha": "x"},
            )
        self.assertEqual(ctx.exception.code, IDEMPOTENCY_CONFLICT)


if __name__ == "__main__":
    unittest.main()
