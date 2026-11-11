"""G2 reverse tests: the station registry constrains who may sign what.

Every assertion here is fail-closed: an identity that cannot be resolved to the
required station kind must block the merge, never pass silently.

Plain ``unittest`` on purpose — the ``validate`` workflow runs
``python -m unittest discover`` with no third-party test dependency installed.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from packages.fpf_policy import stations
from packages.fpf_policy.pr_gate import evaluate


VALID = """\
version: 1
stations:
  - id: ST-DEV
    kind: dev
    carriers:
      - {type: github-login, value: author-user}
      - {type: github-login, value: dev-two}
  - id: ST-QA
    kind: qa-evidence
    carriers:
      - {type: github-login, value: qa-bot}
  - id: ST-QA-2
    kind: qa-evidence
    carriers:
      - {type: github-login, value: qa-bot-2}
  - id: ST-RULE
    kind: ruling-carrier
    carriers:
      - {type: github-login, value: reviewer-two}
"""

CHANGED = ["packages/fpf_policy/pr_gate.py"]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo_with_registry(root: Path, registry: str | None = VALID) -> tuple[Path, str]:
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "user.name", "qa")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    if registry is not None:
        (repo / ".fpf").mkdir(exist_ok=True)
        (repo / stations.REGISTRY_PATH).write_text(registry, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


class RegistryParsingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_valid_registry_parses(self) -> None:
        registry = stations.parse(VALID)
        station = registry.require("qa-bot", {"qa-evidence"}, "QA signer")
        self.assertEqual(station.id, "ST-QA")
        self.assertIsNone(registry.resolve("nobody"))

    def test_missing_registry_fails_closed(self) -> None:
        repo, base = _repo_with_registry(self.root, registry=None)
        with self.assertRaises(ValueError) as ctx:
            stations.load_registry(repo, base)
        self.assertIn("missing on base", str(ctx.exception))

    def test_duplicate_station_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            stations.parse(VALID.replace("id: ST-RULE", "id: ST-QA"))
        self.assertIn("duplicate station id", str(ctx.exception))

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            stations.parse("version: 1\nversion: 1\nstations: []\n")
        self.assertIn("duplicate key", str(ctx.exception))

    def test_empty_carriers_is_rejected(self) -> None:
        text = VALID.replace(
            "    carriers:\n      - {type: github-login, value: reviewer-two}\n",
            "    carriers: []\n",
        )
        with self.assertRaises(ValueError) as ctx:
            stations.parse(text)
        self.assertIn("non-empty 'carriers'", str(ctx.exception))

    def test_empty_carrier_value_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            stations.parse(VALID.replace("value: reviewer-two", 'value: "  "'))
        self.assertIn("empty 'value'", str(ctx.exception))

    def test_unknown_kind_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            stations.parse(VALID.replace("kind: dev", "kind: root"))
        self.assertIn("unknown kind", str(ctx.exception))

    def test_version_must_be_one(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            stations.parse(VALID.replace("version: 1", "version: 2"))
        self.assertIn("version must be 1", str(ctx.exception))

    def test_carrier_duplicate_is_case_insensitive_across_stations(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            stations.parse(VALID.replace("value: reviewer-two", "value: QA-BOT"))
        self.assertIn("registered more than once", str(ctx.exception))

    def test_carrier_duplicate_within_one_station_is_rejected(self) -> None:
        text = VALID.replace(
            "      - {type: github-login, value: qa-bot}\n",
            "      - {type: github-login, value: qa-bot}\n"
            "      - {type: github-login, value: QA-BOT}\n",
        )
        with self.assertRaises(ValueError) as ctx:
            stations.parse(text)
        self.assertIn("registered more than once", str(ctx.exception))


class GateStationEnforcementTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo, self.sha = _repo_with_registry(self.root)
        self._env = {
            "GITHUB_REPOSITORY": "org/repo",
            "FPF_CANDIDATE_REPO": str(self.repo),
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _event(self, author: str = "author-user", body_extra: str = "") -> dict:
        return {
            "pull_request": {
                "head": {"sha": self.sha, "ref": "feat/policy-change"},
                "base": {"sha": self.sha},
                "user": {"login": author},
                "body": (
                    "```yaml\n"
                    "kind: POLICY_CHANGE\n"
                    "task_id: TASK-G2\n"
                    "risk_acknowledged: true\n"
                    f"{body_extra}"
                    f"baseline_sha: {self.sha}\n"
                    f"tested_code_sha: {self.sha}\n"
                    "changed_files:\n"
                    "  - packages/fpf_policy/pr_gate.py\n"
                    "```"
                ),
            }
        }

    def _qa_review(self, login: str) -> dict:
        return {
            "user": {"login": login},
            "state": "APPROVED",
            "commit_id": self.sha,
            "body": (
                "```yaml\n"
                "kind: QA_RESULT\n"
                "task_id: TASK-G2\n"
                f"tested_sha: {self.sha}\n"
                "verdict: PASS\n"
                f"author: {login}\n"
                "```"
            ),
        }

    def _approval(self, login: str) -> dict:
        return {
            "user": {"login": login},
            "state": "APPROVED",
            "commit_id": self.sha,
            "body": "approved",
        }

    def _run(self, event: dict, reviews: list[dict]) -> str:
        with patch.dict(os.environ, self._env), patch(
            "packages.fpf_policy.qa_artifact.independent_qa_evidence"
        ) as evidence, patch(
            "packages.fpf_coordinator.coordinator.validate_qa_result"
        ) as validate:
            evidence.return_value.__enter__.return_value = self.repo
            validate.return_value = []
            return evaluate(event, reviews, CHANGED, set(CHANGED))

    def test_unregistered_qa_signer_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._run(self._event(), [self._qa_review("stranger")])
        self.assertIn("not a registered station", str(ctx.exception))

    def test_qa_signer_registered_as_dev_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._run(self._event(), [self._qa_review("dev-two")])
        self.assertIn("is registered as 'dev'", str(ctx.exception))

    def test_author_registered_as_qa_station_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._run(self._event(author="qa-bot"), [self._qa_review("qa-bot-2")])
        self.assertIn("is a QA station", str(ctx.exception))

    def test_second_approval_unregistered_is_rejected(self) -> None:
        reviews = [self._qa_review("qa-bot"), self._approval("stranger")]
        with self.assertRaises(ValueError) as ctx:
            self._run(self._event(), reviews)
        self.assertIn("second approval", str(ctx.exception))

    def test_second_approval_registered_as_qa_evidence_is_rejected(self) -> None:
        reviews = [self._qa_review("qa-bot"), self._approval("qa-bot-2")]
        with self.assertRaises(ValueError) as ctx:
            self._run(self._event(), reviews)
        self.assertIn("is registered as 'qa-evidence'", str(ctx.exception))

    def test_same_login_cannot_be_both_qa_signer_and_second_approval(self) -> None:
        reviews = [self._qa_review("qa-bot"), self._approval("qa-bot")]
        with self.assertRaises(ValueError) as ctx:
            self._run(self._event(), reviews)
        # Either the QA review is shadowed by the later approval from the same
        # login, or the second-approval filter excludes it. Both are a refusal.
        message = str(ctx.exception)
        self.assertTrue(
            "QA_RESULT" in message or "second independent" in message, message
        )

    def test_sovereign_override_present_is_rejected_even_when_dual_approved(self) -> None:
        for literal in ("true", "false", "null", '""'):
            with self.subTest(value=literal):
                reviews = [self._qa_review("qa-bot"), self._approval("reviewer-two")]
                with self.assertRaises(ValueError) as ctx:
                    self._run(
                        self._event(body_extra=f"sovereign_override: {literal}\n"),
                        reviews,
                    )
                self.assertIn("no longer a substitute", str(ctx.exception))

    def test_head_registry_tampering_does_not_grant_authority(self) -> None:
        tampered = VALID.replace("value: qa-bot", "value: stranger")
        (self.repo / stations.REGISTRY_PATH).write_text(tampered, encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._run(self._event(), [self._qa_review("stranger")])
        self.assertIn("not a registered station", str(ctx.exception))

    def test_valid_station_triple_passes(self) -> None:
        reviews = [self._qa_review("qa-bot"), self._approval("reviewer-two")]
        self.assertIn("dual-approved", self._run(self._event(), reviews))


if __name__ == "__main__":
    unittest.main()
