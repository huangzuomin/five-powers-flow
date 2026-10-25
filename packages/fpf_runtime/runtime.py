"""Unattended single feature slice: DEV -> isolated QA -> bounded DEV rework.

No GitHub merge, remote push, deployment or mutation of official project map.
The state machine, not a model verdict, controls transitions.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .adapters import commit_dev_changes, ensure_qa_worktree, git, run_command
from .ledger import IN_FLIGHT, TERMINAL, Ledger


class SliceRuntime:
    def __init__(self, ledger: Ledger, roles: Any, codex: Any, dev_repo: Path,
                 qa_repo: Path, dev_check: list[str], qa_check: list[str],
                 timeout: int = 600):
        if not dev_check or not qa_check or dev_repo.resolve() == qa_repo.resolve():
            raise ValueError("Distinct workspaces and both verification commands required")
        self.ledger, self.roles, self.codex = ledger, roles, codex
        self.dev, self.qa = dev_repo.resolve(), qa_repo.resolve()
        self.dev_check, self.qa_check, self.timeout = dev_check, qa_check, timeout
        branch = git(self.dev, "branch", "--show-current")
        if not branch or branch in {"main", "master"}:
            raise ValueError("DEV must run on a dedicated feature branch, not main/master")

    def _ask(self, state: dict, role: str, prompt: str) -> str:
        result = self.roles.ask(role, prompt, state["sessions"].get(role))
        if result.response_id:
            state["sessions"][role] = result.response_id
        if not result.text.strip():
            raise RuntimeError("Empty " + role + " response")
        return result.text

    def _failed(self, state: dict, detail: str) -> dict:
        state["last_failure"] = detail[:3000]
        next_phase = "NEEDS_REWORK" if state["attempt"] < state["max_attempts"] else "BLOCKED"
        return self.ledger.save(state, next_phase, detail[:400])

    def step(self, task_id: str) -> dict:
        state = self.ledger.read(task_id)
        if state is None:
            raise ValueError("Unknown task: " + task_id)
        phase = state["phase"]
        if phase in TERMINAL:
            return state
        if phase in IN_FLIGHT:
            return self.ledger.save(state, "BLOCKED_RECONCILIATION",
                                    "Interrupted in-flight operation; inspect external effects")
        try:
            if phase in ("NEW", "NEEDS_REWORK"):
                if state["attempt"] >= state["max_attempts"]:
                    return self.ledger.save(state, "BLOCKED", "Attempt limit exhausted")
                self.ledger.save(state, "PLAN_RUNNING", "Requesting DEV work order")
                order = self._ask(state, "DEV",
                                  "Task: " + state["goal"] + "\nBase: " + state["base_sha"] +
                                  "\nPrevious failure: " + state["last_failure"] +
                                  "\nReturn a concrete work order and tests.")
                state["dev_order"] = order
                return self.ledger.save(state, "PLANNED", "DEV work order ready")

            if phase == "PLANNED":
                expected = state["head_sha"] or state["base_sha"]
                if git(self.dev, "rev-parse", "HEAD") != expected:
                    return self.ledger.save(state, "BLOCKED", "DEV HEAD diverged")
                if git(self.dev, "status", "--porcelain"):
                    return self.ledger.save(state, "BLOCKED", "DEV workspace is dirty")
                state["attempt"] += 1
                self.ledger.save(state, "DEV_RUNNING", "DEV attempt " + str(state["attempt"]))
                prompt = ("You are working strictly inside this workspace. Do not search for missing tools; edit the requested files directly.\nImplement task: " + state["goal"] + "\nWork order: " +
                          state["dev_order"] + "\nFailure to repair: " + state["last_failure"] +
                          "\nDo not merge, deploy, push, or modify governance files. "
                          "Edit files but DO NOT commit: the orchestrator will create "
                          "the local commit. Report results accurately.")
                result = self.codex.run(self.dev, prompt, read_only=False)
                if result.code:
                    return self._failed(state, "DEV Codex exited " + str(result.code) +
                                        ": " + result.output[-1500:])
                current = commit_dev_changes(self.dev, expected, task_id, state["attempt"])
                if current == expected or git(self.dev, "status", "--porcelain"):
                    return self.ledger.save(state, "BLOCKED", "DEV did not deliver clean commit")
                changed = git(self.dev, "diff", "--name-only", expected + ".." + current).splitlines()
                if not changed or any(Path(p).name.lower() in
                                      {"project-map.md", "lessons.md"} for p in changed):
                    return self.ledger.save(state, "BLOCKED", "Protected file in DEV commit")
                check = run_command(self.dev_check, self.dev, self.timeout)
                state["head_sha"] = current
                if check.code:
                    return self._failed(state, "DEV check failed: " + check.output[-1800:])
                state["last_failure"] = ""
                return self.ledger.save(state, "DEV_READY", "DEV commit " + current)

            if phase == "DEV_READY":
                sha = state["head_sha"]
                self.ledger.save(state, "QA_RUNNING", "QA preparing " + sha)
                plan = self._ask(state, "QA",
                                 "Independently assess: " + state["goal"] +
                                 "\nVerify exact commit " + sha + ". Define adversarial tests.")
                state["qa_plan"] = plan
                ensure_qa_worktree(self.dev, self.qa, sha)
                result = self.codex.run(
                    self.qa,
                    "Review commit " + sha + " against task: " + state["goal"] +
                    "\nQA plan: " + plan +
                    "\nDo not alter files. Return ONLY strict JSON " +
                    '{"verdict":"PASS|FAIL|BLOCKED","findings":["..."]}.',
                    read_only=True)
                if result.code:
                    return self._failed(state, "QA Codex exited " + str(result.code) +
                                        ": " + result.output[-1200:])
                try:
                    raw_output = result.output.strip()
                    if "```" in raw_output:
                        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output)
                        if m:
                            raw_output = m.group(1).strip()
                    judgment = json.loads(raw_output)
                    verdict = judgment["verdict"]
                    if verdict not in ("PASS", "FAIL", "BLOCKED") or not isinstance(judgment["findings"], list):
                        raise ValueError("Unexpected QA fields")
                except (ValueError, KeyError, TypeError):
                    return self._failed(state, "QA model output not strict verdict JSON")
                check = run_command(self.qa_check, self.qa, self.timeout)
                if git(self.qa, "rev-parse", "HEAD") != sha or git(self.qa, "status", "--porcelain"):
                    return self.ledger.save(state, "BLOCKED", "QA modified immutable test worktree")
                if check.code or verdict != "PASS":
                    return self._failed(state, "QA verdict=" + verdict + " test_exit=" +
                                        str(check.code) + " findings=" +
                                        str(judgment["findings"]) + " log=" + check.output[-1500:])
                state["report"] = json.dumps(
                    {"task_id": task_id, "goal": state["goal"],
                     "base_sha": state["base_sha"], "tested_sha": sha,
                     "attempts": state["attempt"], "qa_exit_code": check.code,
                     "qa_findings": judgment["findings"],
                     "handoff": "READY_FOR_OWNER_REVIEW"},
                    indent=2, ensure_ascii=False)
                return self.ledger.save(state, "READY_FOR_OWNER_REVIEW",
                                        "QA review and independently executed check passed; no merge")
            raise RuntimeError("Unsupported phase " + phase)
        except Exception as exc:
            # External calls can have side effects; never silently repeat an uncertain step.
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
        return self.ledger.save(state, "BLOCKED", "Maximum orchestration steps exceeded")
