"""Reverse tests for the governed normative-standard route (FPF2-GOV-DOC-PROFILE).

A normative standard document must never be adjudicated on the identity-only
route. These tests cover every way a change can reach the governed tree:
direct edit, rename out of it, rename into another directory, deletion, case
and extension variants, and the fail-closed paths of the profile binding.

Plain ``unittest`` on purpose: the ``validate`` workflow runs
``python -m unittest discover`` with no third-party test dependency installed.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from packages.fpf_coordinator import coordinator
from packages.fpf_policy import pr_gate


STANDARD = "docs/standards/FPF-STANDARD-2.0.md"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(root: Path) -> Path:
    repo = root / "repo"
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


def _card(tested_sha: str, base_sha: str, profile: str) -> dict:
    return {
        "result_version": 1,
        "kind": "QA_RESULT",
        "task_id": "FPF2-TEST-01",
        "tested_sha": tested_sha,
        "runner_sha": base_sha,
        "qa_contract_sha": base_sha,
        "environment": "unit",
        "author": "qa-bot[bot]",
        "verdict": "PASS",
        "profile": profile,
        "checks": [{"name": "EVID-01", "exit_code": 0}],
        "evidence_manifest_sha256": "a" * 64,
    }


def _dev(base: str, head: str) -> dict:
    return {
        "task_id": "FPF2-TEST-01",
        "author": "dev-user",
        "baseline_sha": base,
        "tested_code_sha": head,
    }


class GovernedRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_direct_standard_edit_is_promoted_to_gate_pr(self) -> None:
        self.assertEqual(pr_gate.promote_doc_route("POLICY_PR", [STANDARD]), "GATE_PR")

    def test_non_standard_prose_stays_identity_only(self) -> None:
        self.assertEqual(
            pr_gate.promote_doc_route("POLICY_PR", ["docs/coordination/lessons.md"]),
            "POLICY_PR",
        )

    def test_rename_out_of_governed_tree_is_promoted(self) -> None:
        repo = _init_repo(self.root)
        base = _git(repo, "rev-parse", "HEAD")
        _git(repo, "mv", STANDARD, "docs/FPF-STANDARD-2.0.md")
        _git(repo, "commit", "-q", "-m", "move out")
        head = _git(repo, "rev-parse", "HEAD")

        changed = _git(repo, "diff", "--name-only", f"{base}...{head}").splitlines()
        extra = pr_gate.touched_paths(base, head, repo_dir=str(repo)) - set(changed)

        self.assertEqual(changed, ["docs/FPF-STANDARD-2.0.md"])
        self.assertIn(STANDARD, extra)
        self.assertEqual(
            pr_gate.promote_doc_route("POLICY_PR", changed, extra), "GATE_PR"
        )

    def test_rename_into_map_files_is_still_promoted(self) -> None:
        """A standard renamed onto a MAP path must not ride the MAP_PR route."""
        self.assertEqual(
            pr_gate.promote_doc_route(
                "MAP_PR",
                ["docs/coordination/lessons.md"],
                {"docs/standards/FPF-STANDARD-2.0.md"},
            ),
            "GATE_PR",
        )

    def test_bootstrap_route_is_promoted(self) -> None:
        self.assertEqual(
            pr_gate.promote_doc_route(
                "BOOTSTRAP_PR", ["docs/standards/FPF-STANDARD-2.0.md"]
            ),
            "GATE_PR",
        )

    def test_non_markdown_extension_in_governed_tree_is_promoted(self) -> None:
        self.assertEqual(
            pr_gate.promote_doc_route(
                "POLICY_PR", ["docs/standards/FPF-STANDARD-2.0.markdown"]
            ),
            "GATE_PR",
        )

    def test_deletion_of_standard_is_promoted(self) -> None:
        repo = _init_repo(self.root)
        base = _git(repo, "rev-parse", "HEAD")
        (repo / STANDARD).unlink()
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "delete standard")
        head = _git(repo, "rev-parse", "HEAD")

        changed = _git(repo, "diff", "--name-only", f"{base}...{head}").splitlines()
        extra = pr_gate.touched_paths(base, head, repo_dir=str(repo)) - set(changed)

        self.assertIn(STANDARD, set(changed) | extra)
        self.assertEqual(
            pr_gate.promote_doc_route("POLICY_PR", changed, extra), "GATE_PR"
        )

    def test_qa_result_binding_rejects_generic_profile_for_standard_slice(self) -> None:
        repo = _init_repo(self.root)
        base = _git(repo, "rev-parse", "HEAD")
        (repo / STANDARD).write_text("# standard v2\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "edit standard")
        head = _git(repo, "rev-parse", "HEAD")

        generic_errors = coordinator.validate_qa_result(
            _card(head, base, "Library"), dev_data=_dev(base, head), repo_path=repo
        )
        self.assertTrue(
            any("DOC profile binding violated" in e for e in generic_errors)
        )

        doc_errors = coordinator.validate_qa_result(
            _card(head, base, "DOC"), dev_data=_dev(base, head), repo_path=repo
        )
        self.assertFalse(
            any("DOC profile binding violated" in e for e in doc_errors)
        )

    def test_binding_covers_non_markdown_extension(self) -> None:
        repo = _init_repo(self.root)
        base = _git(repo, "rev-parse", "HEAD")
        extra = repo / "docs" / "standards" / "FPF-STANDARD-2.0.markdown"
        extra.write_text("# standard\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add markdown-suffixed standard")
        head = _git(repo, "rev-parse", "HEAD")

        errors = coordinator.validate_qa_result(
            _card(head, base, "Library"), dev_data=_dev(base, head), repo_path=repo
        )
        self.assertTrue(any("DOC profile binding violated" in e for e in errors))

    def test_binding_fails_closed_when_change_set_is_unreadable(self) -> None:
        repo = _init_repo(self.root)
        base = _git(repo, "rev-parse", "HEAD")
        missing = "0" * 40

        errors = coordinator.validate_qa_result(
            _card(base, base, "Library"),
            dev_data=_dev(missing, base),
            repo_path=repo,
        )
        self.assertTrue(any("cannot be evaluated" in e for e in errors))

    def test_binding_uses_the_same_path_normalization_as_the_router(self) -> None:
        """A case variant must not be promoted by one side and skipped by the other.

        The variant is injected through the diff output rather than the
        filesystem: Windows and macOS checkouts are case-insensitive and cannot
        materialize both spellings, but git can still record either one.
        """
        repo = _init_repo(self.root)
        base = _git(repo, "rev-parse", "HEAD")
        head = base
        real_run_cmd = coordinator.run_cmd

        def fake_run_cmd(cmd, cwd=None, timeout=15):
            if len(cmd) > 1 and cmd[0] == "git" and cmd[1] == "diff":
                return 0, "M\tdocs/Standards/FPF-STANDARD-2.0.md\n", ""
            return real_run_cmd(cmd, cwd=cwd, timeout=timeout)

        with mock.patch.object(coordinator, "run_cmd", fake_run_cmd):
            base_route = pr_gate.classify(
                ["docs/Standards/FPF-STANDARD-2.0.md"], "POLICY_CHANGE", set(), ""
            )
            routed = pr_gate.promote_doc_route(
                base_route, ["docs/Standards/FPF-STANDARD-2.0.md"]
            )
            self.assertEqual(routed, "GATE_PR")

            errors = coordinator.validate_qa_result(
                _card(head, base, "Library"),
                dev_data=_dev(base, head),
                repo_path=repo,
            )
        self.assertTrue(any("DOC profile binding violated" in e for e in errors))

    def test_pass_without_repository_path_is_rejected(self) -> None:
        """No repository context means the change set cannot be computed: reject, never skip."""
        repo = _init_repo(self.root)
        base = _git(repo, "rev-parse", "HEAD")
        head = _git(repo, "rev-parse", "HEAD")

        errors = coordinator.validate_qa_result(
            _card(head, base, "Library"),
            dev_data=_dev(base, head),
            repo_path=None,
        )
        self.assertTrue(any("requires a repository path" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
