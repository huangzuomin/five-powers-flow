"""Reverse tests for the governed normative-standard route (FPF2-GOV-DOC-PROFILE).

A normative standard document must never be adjudicated on the identity-only
(POLICY_PR) route. These tests cover the four ways a change can reach that tree:
direct edit, rename out of it, move to another directory, and deletion.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from packages.fpf_coordinator import coordinator
from packages.fpf_policy import pr_gate


STANDARD = "docs/standards/FPF-STANDARD-2.0.md"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "user.name", "qa")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "docs" / "standards").mkdir(parents=True)
    (repo / STANDARD).write_text("# standard\n", encoding="utf-8")
    (repo / "docs" / "coordination").mkdir(parents=True)
    (repo / "docs" / "coordination" / "lessons.md").write_text("# lessons\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def test_direct_standard_edit_is_promoted_to_gate_pr():
    assert pr_gate.promote_doc_route("POLICY_PR", [STANDARD]) == "GATE_PR"


def test_non_standard_prose_stays_identity_only():
    assert pr_gate.promote_doc_route(
        "POLICY_PR", ["docs/coordination/lessons.md"]
    ) == "POLICY_PR"


def test_rename_out_of_governed_tree_is_promoted(tmp_path):
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", STANDARD, "docs/FPF-STANDARD-2.0.md")
    _git(repo, "commit", "-q", "-m", "move out")
    head = _git(repo, "rev-parse", "HEAD")

    changed = _git(repo, "diff", "--name-only", f"{base}...{head}").splitlines()
    extra = pr_gate.touched_paths(base, head, repo_dir=str(repo)) - set(changed)

    assert changed == ["docs/FPF-STANDARD-2.0.md"]
    assert STANDARD in extra
    assert pr_gate.promote_doc_route("POLICY_PR", changed, extra) == "GATE_PR"


def test_deletion_of_standard_is_promoted(tmp_path):
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    (repo / STANDARD).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "delete standard")
    head = _git(repo, "rev-parse", "HEAD")

    changed = _git(repo, "diff", "--name-only", f"{base}...{head}").splitlines()
    extra = pr_gate.touched_paths(base, head, repo_dir=str(repo)) - set(changed)

    assert STANDARD in (set(changed) | extra)
    assert pr_gate.promote_doc_route("POLICY_PR", changed, extra) == "GATE_PR"


def test_qa_result_binding_rejects_generic_profile_for_standard_slice(tmp_path):
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    (repo / STANDARD).write_text("# standard v2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "edit standard")
    head = _git(repo, "rev-parse", "HEAD")

    dev = {
        "task_id": "FPF2-TEST-01",
        "author": "dev-user",
        "baseline_sha": base,
        "tested_code_sha": head,
    }

    def card(profile: str) -> dict:
        return {
            "result_version": 1,
            "kind": "QA_RESULT",
            "task_id": "FPF2-TEST-01",
            "tested_sha": head,
            "runner_sha": base,
            "qa_contract_sha": base,
            "environment": "unit",
            "author": "qa-bot[bot]",
            "verdict": "PASS",
            "profile": profile,
            "checks": [{"name": "EVID-01", "exit_code": 0}],
            "evidence_manifest_sha256": "a" * 64,
        }

    generic_errors = coordinator.validate_qa_result(
        card("Library"), dev_data=dev, repo_path=repo
    )
    assert any("DOC profile binding violated" in e for e in generic_errors)

    doc_errors = coordinator.validate_qa_result(
        card("DOC"), dev_data=dev, repo_path=repo
    )
    assert not any("DOC profile binding violated" in e for e in doc_errors)
