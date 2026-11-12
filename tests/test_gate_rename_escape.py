# -*- coding: utf-8 -*-
"""A-01 / A-02: a rename source inside a protected tree cannot escape gating."""
from __future__ import annotations

import pytest

from packages.fpf_policy import pr_gate


AUTH_ID = "a" * 64
AUTH_PATH = f".fpf/ledger-authorizations/{AUTH_ID}.yaml"


def _legacy_promote(pr_type: str, files, extra_paths=None) -> str:
    """The pre-fix function, kept only as the A-5.0 negative baseline."""
    if pr_type in ("GATE_PR", "CODE_PR"):
        return pr_type
    touched = {pr_gate.normalize_repo_path(p) for p in files}
    touched |= {pr_gate.normalize_repo_path(p) for p in (extra_paths or set())}
    if any(pr_gate.is_normative_standard(p) for p in touched):
        return "GATE_PR"
    return pr_type


def test_a5_0_negative_baseline_reproduces_the_hole() -> None:
    assert _legacy_promote("CODE_PR", ["docs/x.md"], {AUTH_PATH}) == "CODE_PR"


def test_a5_1_code_pr_rename_out_is_refused() -> None:
    with pytest.raises(ValueError, match="re-submit as POLICY_CHANGE"):
        pr_gate.promote_doc_route("CODE_PR", ["docs/x.md"], {AUTH_PATH})


def test_a5_2_policy_change_rename_out_becomes_gate_pr() -> None:
    assert pr_gate.promote_doc_route("POLICY_PR", ["docs/x.md"], {AUTH_PATH}) == "GATE_PR"


def test_a5_3_map_pr_rename_out_is_refused() -> None:
    with pytest.raises(ValueError, match="re-submit as POLICY_CHANGE"):
        pr_gate.promote_doc_route(
            "MAP_PR", ["docs/coordination/project-map.md"], {AUTH_PATH},
        )


def test_a5_4_bootstrap_rename_out_is_refused() -> None:
    with pytest.raises(ValueError, match="re-submit as POLICY_CHANGE"):
        pr_gate.promote_doc_route("BOOTSTRAP_PR", [".fpf/project.yaml"], {AUTH_PATH})


def test_a5_5_normal_routes_are_unchanged() -> None:
    assert pr_gate.promote_doc_route(
        "CODE_PR", ["packages/fpf_coordinator/dispatch/reducer.py"], set(),
    ) == "CODE_PR"
    assert pr_gate.promote_doc_route(
        "MAP_PR", ["docs/coordination/project-map.md"], set(),
    ) == "MAP_PR"
    assert pr_gate.promote_doc_route(
        "BOOTSTRAP_PR", [".fpf/project.yaml"], set(),
    ) == "BOOTSTRAP_PR"


def test_a5_6_gate_pr_stays_gate_pr() -> None:
    assert pr_gate.promote_doc_route("GATE_PR", ["docs/x.md"], {AUTH_PATH}) == "GATE_PR"


def test_a5_7_rename_source_outside_protected_trees_is_ignored() -> None:
    assert pr_gate.promote_doc_route("CODE_PR", ["docs/new.md"], {"tests/old.py"}) == "CODE_PR"


def test_a5_8_rename_source_listed_in_files_only_does_not_raise() -> None:
    # `files` carries the destination; a protected *destination* already made
    # classify() return GATE_PR, so promote() must stay permissive here.
    assert pr_gate.promote_doc_route("CODE_PR", [AUTH_PATH], set()) == "CODE_PR"


def test_a5_9_error_names_the_offending_path() -> None:
    with pytest.raises(ValueError) as excinfo:
        pr_gate.promote_doc_route("CODE_PR", ["docs/x.md"], {AUTH_PATH})
    assert AUTH_PATH in str(excinfo.value)
