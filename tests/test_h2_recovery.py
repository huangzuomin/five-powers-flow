# -*- coding: utf-8 -*-
"""M3 four required cases: first init, sticky failure, authorized recovery,
audit PASS after recovery.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:  # the `validate` job's unittest discovery has no pytest; H2 runs via EVID-37
    import pytest
except ModuleNotFoundError:  # pragma: no cover
    import unittest

    raise unittest.SkipTest("pytest not installed; H2 contracts execute via QA EVID-37")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.fpf_coordinator.worktree import recovery  # noqa: E402


def test_first_initialization_requires_empty_history():
    ledger = recovery.initialize(recovery.Ledger(), True, "5b4bfa2")
    assert ledger.state == recovery.ACTIVE
    assert ledger.history == ["INIT@5b4bfa2"]


def test_initialization_refused_when_history_exists():
    ledger = recovery.Ledger(history=["GENESIS"])
    with pytest.raises(recovery.NotEmpty):
        recovery.initialize(ledger, True, "5b4bfa2")


def test_failure_is_sticky_and_blocks_reinit():
    ledger = recovery.fail(recovery.Ledger(state=recovery.ACTIVE), "tamper")
    assert ledger.state == recovery.FAILED
    with pytest.raises(recovery.StickyFailure):
        recovery.initialize(ledger, True, "5b4bfa2")
    with pytest.raises(recovery.NotEmpty):
        recovery.initialize(recovery.Ledger(history=["GENESIS"]), True, "x")


def test_recovery_requires_authorization_and_is_single_use():
    ledger = recovery.fail(recovery.Ledger(state=recovery.ACTIVE), "tamper")
    with pytest.raises(recovery.Unauthorized):
        recovery.recover(ledger, "", "5b4bfa2")
    ledger = recovery.recover(ledger, "AUTH-1", "5b4bfa2")
    assert ledger.state == recovery.RECOVERED
    with pytest.raises(recovery.Unauthorized):
        recovery.recover(recovery.fail(ledger, "again"), "AUTH-1", "5b4bfa2")


def test_audit_passes_after_recovery():
    ledger = recovery.recover(
        recovery.fail(recovery.Ledger(state=recovery.ACTIVE), "tamper"),
        "AUTH-1", "5b4bfa2")
    assert recovery.audit(ledger, "abc", "abc") == "AUDIT_PASS"
    assert ledger.state == recovery.ACTIVE


def test_audit_mismatch_flips_back_to_failed():
    ledger = recovery.initialize(recovery.Ledger(), True, "5b4bfa2")
    assert recovery.audit(ledger, "abc", "def") == "AUDIT_FAILED"
    assert ledger.state == recovery.FAILED


def test_state_survives_roundtrip(tmp_path):
    ledger = recovery.recover(
        recovery.fail(recovery.Ledger(state=recovery.ACTIVE), "tamper"),
        "AUTH-1", "5b4bfa2")
    path = tmp_path / "ledger.json"
    recovery.save(ledger, path)
    assert recovery.load(path).state == recovery.RECOVERED
