# -*- coding: utf-8 -*-
"""Ledger initialization and recovery state machine (M3).

Three facts must stay distinguishable by machine, because the operator action
differs for each: a first-ever initialization, a genuine tamper, and the
residue of an earlier failed attempt.  Failure is sticky: a failed ledger is
never silently re-initialized.  Recovery is a single-use, authorization-bound
transition, and the audit must pass again afterwards.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

INIT = "INIT"
ACTIVE = "ACTIVE"
FAILED = "FAILED"
RECOVERED = "RECOVERED"


class RecoveryError(RuntimeError):
    pass


class NotEmpty(RecoveryError):
    """Initialization refused: the ledger already has history."""


class StickyFailure(RecoveryError):
    """A failed ledger cannot be re-initialized; it needs recovery."""


class Unauthorized(RecoveryError):
    """Recovery needs an authorization that has not been consumed."""


@dataclass
class Ledger:
    state: str = INIT
    authorization_id: str | None = None
    consumed: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)


def initialize(ledger: Ledger, history_empty: bool,
               baseline_sha: str) -> Ledger:
    if ledger.state == FAILED:
        raise StickyFailure("ledger is in FAILED; use recover()")
    if not history_empty or ledger.history:
        raise NotEmpty("refusing INIT over existing history")
    ledger.state = ACTIVE
    ledger.history.append(f"INIT@{baseline_sha}")
    return ledger


def fail(ledger: Ledger, reason: str) -> Ledger:
    ledger.state = FAILED
    ledger.history.append(f"FAILED:{reason}")
    return ledger


def recover(ledger: Ledger, authorization_id: str,
            baseline_sha: str) -> Ledger:
    if ledger.state != FAILED:
        raise RecoveryError("only a FAILED ledger can be recovered")
    if not authorization_id:
        raise Unauthorized("recovery requires an authorization id")
    if authorization_id in ledger.consumed:
        raise Unauthorized("authorization already consumed")
    ledger.consumed.append(authorization_id)
    ledger.authorization_id = authorization_id
    ledger.state = RECOVERED
    ledger.history.append(f"RECOVER@{baseline_sha}#{authorization_id}")
    return ledger


def audit(ledger: Ledger, expected_sha: str, actual_sha: str) -> str:
    if ledger.state not in (ACTIVE, RECOVERED):
        raise RecoveryError(f"audit not allowed in state {ledger.state}")
    if expected_sha != actual_sha:
        ledger.state = FAILED
        ledger.history.append("AUDIT_FAILED")
        return "AUDIT_FAILED"
    ledger.state = ACTIVE
    ledger.history.append("AUDIT_PASS")
    return "AUDIT_PASS"


def save(ledger: Ledger, path: os.PathLike[str] | str) -> None:
    Path(path).write_text(
        json.dumps(ledger.__dict__, sort_keys=True, indent=2), encoding="utf-8")


def load(path: os.PathLike[str] | str) -> Ledger:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Ledger(**data)
