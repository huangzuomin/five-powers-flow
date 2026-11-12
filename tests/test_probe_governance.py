# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

from packages.fpf_coordinator.dispatch.probe import (
    AUTH_SCHEMA,
    PROBE_REF_PREFIX,
    ProbeError,
    SlotConsumer,
    TransportUncertain,
    authorization_id_for,
    conflict_confirmed,
    load_registry,
    matching_refs,
    run_probe,
    select_authorization,
    validate_request,
)


class FakeGitHub:
    repo = "owner/repo"

    def __init__(self) -> None:
        self.refs: dict[str, dict] = {}
        self.tags: dict[str, str] = {}
        self._lock = threading.Lock()
        self._tag_seq = 0
        self.raise_uncertain = False

    def _tag(self, message: str) -> str:
        with self._lock:
            self._tag_seq += 1
            sha = f"tag{self._tag_seq:04d}"
            self.tags[sha] = message
            return sha

    def call(self, method: str, path: str, payload=None):
        if method == "POST" and path.endswith("/git/tags"):
            sha = self._tag(str(payload["message"]))
            return 201, {"sha": sha}
        if method == "POST" and path.endswith("/git/refs"):
            if self.raise_uncertain:
                raise TransportUncertain("simulated timeout")
            ref = str(payload["ref"])
            with self._lock:
                if ref in self.refs:
                    return 422, {"message": "Reference already exists"}
                self.refs[ref] = {"object": {"sha": payload["sha"], "type": "tag"}}
                return 201, {"object": {"sha": payload["sha"]}}
        if method == "GET" and "/git/ref/" in path:
            ref = path.split("/git/ref/", 1)[1]
            with self._lock:
                value = self.refs.get(ref)
            return (200, value) if value else (404, {"message": "Not Found"})
        if method == "GET" and "/git/tags/" in path:
            sha = path.rsplit("/", 1)[1]
            message = self.tags.get(sha)
            return (200, {"message": message}) if message is not None else (404, {})
        if method == "GET" and "/git/matching-refs/" in path:
            prefix = path.split("/git/matching-refs/", 1)[1]
            with self._lock:
                items = [
                    {"ref": ref, "object": value["object"]}
                    for ref, value in self.refs.items() if ref.startswith(prefix)
                ]
            return 200, items
        raise AssertionError(f"unexpected call {method} {path}")


def build_registry(max_runs: int = 2, actors=("alpha", "beta")) -> str:
    actors = list(actors)
    auth_id = authorization_id_for(
        probe_id="g4-probe-20261112-a",
        task_id="FPF2-G4-REDUCER-01",
        work_order="WO-20261112-g4-final-remediation",
        authorized_actors=actors,
        max_runs=max_runs,
        expires_at="2026-12-12T00:00:00Z",
    )
    return yaml.safe_dump({
        "schema_version": AUTH_SCHEMA,
        "probe_authorizations": [{
            "authorization_id": auth_id,
            "probe_id": "g4-probe-20261112-a",
            "task_id": "FPF2-G4-REDUCER-01",
            "work_order": "WO-20261112-g4-final-remediation",
            "authorized_actors": actors,
            "max_runs": max_runs,
            "max_attempts": 4,
            "max_window_seconds": 90,
            "expires_at": "2026-12-12T00:00:00Z",
            "inherits_r4_claim_exception": False,
        }],
    })


