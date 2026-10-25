"""Deterministic single-slice DEV -> independent-worktree QA -> bounded rework.

Role decisions are advisory. Only fixed-head checks can advance the state.
The optional publisher can create a draft PR; it can never merge or deploy.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .adapters import commit_dev_changes, ensure_qa_worktree, git, run_command
from .evidence import write_qa_evidence
from .ledger import IN_FLIGHT, TERMINAL, Ledger


class SliceRuntime:
    def __init__(self, ledger: Ledger, roles: Any, codex: Any, dev_repo: Path,
                 qa_repo: Path, dev_check: list[str], qa_check: list[str],
                 timeout: int = 600, publisher: Any = None,
                 evidence_root: Path | None = None):
        dev, qa = dev_repo.resolve(), qa_repo.resolve()
        if (not dev_check or not qa_check or dev == qa or qa.is_relative_to(dev)
                or dev.is_relative_to(qa)):
            raise ValueError("Separate worktrees and verification commands required")
        self.ledger, self.roles, self.codex = ledger, roles, codex
        self.dev, self.qa = dev, qa
        self.dev_check, self.qa_check, self.timeout = dev_check, qa_check, timeout
        self.publisher = publisher
        self.evidence_root = (evidence_root or qa.parent / ".fpf-evidence").resolve()
        if self.evidence_root.is_relative_to(dev) or self.evidence_root.is_relative_to(qa):
            raise ValueError("Evidence directory must be outside both worktrees")
        branch = git(dev, "branch", "--show-current")
        if not branch or branch in ("main", "master"):
            raise ValueError("DEV requires a dedicated feature branch")

    def _ask(self, state: dict, role: str, prompt: str) -> str:
        answer = self.roles.ask(role, prompt, state["sessions"].get(role))
        if answer.response_id:
            state["sessions"][role] = answer.response_id
        if not answer.text.strip():
            raise RuntimeError(role + " returned an empty response")
        return answer.text

    def _failed(self, state: dict, detail: str) -> dict:
        state["last_failure"] = detail[-3500:]
        phase = "NEEDS_REWORK" if state["attempt"] < state["max_attempts"] else "BLOCKED"
        return self.ledger.save(state, phase, detail[-400:])

    def step(self, task_id: str) -> dict:
        state = self.ledger.read(task_id)
        if state is None:
            raise ValueError("Unknown task ID")
        phase = state["phase"]
        if phase in TERMINAL:
            return state
        if phase in IN_FLIGHT:
            return self.ledger.save(state, "BLOCKED_RECONCILIATION",
                                    "Interrupted external operation; inspect before resuming")
        try:
            if phase in ("NEW", "NEEDS_REWORK"):
                if state["attempt"] >= state["max_attempts"]:
                    return self.ledger.save(state, "BLOCKED", "Attempt limit reached")
                self.ledger.save(state, "PLAN_RUNNING", "Requesting DEV plan")
                state["dev_order"] = self._ask(
                    state, "DEV", "Task: " + state["goal"] + "\nBaseline: " +
                    state["base_sha"] + "\nPrevious QA failure: " +
                    state["last_failure"] + "\nReturn implementation steps and a test plan.")
                return self.ledger.save(state, "PLANNED", "DEV plan prepared")

            if phase == "PLANNED":
                expected = state["head_sha"] or state["base_sha"]
                if git(self.dev, "rev-parse", "HEAD") != expected:
                    return self.ledger.save(state, "BLOCKED", "DEV HEAD drift")
                if git(self.dev, "status", "--porcelain"):
                    return self.ledger.save(state, "BLOCKED", "Dirty DEV worktree")
                state["attempt"] += 1
                self.ledger.save(state, "DEV_RUNNING", "DEV attempt " + str(state["attempt"]))
                prompt = (
                    "You are working strictly inside this workspace. Do not search for missing tools; edit the requested files directly.\n"
                    "Implement exactly one bounded feature slice: " + state["goal"] +
                    "\nPlan: " + state["dev_order"] +
                    "\nPrior failures: " + state["last_failure"] +
                    "\nDO NOT push, merge, deploy, or modify project-map/lessons. "
                    "Only edit code; orchestrator handles commits. Never fabricate test results."
                )
                result = self.codex.run(self.dev, prompt, read_only=False)
                if result.code:
                    return self._failed(state, "DEV exited " + str(result.code) + ": " + result.output)
                head = commit_dev_changes(self.dev, expected, task_id, state["attempt"])
                if head == expected or git(self.dev, "status", "--porcelain"):
                    return self.ledger.save(state, "BLOCKED", "DEV produced no clean new commit")
                changed = git(self.dev, "diff", "--name-only", expected + ".." + head).splitlines()
                if not changed or any(Path(p).name.lower() in ("project-map.md", "lessons.md")
                                      for p in changed):
                    return self.ledger.save(state, "BLOCKED", "Protected path in DEV change")
                check = run_command(self.dev_check, self.dev, self.timeout)
                state["head_sha"] = head
                state["dev_check_command"] = " ".join(self.dev_check)
                if check.code:
                    return self._failed(state, "DEV check exit=" + str(check.code) +
                                        ": " + check.output)
                state["last_failure"] = ""
                return self.ledger.save(state, "DEV_READY", "DEV tested " + head)

            if phase == "DEV_READY":
                sha = state["head_sha"]
                self.ledger.save(state, "QA_RUNNING", "QA testing exact HEAD " + sha)
                state["qa_plan"] = self._ask(
                    state, "QA", "Independently review feature: " + state["goal"] +
                    "\nFixed SHA: " + sha +
                    "\nSpecify tests and adversarial edge cases; do not self-certify.")
                ensure_qa_worktree(self.dev, self.qa, sha)
                result = self.codex.run(
                    self.qa, "Audit commit " + sha + " for task: " + state["goal"] +
                    "\nQA plan: " + state["qa_plan"] +
                    "\nDo not write any files. Return strict JSON only, with the keys " +
                    'verdict ("PASS", "FAIL", or "BLOCKED") and findings (list of strings).',
                    read_only=True)
                if result.code:
                    return self._failed(state, "QA runner exit=" + str(result.code) +
                                        ": " + result.output)
                try:
                    raw_output = result.output.strip()
                    if "```" in raw_output:
                        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output)
                        if m:
                            raw_output = m.group(1).strip()
                    verdict = json.loads(raw_output)
                    if (not isinstance(verdict, dict)
                            or verdict.get("verdict") not in ("PASS", "FAIL", "BLOCKED")
                            or not isinstance(verdict.get("findings"), list)):
                        raise ValueError("Invalid QA verdict fields")
                except (ValueError, TypeError):
                    return self._failed(state, "QA did not emit valid verdict JSON")
                check = run_command(self.qa_check, self.qa, self.timeout)
                if git(self.qa, "rev-parse", "HEAD") != sha or git(self.qa, "status", "--porcelain"):
                    return self.ledger.save(state, "BLOCKED", "QA checkout mutated or drifted")
                evidence_path, evidence_sha = write_qa_evidence(
                    self.evidence_root, task_id, sha,
                    result.output, self.qa_check, check.code, check.output)
                state["evidence_path"] = evidence_path
                state["evidence_sha256"] = evidence_sha
                if check.code or verdict["verdict"] != "PASS":
                    return self._failed(
                        state, "QA verdict=" + verdict["verdict"] +
                        " check_exit=" + str(check.code) + " findings=" +
                        str(verdict["findings"]) + " check_log=" + check.output[-1200:])
                state["report"] = json.dumps(
                    {"task_id": task_id, "goal": state["goal"],
                     "base_sha": state["base_sha"], "tested_sha": sha,
                     "attempts": state["attempt"], "qa_check_exit": check.code,
                     "qa_findings": verdict["findings"],
                     "evidence_manifest": evidence_path,
                     "evidence_manifest_sha256": evidence_sha,
                     "qa_authority": "local-provisional",
                     "next": "READY_FOR_OWNER_REVIEW"},
                    indent=2, ensure_ascii=False)
                if self.publisher:
                    return self.ledger.save(state, "QA_PASSED_LOCAL",
                                            "Local provisional QA pass, draft PR pending")
                return self.ledger.save(state, "READY_FOR_OWNER_REVIEW",
                                        "Local QA passed; human review required")

            if phase == "QA_PASSED_LOCAL":
                if not self.publisher:
                    return self.ledger.save(state, "BLOCKED", "Publisher not configured")
                self.ledger.save(state, "PUBLISH_RUNNING", "Publishing draft PR")
                url = self.publisher.publish(self.dev, state)
                state["pr_url"] = url
                report = json.loads(state["report"])
                report["draft_pr_url"] = url
                state["report"] = json.dumps(report, indent=2, ensure_ascii=False)
                return self.ledger.save(state, "READY_FOR_OWNER_REVIEW",
                                        "Draft PR created, owner review required")

            raise RuntimeError("Unknown phase: " + phase)
        except Exception as exc:
            # Do not retry a call with unknown external effects.
            return self.ledger.save(state, "BLOCKED_RECONCILIATION",
                                    type(exc).__name__ + ": " + str(exc)[:300])

    def run(self, task_id: str, max_steps: int = 30) -> dict:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        for _ in range(max_steps):
            state = self.ledger.read(task_id)
            if not state or state["phase"] in TERMINAL:
                return state
            self.step(task_id)
        state = self.ledger.read(task_id)
        return self.ledger.save(state, "BLOCKED", "Orchestration step limit exceeded")
