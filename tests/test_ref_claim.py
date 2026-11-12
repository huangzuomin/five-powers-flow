# -*- coding: utf-8 -*-
"""D-01 / D-06: the claim primitive must be atomic and permanently binding."""
from __future__ import annotations

import base64
import threading

from packages.fpf_coordinator.dispatch.claims import (
    ClaimConflict,
    InMemoryClaimStore,
    claim_document,
    claim_message,
    consumption_id,
    verify_claim,
    verify_recovery_claim,
)
from packages.fpf_coordinator.dispatch.authorization import (
    Authorization,
    AuthorizationVerifier,
    GitHubFactsClient,
    GitHubFactsError,
    Verdict,
)

AUTH = "a" * 64
TIP = "b" * 40
DIGEST = "c" * 64


def _document(run_id: int = 7, failure_run_id: int = 99):
    return claim_document(
        authorization_id=AUTH, tip_sha=TIP, failure_run_id=failure_run_id,
        projection_digest=DIGEST, claimant_run_id=str(run_id),
        claimed_at="2026-11-12T00:00:00Z",
    )


def test_consumption_id_binds_the_four_tuple_and_ignores_the_claimant() -> None:
    first = consumption_id(AUTH, TIP, 99, DIGEST)
    second = consumption_id(AUTH, TIP, 99, DIGEST)
    other_tip = consumption_id(AUTH, "d" * 40, 99, DIGEST)
    other_failure = consumption_id(AUTH, TIP, 100, DIGEST)
    assert first == second
    assert first != other_tip
    assert first != other_failure
    assert _document(1)["consumption_id"] == _document(2)["consumption_id"]


def test_the_claim_message_is_canonical_and_stable() -> None:
    assert claim_message(_document()) == claim_message(_document())
    assert claim_message(_document()).endswith("\n")


def test_d_7_1_concurrent_claims_have_exactly_one_winner() -> None:
    store = InMemoryClaimStore()
    winners: list[int] = []
    losers: list[int] = []
    barrier = threading.Barrier(8)
    lock = threading.Lock()

    def attempt(index: int) -> None:
        barrier.wait()
        try:
            store.create(_document(run_id=index))
        except ClaimConflict:
            with lock:
                losers.append(index)
        else:
            with lock:
                winners.append(index)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(winners) == 1
    assert len(losers) == 7
    assert store.read(AUTH)["claimant_run_id"] == str(winners[0])


def test_d_7_2_a_second_consumption_id_cannot_reuse_the_authorization() -> None:
    store = InMemoryClaimStore()
    store.create(_document())
    try:
        store.create(claim_document(
            authorization_id=AUTH, tip_sha="e" * 40, failure_run_id=100,
            projection_digest="f" * 64, claimant_run_id="8",
            claimed_at="2026-11-12T01:00:00Z",
        ))
    except ClaimConflict:
        pass
    else:  # pragma: no cover
        raise AssertionError("a consumed authorization must not be reusable")


def test_verify_claim_rejects_a_replaced_record() -> None:
    expected = _document()
    stored = dict(expected)
    stored["projection_digest"] = "9" * 64
    ok, reason = verify_claim(stored, expected)
    assert not ok
    assert reason == "CLAIM_FIELD_MISMATCH:projection_digest"


def test_verify_claim_requires_the_ref_to_exist() -> None:
    ok, reason = verify_claim(None, _document())
    assert not ok
    assert reason == "CLAIM_REF_MISSING"


def test_verify_claim_accepts_the_exact_record() -> None:
    document = _document()
    assert verify_claim(dict(document), document) == (True, "")


def _recovery_authorization(tip: str = TIP, failure_run_id: int = 99) -> Authorization:
    return Authorization(
        path=f".fpf/ledger-authorizations/{AUTH}.yaml",
        body={"kind": "LEDGER_RECOVERY", "tip_sha": tip,
              "failure_check_run_id": failure_run_id},
        authorization_id=AUTH,
    )


def _failure(run_id: int = 99, conclusion: str = "failure", head: str = TIP) -> dict:
    return {"id": run_id, "conclusion": conclusion, "head_sha": head}


def _verified() -> Verdict:
    return Verdict("VERIFIED", "AUTHORIZATION_VERIFIED", {})


def test_verified_claim_requires_derived_facts_to_agree() -> None:
    ok, reason = verify_recovery_claim(
        verdict=_verified(),
        authorization=_recovery_authorization(),
        tip_sha=TIP,
        failure_run_id=99,
        projection_digest=DIGEST,
        replay_digest=DIGEST,
        failure_facts=_failure(),
    )
    assert (ok, reason) == (True, "")


def test_claim_refuses_when_authorization_verdict_is_blocked() -> None:
    ok, reason = verify_recovery_claim(
        verdict=Verdict("BLOCKED", "AUTHORIZATION_UNVERIFIABLE", {}),
        authorization=_recovery_authorization(),
        tip_sha=TIP, failure_run_id=99, projection_digest=DIGEST,
        replay_digest=DIGEST, failure_facts=_failure(),
    )
    assert not ok
    assert reason == "AUTHORIZATION_UNVERIFIABLE"


def test_claim_refuses_a_failure_run_that_did_not_fail() -> None:
    ok, reason = verify_recovery_claim(
        verdict=_verified(),
        authorization=_recovery_authorization(),
        tip_sha=TIP, failure_run_id=99, projection_digest=DIGEST,
        replay_digest=DIGEST, failure_facts=_failure(conclusion="success"),
    )
    assert not ok
    assert reason == "FAILURE_RUN_NOT_FAILED"


def test_claim_refuses_projection_that_the_job_cannot_reproduce() -> None:
    ok, reason = verify_recovery_claim(
        verdict=_verified(),
        authorization=_recovery_authorization(),
        tip_sha=TIP, failure_run_id=99, projection_digest=DIGEST,
        replay_digest="d" * 64, failure_facts=_failure(),
    )
    assert not ok
    assert reason == "PROJECTION_DIGEST_MISMATCH"


def test_claim_refuses_authorization_for_another_tip() -> None:
    ok, reason = verify_recovery_claim(
        verdict=_verified(),
        authorization=_recovery_authorization(tip="e" * 40),
        tip_sha=TIP, failure_run_id=99, projection_digest=DIGEST,
        replay_digest=DIGEST, failure_facts=_failure(),
    )
    assert not ok
    assert reason == "AUTHORIZATION_TIP_MISMATCH"


def test_facts_client_requires_a_token() -> None:
    try:
        GitHubFactsClient(repo="owner/name", token="")
    except GitHubFactsError as exc:
        assert "token" in str(exc)
    else:
        raise AssertionError("a tokenless client must not be constructed")


def test_facts_client_maps_station_carriers() -> None:
    text = (
        "version: 1\n"
        "stations:\n"
        "  - id: ST-QA\n"
        "    kind: qa-evidence\n"
        "    carriers:\n"
        "      - {type: github-login, value: 'Bot-Reviewer[bot]'}\n"
    )
    client = GitHubFactsClient(repo="owner/name", token="t")
    client._get = lambda path: {
        "encoding": "base64",
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }
    assert client.stations("main") == {"bot-reviewer[bot]": "qa-evidence"}