class AuthorizationTests(unittest.TestCase):
    def test_repository_registry_loads(self) -> None:
        root = Path(__file__).resolve().parents[1]
        entries = load_registry(
            (root / ".fpf" / "probe-authorizations.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].expires_at, "2026-12-12T00:00:00Z")

    def test_registry_roundtrip(self) -> None:
        entries = load_registry(build_registry())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].authorized_actors, ("alpha", "beta"))
        self.assertEqual(
            entries[0].canonical_sha256(), entries[0].canonical_sha256(),
        )

    def test_registry_rejects_tampered_actor(self) -> None:
        text = build_registry().replace("- alpha", "- aardvark")
        with self.assertRaises(ProbeError) as ctx:
            load_registry(text)
        self.assertEqual(ctx.exception.code, "PROBE_AUTH_ID_MISMATCH")

    def test_registry_rejects_unsorted_actors(self) -> None:
        text = build_registry(actors=("beta", "alpha"))
        with self.assertRaises(ProbeError) as ctx:
            load_registry(text)
        self.assertEqual(ctx.exception.code, "PROBE_ACTORS_UNSORTED")

    def test_select_rejects_unknown_actor(self) -> None:
        entry = load_registry(build_registry())[0]
        with self.assertRaises(ProbeError) as ctx:
            select_authorization(
                [entry], probe_id=entry.probe_id, actor="mallory", triggering_actor="mallory",
            )
        self.assertEqual(ctx.exception.code, "PROBE_NOT_AUTHORIZED")

    def test_select_rejects_actor_divergence(self) -> None:
        entry = load_registry(build_registry())[0]
        with self.assertRaises(ProbeError) as ctx:
            select_authorization(
                [entry], probe_id=entry.probe_id, actor="alpha", triggering_actor="beta",
            )
        self.assertEqual(ctx.exception.code, "PROBE_ACTOR_MISMATCH")

    def test_select_rejects_expired(self) -> None:
        entry = load_registry(build_registry())[0]
        with self.assertRaises(ProbeError) as ctx:
            select_authorization(
                [entry], probe_id=entry.probe_id, actor="alpha", triggering_actor="alpha",
                now=datetime(2027, 1, 1, tzinfo=timezone.utc),
            )
        self.assertEqual(ctx.exception.code, "PROBE_AUTH_EXPIRED")

    def test_request_bounds(self) -> None:
        entry = load_registry(build_registry())[0]
        ok = validate_request(
            {"schema": "fpf-probe-request/v1", "probe_id": entry.probe_id,
             "attempts": 4, "window_seconds": 60},
            entry,
        )
        self.assertEqual(ok.attempts, 4)
        with self.assertRaises(ProbeError):
            validate_request(
                {"schema": "fpf-probe-request/v1", "probe_id": entry.probe_id,
                 "attempts": 9, "window_seconds": 60},
                entry,
            )
        with self.assertRaises(ProbeError):
            validate_request(
                {"schema": "fpf-probe-request/v1", "probe_id": entry.probe_id,
                 "attempts": 4, "window_seconds": 600},
                entry,
            )


class SlotTests(unittest.TestCase):
    def consumer(self, client, entry, *, run_id="1", actor="alpha", pinned="a" * 40):
        return SlotConsumer(
            client, entry, run_id=run_id, run_attempt="1", actor=actor,
            pinned_sha=pinned, base_sha="b" * 40, sleep=lambda _: None,
        )

    def test_single_consumer_binds_slot_one(self) -> None:
        client, entry = FakeGitHub(), load_registry(build_registry())[0]
        outcome = self.consumer(client, entry).claim()
        self.assertEqual(outcome.state, "BOUND")
        self.assertEqual(outcome.slot, "slot-001")

    def test_second_consumer_uses_next_slot(self) -> None:
        client, entry = FakeGitHub(), load_registry(build_registry())[0]
        first = self.consumer(client, entry, run_id="1").claim()
        second = self.consumer(client, entry, run_id="2").claim()
        self.assertEqual(first.slot, "slot-001")
        self.assertEqual(second.slot, "slot-002")

    def test_resume_does_not_consume_a_new_slot(self) -> None:
        client, entry = FakeGitHub(), load_registry(build_registry())[0]
        self.consumer(client, entry, run_id="1").claim()
        again = self.consumer(client, entry, run_id="1").claim()
        self.assertEqual(again.slot, "slot-001")
        self.assertEqual(len(client.refs), 1)

    def test_slots_exhausted(self) -> None:
        client, entry = FakeGitHub(), load_registry(build_registry(max_runs=2))[0]
        self.consumer(client, entry, run_id="1").claim()
        self.consumer(client, entry, run_id="2").claim()
        third = self.consumer(client, entry, run_id="3").claim()
        self.assertEqual(third.state, "PROBE_SLOTS_EXHAUSTED")
        self.assertEqual(len(client.refs), 2)

    def test_uncertain_claim_does_not_take_another_slot(self) -> None:
        client, entry = FakeGitHub(), load_registry(build_registry())[0]
        client.raise_uncertain = True
        outcome = self.consumer(client, entry).claim()
        self.assertEqual(outcome.state, "CLAIM_OUTCOME_UNKNOWN")
        self.assertEqual(client.refs, {})

    def test_resume_subject_mismatch(self) -> None:
        client, entry = FakeGitHub(), load_registry(build_registry())[0]
        self.consumer(client, entry, run_id="1").claim()
        with self.assertRaises(ProbeError) as ctx:
            self.consumer(client, entry, run_id="1", actor="beta").claim()
        self.assertEqual(ctx.exception.code, "PROBE_SLOT_SUBJECT_MISMATCH")

    def test_corrupt_slot_tag(self) -> None:
        client, entry = FakeGitHub(), load_registry(build_registry())[0]
        prefix = f"{PROBE_REF_PREFIX}consumption/{entry.authorization_id}/"
        client.tags["tagbad"] = "not-json"
        client.refs[prefix + "slot-001"] = {"object": {"sha": "tagbad", "type": "tag"}}
        with self.assertRaises(ProbeError) as ctx:
            self.consumer(client, entry).claim()
        self.assertEqual(ctx.exception.code, "PROBE_SLOT_CORRUPT")


