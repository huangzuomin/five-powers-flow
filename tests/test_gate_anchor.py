"""The gate's requirement table must come from base, never from the PR head.

A PR used to be able to edit ``REQUIRED_PROFILE_EVIDENCES`` in
``packages/fpf_coordinator/coordinator.py`` and have the gate read the edited
table, because only ``packages/fpf_policy/`` was restored from base. That is two
defects in one: a PR could *raise* its own bar (and then be unable to satisfy it,
which is what deadlocked EVID-35/36) or *lower* it (weakening its own gate).

These tests pin the anchor step itself: base bytes must win for both packages.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "validate-handoff-cards.yml"
ANCHORED = ("packages/fpf_policy/", "packages/fpf_coordinator/")


def _coordinator(evids: tuple[str, ...]) -> str:
    body = ", ".join(f'"{e}"' for e in evids)
    return textwrap.dedent(
        f'''\
        """Synthetic stand-in for the real coordinator table."""

        REQUIRED_PROFILE_EVIDENCES = {{"Library": frozenset({{{body}}})}}
        '''
    )


def _write_tree(root: Path, evids: tuple[str, ...]) -> None:
    package = root / "packages" / "fpf_coordinator"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "coordinator.py").write_text(_coordinator(evids), encoding="utf-8")
    policy = root / "packages" / "fpf_policy"
    policy.mkdir(parents=True, exist_ok=True)
    (policy / "__init__.py").write_text("", encoding="utf-8")
    (policy / "pr_gate.py").write_text('"""Synthetic gate stand-in."""\n', encoding="utf-8")


def _anchor(head: Path, base: Path, paths=ANCHORED) -> None:
    """Mirror ``git checkout <base> -- <paths>``: base bytes overwrite head."""
    for relative in paths:
        source, target = base / relative, head / relative
        if not source.is_dir():
            raise AssertionError(f"base lacks {relative}")
        shutil.copytree(source, target, dirs_exist_ok=True)


def _effective_library(root: Path) -> tuple[str, ...]:
    script = (
        "from packages.fpf_coordinator import coordinator as c;"
        "print(' '.join(sorted(c.REQUIRED_PROFILE_EVIDENCES['Library'])))"
    )
    out = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root, capture_output=True, text=True, check=True,
        env={**os.environ, "PYTHONPATH": str(root)},
    ).stdout.split()
    return tuple(out)


class GateAnchorTests(unittest.TestCase):
    def test_workflow_restores_both_gate_packages_from_base(self) -> None:
        document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = document["jobs"]["validate-card"]["steps"]
        restore = [s for s in steps if s.get("name") == "Restore trusted policy gate from base"]
        self.assertEqual(len(restore), 1, "anchor step must exist exactly once")
        run = restore[0]["run"]
        self.assertIn("github.event.pull_request.base.sha", run)
        for relative in ANCHORED:
            self.assertIn(relative, run, f"{relative} must be restored from base")
        self.assertIn("git checkout", run)

    def test_head_shrinking_the_table_cannot_lower_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = Path(tmp) / "base", Path(tmp) / "head"
            _write_tree(base, ("EVID-01", "EVID-02"))
            _write_tree(head, ("EVID-01",))
            # Before the anchor the candidate really did dictate its own bar.
            self.assertEqual(_effective_library(head), ("EVID-01",))
            _anchor(head, base)
            # After the anchor base wins: the deletion has no effect on this PR.
            self.assertEqual(_effective_library(head), ("EVID-01", "EVID-02"))

    def test_head_expanding_the_table_does_not_apply_to_this_pr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = Path(tmp) / "base", Path(tmp) / "head"
            _write_tree(base, ("EVID-01", "EVID-02"))
            _write_tree(head, ("EVID-01", "EVID-02", "EVID-35"))
            self.assertEqual(_effective_library(head), ("EVID-01", "EVID-02", "EVID-35"))
            _anchor(head, base)
            self.assertEqual(_effective_library(head), ("EVID-01", "EVID-02"))

    def test_anchor_is_byte_identical_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = Path(tmp) / "base", Path(tmp) / "head"
            _write_tree(base, ("EVID-01", "EVID-02"))
            _write_tree(head, ("EVID-09",))
            _anchor(head, base)
            once = hashlib.sha256(
                (head / "packages/fpf_coordinator/coordinator.py").read_bytes()
            ).hexdigest()
            _anchor(head, base)
            twice = hashlib.sha256(
                (head / "packages/fpf_coordinator/coordinator.py").read_bytes()
            ).hexdigest()
            expected = hashlib.sha256(
                (base / "packages/fpf_coordinator/coordinator.py").read_bytes()
            ).hexdigest()
            self.assertEqual(once, expected)
            self.assertEqual(twice, expected)

    def test_base_without_coordinator_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base, head = Path(tmp) / "base", Path(tmp) / "head"
            _write_tree(head, ("EVID-01",))
            (base / "packages" / "fpf_policy").mkdir(parents=True)
            with self.assertRaises(AssertionError):
                _anchor(head, base)


if __name__ == "__main__":
    unittest.main()
