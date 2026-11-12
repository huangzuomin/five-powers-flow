# -*- coding: utf-8 -*-
"""B-01: ledger authorizations are derived from merged GitHub facts only."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fpf_unittest_support import raises, suite_from_globals  # noqa: E402

from packages.fpf_coordinator.dispatch.authorization import (
    AUTH_DIR,
    SCHEMA,
    AuthorizationError,
    AuthorizationVerifier,
    authorization_id_for,
    validate_body,
)

HEAD = "1" * 40
BASE = "2" * 40
MERGE = "3" * 40
QA_BOT = "fpf-qa-bot-huangzuomin[bot]"
CARRIER = "fpf-reviewer-huangzuomin[bot]"


def make_authorization(kind: str = "LEDGER_INIT", **overrides):
    body = {
        "schema": SCHEMA,
        "kind": kind,
        "repo": "huangzuomin/five-powers-flow",
        "task_id": "FPF2-G4-REDUCER-01",
        "scope": "ledger init",
        "one_time": True,
        "reason": "test",
    }
    if kind == "LEDGER_INIT":
        body.update({
            "baseline_sha": BASE,
            "baseline_ledger_blob_sha": None,
            "expected_history_commits": 0,
        })
    else:
        body.update({
            "tip_sha": "4" * 40,
            "failure_check_run_id": 99,
            "init_id": "5" * 64,
        })
    body.update(overrides)
    body["authorization_id"] = authorization_id_for(body)
    return validate_body(body)


class FakeFacts:
    def __init__(self, **over):
        self.commits = over.get("commits", [{"sha": "6" * 40}])
        self.pulls = over.get("pulls", [{
            "number": 77,
            "merged": True,
            "merged_at": "2026-11-12T00:00:00Z",
            "base": {"ref": "main", "sha": BASE},
            "head": {"sha": HEAD},
            "merge_commit_sha": MERGE,
            "user": {"login": "huangzuomin"},
        }])
        self.reviews = over.get("reviews", [
            {"state": "APPROVED", "commit_id": HEAD, "user": {"login": QA_BOT},
             "submitted_at": "2026-11-12T01:00:00Z"},
            {"state": "APPROVED", "commit_id": HEAD, "user": {"login": CARRIER},
             "submitted_at": "2026-11-12T02:00:00Z"},
        ])
        self.files = over.get("files", [f"{AUTH_DIR}/{'a'*64}.yaml"])
        self.blob = over.get("blob", "b" * 40)
        self.registry = over.get("registry", {
            "huangzuomin": "dev",
            QA_BOT: "qa-evidence",
            CARRIER: "ruling-carrier",
        })
        self.fail = over.get("fail", False)

    def commits_for_path(self, path):
        if self.fail:
            raise RuntimeError("api down")
        return self.commits

    def pulls_for_commit(self, sha):
        return self.pulls

    def reviews_for_pull(self, number):
        return self.reviews

    def pr_files(self, number):
        return self.files

    def content_blob_sha(self, path, ref):
        return self.blob

    def stations(self, ref):
        return self.registry


def verify(auth, facts, local_blob="b" * 40, revoked=False):
    return AuthorizationVerifier(facts, "huangzuomin/five-powers-flow").verify(
        auth, local_blob_sha=local_blob, revoked=revoked,
    )


def test_authorization_accepts_a_well_formed_merged_gate_pr() -> None:
    auth = make_authorization()
    verdict = verify(auth, FakeFacts(files=[auth.path]))
    assert verdict.ok, verdict
    assert verdict.evidence["qa_reviewer"] == QA_BOT
    assert verdict.evidence["ruling_reviewer"] == CARRIER


def test_declared_identity_fields_are_refused() -> None:
    with raises(AuthorizationError) as excinfo:
        validate_body({
            "schema": SCHEMA, "kind": "LEDGER_INIT", "authorization_id": "a" * 64,
            "repo": "o/r", "task_id": "t", "scope": "s", "one_time": True,
            "baseline_sha": BASE, "baseline_ledger_blob_sha": None,
            "expected_history_commits": 0, "authorized_by": "project-owner",
        })
    assert excinfo.value.reason == "AUTHORIZATION_FIELD_FORBIDDEN"


def test_authorization_id_must_be_recomputable() -> None:
    body = {
        "schema": SCHEMA, "kind": "LEDGER_INIT", "authorization_id": "a" * 64,
        "repo": "o/r", "task_id": "t", "scope": "s", "one_time": True,
        "baseline_sha": BASE, "baseline_ledger_blob_sha": None,
        "expected_history_commits": 0,
    }
    with raises(AuthorizationError) as excinfo:
        validate_body(body)
    assert excinfo.value.reason == "AUTHORIZATION_ID_MISMATCH"


def test_zero_history_with_a_blob_is_rejected() -> None:
    with raises(AuthorizationError) as excinfo:
        make_authorization(expected_history_commits=0, baseline_ledger_blob_sha="b" * 40)
    assert excinfo.value.reason == "AUTHORIZATION_HISTORY_HINT_INVALID"


def test_an_unmerged_pull_never_authorises() -> None:
    auth = make_authorization()
    facts = FakeFacts(pulls=[{
        "number": 77, "merged": False, "base": {"ref": "main", "sha": BASE},
        "head": {"sha": HEAD}, "merge_commit_sha": None,
        "user": {"login": "huangzuomin"},
    }], files=[auth.path])
    verdict = verify(auth, facts)
    assert verdict.status == "BLOCKED"
    assert verdict.reason == "AUTHORIZATION_NOT_MERGED"


def test_a_missing_ruling_carrier_approval_blocks() -> None:
    auth = make_authorization()
    facts = FakeFacts(files=[auth.path], reviews=[
        {"state": "APPROVED", "commit_id": HEAD, "user": {"login": QA_BOT},
         "submitted_at": "2026-11-12T01:00:00Z"},
    ])
    verdict = verify(auth, facts)
    assert verdict.reason == "AUTHORIZATION_RULING_APPROVAL_MISSING"


def test_an_approval_pinned_to_an_old_head_blocks() -> None:
    auth = make_authorization()
    facts = FakeFacts(files=[auth.path], reviews=[
        {"state": "APPROVED", "commit_id": "9" * 40, "user": {"login": QA_BOT},
         "submitted_at": "2026-11-12T01:00:00Z"},
        {"state": "APPROVED", "commit_id": "9" * 40, "user": {"login": CARRIER},
         "submitted_at": "2026-11-12T02:00:00Z"},
    ])
    verdict = verify(auth, facts)
    assert verdict.reason == "AUTHORIZATION_QA_APPROVAL_MISSING"


def test_a_changed_later_review_supersedes_the_earlier_approval() -> None:
    auth = make_authorization()
    facts = FakeFacts(files=[auth.path], reviews=[
        {"state": "APPROVED", "commit_id": HEAD, "user": {"login": QA_BOT},
         "submitted_at": "2026-11-12T01:00:00Z"},
        {"state": "CHANGES_REQUESTED", "commit_id": HEAD, "user": {"login": QA_BOT},
         "submitted_at": "2026-11-12T03:00:00Z"},
        {"state": "APPROVED", "commit_id": HEAD, "user": {"login": CARRIER},
         "submitted_at": "2026-11-12T02:00:00Z"},
    ])
    verdict = verify(auth, facts)
    assert verdict.reason == "AUTHORIZATION_QA_APPROVAL_MISSING"


def test_two_commits_touching_the_authorization_invalidate_it() -> None:
    auth = make_authorization()
    verdict = verify(auth, FakeFacts(files=[auth.path], commits=[{"sha": "6" * 40}, {"sha": "7" * 40}]))
    assert verdict.reason == "AUTHORIZATION_HISTORY_INVALID"


def test_smuggled_paths_in_the_authorization_pr_are_refused() -> None:
    auth = make_authorization()
    verdict = verify(auth, FakeFacts(files=[auth.path, "packages/fpf_policy/pr_gate.py"]))
    assert verdict.reason == "AUTHORIZATION_SCOPE_VIOLATION"


def test_blob_drift_blocks() -> None:
    auth = make_authorization()
    verdict = verify(auth, FakeFacts(files=[auth.path], blob="c" * 40))
    assert verdict.reason == "AUTHORIZATION_CONTENT_DRIFT"


def test_api_failure_is_fail_closed() -> None:
    auth = make_authorization()
    verdict = verify(auth, FakeFacts(files=[auth.path], fail=True))
    assert verdict.reason == "AUTHORIZATION_UNVERIFIABLE"


def test_revocation_blocks_even_a_valid_authorization() -> None:
    auth = make_authorization()
    verdict = verify(auth, FakeFacts(files=[auth.path]), revoked=True)
    assert verdict.reason == "AUTHORIZATION_REVOKED"


def load_tests(loader, tests, pattern):
    return suite_from_globals(globals())
