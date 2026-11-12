"""G3 credential-boundary tests.

Everything planted here is assembled at runtime from fragments. Writing a
literal fake credential into a tracked file would make the scanner flag its own
test-suite, which is exactly the self-defeating behaviour this file guards
against.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "fpf_gates"))

import install_hooks  # noqa: E402
import secret_scan  # noqa: E402

AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
GITHUB_TOKEN = "ghp_" + "A" * 36
PEM_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"
ED_SEED = "a" * 64


class ScannerRulesTest(unittest.TestCase):
    def test_detects_aws_access_key(self) -> None:
        findings = secret_scan.scan_text("f.txt", f"id = '{AWS_KEY}'\n")
        self.assertEqual([f.rule_id for f in findings], ["AWS-ACCESS-KEY"])

    def test_detects_github_token(self) -> None:
        findings = secret_scan.scan_text("f.txt", f"token: {GITHUB_TOKEN}\n")
        self.assertEqual([f.rule_id for f in findings], ["GITHUB-TOKEN"])

    def test_detects_pem_private_key(self) -> None:
        findings = secret_scan.scan_text("f.pem", PEM_HEADER + "\nMIIE...\n")
        self.assertEqual([f.rule_id for f in findings], ["PEM-PRIVATE-KEY"])

    def test_detects_hex64_seed_next_to_key_wording(self) -> None:
        findings = secret_scan.scan_text("k.json", f'{{"private_key_hex": "{ED_SEED}"}}\n')
        self.assertEqual([f.rule_id for f in findings], ["HEX64-KEY-CONTEXT"])

    def test_plain_hash_without_key_wording_is_not_flagged(self) -> None:
        line = f'sha256 = "{ED_SEED}"\n'
        self.assertEqual(secret_scan.scan_text("f.txt", line), [])

    def test_vendor_placeholder_is_allowlisted(self) -> None:
        placeholder = "AKIA" + "IOSFODNN7EXAMPLE"
        self.assertEqual(secret_scan.scan_text("f.txt", placeholder + "\n"), [])

    def test_suppression_marker_requires_reason_on_the_same_line(self) -> None:
        suppressed = f"key = '{AWS_KEY}'  # fpf-secret-scan: allow vendor sample\n"
        self.assertEqual(secret_scan.scan_text("f.txt", suppressed), [])

    def test_marker_on_another_line_does_not_suppress(self) -> None:
        text = "# fpf-secret-scan: allow vendor sample\n" + f"key = '{AWS_KEY}'\n"
        self.assertEqual(len(secret_scan.scan_text("f.txt", text)), 1)


class RepositoryIsCleanTest(unittest.TestCase):
    def test_tracked_files_contain_no_secret_material(self) -> None:
        findings = secret_scan.scan_tracked()
        self.assertEqual(
            findings,
            [],
            "tracked files must stay free of secret material: "
            + ", ".join(f"{f.path}:{f.line}:{f.rule_id}" for f in findings),
        )

    def test_cli_exit_code_is_zero_on_clean_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "notes.md").write_text("nothing to see\n", encoding="utf-8")
            self.assertEqual(secret_scan.main(["--path", tmp]), 0)

    def test_cli_exit_code_is_one_when_tree_is_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "leak.txt").write_text(AWS_KEY + "\n", encoding="utf-8")
            self.assertEqual(secret_scan.main(["--path", tmp]), 1)


class HookBlocksCommitTest(unittest.TestCase):
    """The pre-commit hook must actually stop a staged secret."""

    def setUp(self) -> None:
        self.shell = shutil.which("sh") or shutil.which("bash")
        if not self.shell:
            self.skipTest("no POSIX shell available to execute the hook")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "qa@example.invalid")
        self._git("config", "user.name", "qa")
        gates = self.root / "packages" / "fpf_gates"
        gates.mkdir(parents=True)
        shutil.copy(
            REPO_ROOT / "packages" / "fpf_gates" / "secret_scan.py",
            gates / "secret_scan.py",
        )
        install_hooks.write_hook(self.root)
        self._git("config", "core.hooksPath", ".githooks")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True, check=False
        )

    def _run_hook(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.shell, ".githooks/pre-commit"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_hook_blocks_staged_secret(self) -> None:
        (self.root / "leak.txt").write_text(AWS_KEY + "\n", encoding="utf-8")
        self._git("add", "leak.txt")
        result = self._run_hook()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BLOCKED", result.stderr)

    def test_hook_allows_clean_index(self) -> None:
        (self.root / "notes.md").write_text("clean\n", encoding="utf-8")
        self._git("add", "notes.md")
        result = self._run_hook()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
