"""Hermetic project bootstrap tests. No network, API key, or user repository mutations."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml
from unittest.mock import patch
from packages.fpf_bootstrap.artifacts import bundle, map_text
from packages.fpf_bootstrap.bootstrap import apply, doctor, layout, plan
from packages.fpf_bootstrap.discovery import git


def cmd(path: Path, *args: str):
    p = subprocess.run(args, cwd=path, capture_output=True, text=True, check=False)
    if p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout.strip()


class TestProjectBootstrap(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fpf-bootstrap-test-")
        root = Path(self.temp.name)
        self.repo, self.workspace = root / "source", root / "fpf-workspaces"
        self.repo.mkdir()
        cmd(self.repo, "git", "init", "-b", "main")
        cmd(self.repo, "git", "config", "user.name", "FPF Tester")
        cmd(self.repo, "git", "config", "user.email", "fpf@example.invalid")
        (self.repo / "README.md").write_text("# Real Requirements\n\n## Proposed Architecture\n", encoding="utf-8")
        docs = self.repo / "docs"
        docs.mkdir()
        (docs / "spec.md").write_text("# Goal\n\n## Future Milestones\n", encoding="utf-8")
        (self.repo / "app.py").write_text("print('hello')\n", encoding="utf-8")
        cmd(self.repo, "git", "add", ".")
        cmd(self.repo, "git", "commit", "-m", "baseline")
        self.sha = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self):
        self.temp.cleanup()

    def proposal(self, mode="api"):
        return plan(self.repo, self.workspace, "DEMO01", "Demo Application", mode)

    def test_plan_is_read_only_and_evidence_not_fabricated(self):
        out = self.proposal()
        self.assertEqual(out["discovery"]["sha"], self.sha)
        self.assertEqual(out["status"], "BOOTSTRAP_PLAN")
        self.assertFalse(self.workspace.exists())
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        m = out["files"]["docs/coordination/PROJECT-MAP.md"]
        self.assertIn("README.md", m)
        self.assertIn("docs/spec.md", m)
        self.assertIn("PROPOSED", m)
        self.assertIn("NOT_RUN", m)
        self.assertNotIn("QA_PASS", m.split("## 4.")[1].split("## 5.")[0])
        self.assertEqual(yaml.safe_load(out["files"][".fpf/project.yaml"])["slice_authorized"], False)

    def test_apply_creates_three_worktrees_without_main_changes(self):
        p = self.proposal()
        state = apply(self.repo, p)
        self.assertEqual(state["bootstrap_state"], "BOOTSTRAP_REVIEW")
        self.assertFalse(state["slice_authorized"])
        for name in ("bootstrap", "dev", "qa"):
            worktree = Path(state["paths"][name])
            self.assertTrue(worktree.is_dir())
            self.assertEqual(git(worktree, "rev-parse", "HEAD"), self.sha)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(Path(state["paths"]["qa"]), "branch", "--show-current"), "")
        self.assertTrue((Path(state["paths"]["bootstrap"]) / ".fpf/agents.yaml").exists())
        root=Path(state["paths"]["bootstrap"])
        self.assertTrue((root / ".fpf/vendor/packages/fpf_policy/qa_artifact.py").exists())
        self.assertTrue((root / ".fpf/vendor/packages/fpf_policy/qa_collector.py").exists())
        self.assertTrue((root / ".github/workflows/fpf-independent-qa.yml").exists())
        runner=(root / ".github/workflows/fpf-independent-qa.yml").read_text()
        self.assertIn("trusted/.fpf/vendor",runner)

    def test_rerun_is_idempotent_and_preserves_artifacts(self):
        proposal = self.proposal()
        a = apply(self.repo, proposal)
        b = apply(self.repo, proposal)
        self.assertEqual(a, b)
        self.assertEqual(len([x for x in git(self.repo, "worktree", "list", "--porcelain").splitlines()
                              if x.startswith("worktree ")]), 4)

    def test_existing_changes_are_never_overwritten(self):
        proposal = self.proposal()
        state = apply(self.repo, proposal)
        path = Path(state["paths"]["bootstrap"]) / "AGENTS.md"
        path.write_text("MANUAL CHANGE", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "will not overwrite"):
            apply(self.repo, proposal)
        self.assertEqual(path.read_text(encoding="utf-8"), "MANUAL CHANGE")

    def test_existing_governance_in_base_causes_refusal(self):
        (self.repo / "AGENTS.md").write_text("Existing constitution", encoding="utf-8")
        cmd(self.repo, "git", "add", "AGENTS.md")
        cmd(self.repo, "git", "commit", "-m", "governance exists")
        with self.assertRaisesRegex(RuntimeError, "governance files"):
            self.proposal()

    def test_doctor_does_not_claim_project_ready_before_approval(self):
        apply(self.repo, self.proposal())
        report = doctor(self.repo, self.workspace, "DEMO01")
        self.assertEqual(report["state"], "BOOTSTRAP_PARTIAL")
        self.assertFalse(report["ok"])
        self.assertTrue(any("approved" in issue for issue in report["issues"]))
        self.assertTrue(any("NOT been provisioned" in issue for issue in report["issues"]))

    def test_manual_mode_creates_prompts_but_not_chatgpt_threads(self):
        state = apply(self.repo, self.proposal("manual"))
        boot = Path(state["paths"]["bootstrap"])
        text = (boot / ".fpf/CHATGPT-SETUP.md").read_text(encoding="utf-8")
        self.assertIn("cannot create ChatGPT", text)
        agents = yaml.safe_load((boot / ".fpf/agents.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(agents["roles"]), 4)
        self.assertTrue(all(a["session_id"] is None for a in agents["roles"]))

    def test_reject_workspace_nested_inside_repo(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            plan(self.repo, self.repo / "workspace", "DEMO01", "Demo", "api")

    def test_reject_other_repo_occupying_worktree_path(self):
        p = self.proposal()
        directory = Path(p["paths"]["bootstrap"])
        directory.mkdir(parents=True)
        cmd(directory, "git", "init")
        with self.assertRaises(RuntimeError):
            apply(self.repo, p)

    def test_doctor_check_only_can_succeed_without_claiming_approval(self):
        apply(self.repo, self.proposal())
        status = doctor(self.repo, self.workspace, "DEMO01", require_ready=False)
        self.assertTrue(status["ok"])
        self.assertEqual(status["state"], "BOOTSTRAP_REVIEW")
        self.assertTrue(status["requires_approval"])

    def test_partial_initialize_has_persistent_pending_record_and_safe_rollback(self):
        from packages.fpf_bootstrap import bootstrap
        proposal = self.proposal()
        real_ensure = bootstrap._ensure_worktree
        calls = [0]
        def interrupted(repo, directory, branch, sha):
            calls[0] += 1
            if calls[0] == 3:
                raise RuntimeError("QA disk unavailable")
            return real_ensure(repo, directory, branch, sha)
        with patch.object(bootstrap, "_ensure_worktree", side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError, "disk unavailable"):
                apply(self.repo, proposal)
        state = Path(proposal["paths"]["state"])
        self.assertEqual(json.loads(state.read_text())["bootstrap_state"], "PENDING")
        self.assertFalse(doctor(self.repo, self.workspace, "DEMO01", require_ready=False)["ok"])
        self.assertEqual(bootstrap.rollback(self.repo, self.workspace, "DEMO01")["rollback"], "COMPLETE")
        self.assertFalse(state.exists())
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")

    def test_invalid_project_id_refused(self):
        with self.assertRaises(ValueError):
            plan(self.repo, self.workspace, "../escape", "Oops", "api")


if __name__ == "__main__":
    unittest.main()
