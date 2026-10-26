"""Bounded foreground coordinator loop. No daemon, UI access or QA authority."""
from __future__ import annotations
import time
from typing import Callable
from .controller import Coordinator
from .core import next_action


class CoordinationRunner:
    """Refresh GitHub before every role transition and receipt observation.

    A transport COMPLETED observation only tells us to wait for canonical
    GitHub validation; it never advances DEV/QA without new trusted records.
    """
    def __init__(self, source, coordinator: Coordinator, *,
                 issue_number: int, pr_number: int | None, project_id: str,
                 baseline_sha: str, approved_owner_login: str,
                 repo_path, evidence_dir=None,
                 authenticate_qa_pass=None, authenticate_qa_failure=None):
        self.source, self.coordinator = source, coordinator
        self.options = dict(
            issue_number=issue_number,pr_number=pr_number,
            project_id=project_id,baseline_sha=baseline_sha,
            approved_owner_login=approved_owner_login,repo_path=repo_path,
            journal=coordinator.journal,evidence_dir=evidence_dir,
            authenticate_qa_pass=authenticate_qa_pass,
            authenticate_qa_failure=authenticate_qa_failure)

    def tick(self) -> dict:
        """Perform one durable step; safely callable after process restart."""
        state=self.source.snapshot(**self.options)
        decision=next_action(state)
        if decision.phase != "DISPATCH":
            return {"phase":decision.phase,"reason":decision.reason,"request_id":None}
        row=self.coordinator.dispatch_next(state)
        if row["phase"] in ("ACKNOWLEDGED","RUNNING"):
            return self.coordinator.observe(row["request_id"])
        return row

    def run_bounded(self, *, cycles: int = 20, interval_seconds: float = 5.0,
                    sleeper: Callable[[float],None] = time.sleep) -> dict:
        """Foreground caller must explicitly run this; no background promises."""
        if not 1 <= cycles <= 1000 or not 0 <= interval_seconds <= 300:
            raise ValueError("Bounded cycles and interval required")
        result={"phase":"NOT_STARTED"}
        gates={"BLOCKED","BLOCKED_RECONCILIATION","HUMAN_GATE_SCOPE",
               "HUMAN_GATE_MAP","QA_PASSED_AWAITING_OWNER_MERGE"}
        for idx in range(cycles):
            result=self.tick()
            if result["phase"] in gates:
                return result
            if idx+1 < cycles:
                sleeper(interval_seconds)
        return {**result,"bounded_run_exhausted":True}