class ProbeRunTests(unittest.TestCase):
    def test_single_winner_and_strict_conflicts(self) -> None:
        client = FakeGitHub()
        probe_id = "g4-probe-20261112-a"
        with tempfile.TemporaryDirectory() as tmp:
            result = run_probe(
                client=client, probe_id=probe_id, attempts=4, window_seconds=30,
                run_id="1", run_attempt="1", base_sha="b" * 40,
                log_path=Path(tmp) / "probe.jsonl", sleep=lambda _: None,
            )
        self.assertEqual(result.winners, 1)
        self.assertEqual(result.conflicts, 7)
        self.assertEqual(result.other_422, 0)
        self.assertEqual(result.failures, 0)
        self.assertTrue(result.final_unique)

    def test_conflict_requires_exact_message(self) -> None:
        client = FakeGitHub()
        probe_id = "g4-probe-20261112-a"
        client.refs[f"{PROBE_REF_PREFIX}{probe_id}"] = {
            "object": {"sha": "tag0001", "type": "tag"},
        }
        self.assertFalse(conflict_confirmed(client, probe_id, "Validation Failed", "tag0001"))
        self.assertTrue(conflict_confirmed(client, probe_id, "Reference already exists", "tag0001"))

    def test_conflict_requires_matching_sha(self) -> None:
        client = FakeGitHub()
        probe_id = "g4-probe-20261112-a"
        client.refs[f"{PROBE_REF_PREFIX}{probe_id}"] = {
            "object": {"sha": "tag0001", "type": "tag"},
        }
        self.assertFalse(conflict_confirmed(client, probe_id, "Reference already exists", "other"))
        self.assertEqual(len(matching_refs(client, probe_id)), 1)


class WorkflowPermissionTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        root = Path(__file__).resolve().parents[1]
        return yaml.safe_load((root / ".github" / "workflows" / name).read_text(encoding="utf-8"))

    def triggers(self, doc: dict) -> dict:
        return doc.get("on") or doc.get(True) or {}

    def test_trigger_is_dispatch_only_and_read_only(self) -> None:
        doc = self.load("state-claim-probe-trigger.yml")
        self.assertEqual(set(self.triggers(doc)), {"workflow_dispatch"})
        self.assertEqual(doc["permissions"], {})
        for job in doc["jobs"].values():
            self.assertEqual(job["permissions"], {"contents": "read"})

    def test_probe_is_workflow_run_and_writes_only_in_job(self) -> None:
        doc = self.load("state-claim-probe.yml")
        self.assertEqual(set(self.triggers(doc)), {"workflow_run"})
        self.assertEqual(doc["permissions"], {})
        job = doc["jobs"]["probe"]
        self.assertEqual(job["permissions"], {"contents": "write", "actions": "read"})
        checkout = [s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout")][0]
        self.assertEqual(checkout["with"]["ref"], "main")


if __name__ == "__main__":
    unittest.main()
