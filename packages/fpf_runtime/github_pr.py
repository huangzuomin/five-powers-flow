"""Opt-in GitHub draft PR publisher. No auto-merge, no deploy.

Uses an installed, authenticated gh CLI. The publisher refuses stale QA artifacts.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
import tempfile
import yaml
from .adapters import git
from .evidence import verify_qa_evidence
from packages.fpf_policy.protected import is_protected


class GhDraftPublisher:
    def __init__(self, base_branch: str = "main", executable: str = "gh",
                 remote: str = "origin"):
        if not re.fullmatch(r"[a-zA-Z0-9_./-]+", base_branch):
            raise ValueError("Invalid target branch")
        self.base_branch, self.executable, self.remote = base_branch, executable, remote

    def _gh(self, repo: Path, *args: str) -> str:
        p = subprocess.run([self.executable, *args], cwd=repo,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120, check=False)
        if p.returncode:
            raise RuntimeError("GitHub CLI failed: " + (p.stderr or p.stdout)[-900:])
        return p.stdout.strip()

    def publish(self, repo: Path, state: dict) -> str:
        sha = state.get("head_sha")
        if not sha or git(repo, "rev-parse", "HEAD") != sha:
            raise RuntimeError("Unverified/stale DEV head")
        if git(repo, "status", "--porcelain"):
            raise RuntimeError("DEV working tree is dirty")
        if not verify_qa_evidence(state.get("evidence_path", ""),
                                  state.get("evidence_sha256", ""), sha):
            raise RuntimeError("Missing, modified or stale local QA evidence")
        branch = git(repo, "branch", "--show-current")
        if not branch or branch in {"main", "master", self.base_branch}:
            raise RuntimeError("Protected/unknown branch cannot be published")
        baseline = state["base_sha"]
        if subprocess.run(["git", "merge-base", "--is-ancestor", baseline, sha],
                          cwd=repo, check=False).returncode:
            raise RuntimeError("Baseline is not an ancestor of tested head")
        files = git(repo, "diff", "--name-only", baseline + ".." + sha).splitlines()
        if not files or any(is_protected(p) for p in files):
            raise RuntimeError("No changes or protected governance files in Code PR")

        slug = json.loads(self._gh(repo, "repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
        found = json.loads(self._gh(repo, "pr", "list", "--state", "open",
                                    "--head", branch,
                                    "--json", "url,headRefOid,baseRefName,isDraft"))
        if len(found) > 1 or (found and
                             (not found[0]["isDraft"] or found[0]["baseRefName"] != self.base_branch)):
            raise RuntimeError("PR already exists in incompatible state")

        actor = self._gh(repo, "api", "user", "--jq", ".login").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", actor):
            raise RuntimeError("Could not authenticate GitHub PR author")
        card = {
            "handoff_version": 1, "kind": "DEV_HANDOFF", "task_id": state["id"],
            "baseline_sha": baseline, "tested_code_sha": sha, "author": actor,
            "pr_url": found[0]["url"] if found else
                      "https://github.com/" + slug + "/pull/0",
            "scope": state["goal"][:500], "changed_files": files,
            "dev_checks": [{"command": state.get("dev_check_command", "configured local DEV check"),
                            "exit_code": 0}],
            "not_run": ["Server-authenticated independent QA and deployment are not certified"],
            "known_risks": ["Local QA artifacts are provisional; final owner review required"],
            "state": "DEV_READY_FOR_QA",
        }

        def render_body() -> str:
            ticks = chr(96) * 3
            return (
                "## FPF unattended single-slice handoff\n\n"
                "DEV and provisional independent-worktree QA tested SHA " + sha + ".\n\n"
                "Local QA artifact manifest SHA256: " + state["evidence_sha256"] + ".\n\n"
                "**Not a GitHub authenticated independent QA PASS. No automatic merge.**\n\n"
                + ticks + "yaml\n" + yaml.safe_dump(card, sort_keys=False,
                    allow_unicode=True) + ticks + "\n"
            )

        with tempfile.TemporaryDirectory(prefix="fpf-pr-") as tmp:
            p = Path(tmp) / "pr-body.md"
            p.write_text(render_body(), encoding="utf-8")
            self._gh(repo, "auth", "status")
            # Never force-push; can update only the same feature branch.
            git(repo, "push", self.remote, branch)
            if found:
                url = found[0]["url"]
                if git(repo, "rev-parse", self.remote + "/" + branch) != sha:
                    raise RuntimeError("Remote branch SHA diverged after push")
            else:
                url = self._gh(repo, "pr", "create", "--draft", "--base",
                               self.base_branch, "--head", branch,
                               "--title", "feat(" + state["id"] + "): " + state["goal"][:65],
                               "--body-file", str(p)).splitlines()[-1].strip()
                if not url.startswith("https://github.com/" + slug + "/pull/"):
                    raise RuntimeError("Unexpected PR URL: " + url)
            card["pr_url"] = url
            p.write_text(render_body(), encoding="utf-8")
            self._gh(repo, "pr", "edit", url, "--body-file", str(p))
        return url
