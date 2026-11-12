"""The pre-push hook must block DEV self-marking but let the Scribe through.

Blocking the sanctioned scribe route does not add safety: it pushes the scribe
into ``git push --no-verify``, which disables *every* hook check for that push.
These tests execute the tracked template for real inside a temporary repository.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "git-hooks" / "pre-push.template"
BASH = shutil.which("bash")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()


@unittest.skipIf(BASH is None, "bash is required to execute the hook")
class HookBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "qa@example.invalid")
        _git(self.repo, "config", "user.name", "QA")
        (self.repo / "docs" / "coordination").mkdir(parents=True)
        (self.repo / "docs" / "coordination" / "project-map.md").write_text("map\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "base")
        self.base = _git(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "update-ref", "refs/remotes/origin/main", self.base)
        # Run a copy inside the repo: Windows absolute paths are not bash paths.
        shutil.copyfile(TEMPLATE, self.repo / ".pre-push-under-test")
        (self.repo / "docs" / "coordination" / "project-map.md").write_text("map2\n", encoding="utf-8")
        _git(self.repo, "commit", "-qam", "scribe edit")
        self.head = _git(self.repo, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, branch: str) -> subprocess.CompletedProcess[str]:
        stdin = f"refs/heads/{branch} {self.head} refs/heads/{branch} {self.base}\n"
        return subprocess.run(
            [BASH, ".pre-push-under-test"], cwd=self.repo, input=stdin,
            capture_output=True, text=True,
        )

    def test_dev_branch_touching_the_map_is_blocked(self) -> None:
        result = self._run("fpf/g4-reducer-20261112")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("PRE-PUSH BLOCKED", result.stdout)

    def test_scribe_branch_touching_the_map_is_allowed(self) -> None:
        result = self._run("fpf/scribe-gov-20261112")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Scribe branch", result.stdout)

    def test_scribe_map_prefix_is_allowed(self) -> None:
        result = self._run("fpf/map-g4-closeout-20261112")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unprotected_change_passes_on_any_branch(self) -> None:
        # Restore the map first: the range is merge-base..HEAD, so an earlier
        # map edit would still be in scope and would (correctly) block.
        (self.repo / "docs" / "coordination" / "project-map.md").write_text("map\n", encoding="utf-8")
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "docs only")
        self.head = _git(self.repo, "rev-parse", "HEAD")
        result = self._run("fpf/g4-reducer-20261112")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TemplateContractTests(unittest.TestCase):
    def test_template_keeps_the_block_for_non_scribe_branches(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("PROTECTED_RE=", text)
        self.assertIn("PRE-PUSH BLOCKED", text)
        self.assertIn("exit 1", text)

    def test_template_declares_the_scribe_allowlist(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("SCRIBE_RE=", text)
        self.assertIn("fpf/(scribe|map)-", text)


if __name__ == "__main__":
    unittest.main()
