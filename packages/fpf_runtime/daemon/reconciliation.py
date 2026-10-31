# -*- coding: utf-8 -*-
"""FPF Autonomous Engineering Coordinator Reconciliation Engine.

Implements crash recovery, intent reconciliation, and BLOCKED_RECONCILIATION
fail-closed protections against duplicate dispatch of unknown external side effects.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from packages.fpf_coordinator.dispatch.journal import (
    IntentRecord,
    StateJournal,
    TaskRecord,
)
from packages.fpf_coordinator.dispatch.states import (
    IN_FLIGHT_PHASES,
    TERMINAL_PHASES,
    Phase,
)

logger = logging.getLogger("fpf.daemon.reconciliation")


class ReconciliationEngine:
    """Reconciles persistent journal intents and external state upon startup or heartbeat."""

    def __init__(
        self,
        journal: StateJournal,
        max_attempts: int = 3,
        provider_lookup: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        self.journal = journal
        self.max_attempts = max_attempts
        self.provider_lookup = provider_lookup
        self._reconciliation_counts: Dict[str, int] = {}

    def reconcile_intent(self, intent: IntentRecord) -> str:
        """Evaluate a single pending or dispatched intent against external truth.

        Returns one of: "SETTLED", "FAILED", "RUNNING", "BLOCKED_RECONCILIATION".
        """
        request_id = intent.request_id
        task_id = intent.task_id

        # 1. If intent is PENDING: crash occurred between intent recording and dispatch
        if intent.status == "PENDING":
            # If provider lookup indicates action never occurred, settle as CANCELLED/PENDING_CLEARED
            if self.provider_lookup:
                lookup_res = self.provider_lookup(request_id)
                status = lookup_res.get("status", "unknown")
                if status == "confirmed_absent":
                    self.journal.mark_intent_settled(request_id, "CONFIRMED_ABSENT")
                    return "FAILED"
            # Otherwise mark as DISPATCH_ABORTED so it can be re-evaluated
            self.journal.mark_intent_settled(request_id, "DISPATCH_ABORTED")
            return "FAILED"

        # 2. If intent is DISPATCHED: query provider or evaluate observation
        if intent.status == "DISPATCHED":
            observation_status = "unknown"
            if self.provider_lookup:
                try:
                    res = self.provider_lookup(request_id)
                    observation_status = res.get("status", "unknown")
                except Exception as exc:
                    logger.warning("Provider lookup failed for %s: %s", request_id, exc)
                    observation_status = "unknown"
            elif intent.receipt and "observation" in intent.receipt:
                observation_status = intent.receipt["observation"].get("status", "unknown")

            if observation_status == "completed":
                self.journal.mark_intent_settled(request_id, "SETTLED")
                return "SETTLED"
            elif observation_status == "failed":
                self.journal.mark_intent_settled(request_id, "FAILED")
                return "FAILED"
            elif observation_status == "running":
                return "RUNNING"
            else:
                # UNKNOWN outcome: track attempt count and fail-closed to BLOCKED_RECONCILIATION
                cnt = self._reconciliation_counts.get(request_id, 0) + 1
                self._reconciliation_counts[request_id] = cnt

                if cnt >= self.max_attempts:
                    logger.critical(
                        "External side effect outcome for request %s is UNKNOWN after %d attempts. "
                        "Transitioning task %s to BLOCKED_RECONCILIATION to prevent duplicate dispatch.",
                        request_id, cnt, task_id,
                    )
                    self.journal.mark_intent_settled(request_id, "BLOCKED_UNKNOWN")
                    try:
                        task = self.journal.get_task(task_id)
                        if task.phase not in TERMINAL_PHASES:
                            self.journal.update_phase(
                                task_id=task_id,
                                expected_version=task.version,
                                new_phase=Phase.BLOCKED_RECONCILIATION,
                                last_failure=(
                                    f"Unknown outcome for request {request_id}: "
                                    f"entering BLOCKED_RECONCILIATION to protect against double dispatch"
                                ),
                            )
                    except Exception as e:
                        logger.error("Failed to transition task %s to BLOCKED_RECONCILIATION: %s", task_id, e)
                    return "BLOCKED_RECONCILIATION"

                return "UNKNOWN"

        return intent.status

    def reconcile_task(self, task_id: str) -> Phase:
        """Reconcile in-flight state and pending intents for a task."""
        task = self.journal.get_task(task_id)
        if task.phase in TERMINAL_PHASES:
            return task.phase

        intents = self.journal.get_pending_intents(task_id=task_id)
        for intent in intents:
            outcome = self.reconcile_intent(intent)
            if outcome == "BLOCKED_RECONCILIATION":
                return Phase.BLOCKED_RECONCILIATION

        # Re-fetch task state after intent reconciliation
        task = self.journal.get_task(task_id)

        # If task was in an IN_FLIGHT phase (e.g. DEV_RUNNING) but has no pending intents remaining
        if task.phase in IN_FLIGHT_PHASES and not intents:
            logger.info("Task %s in flight without active intent, rolling back to BOUNDED_DEV_REWORK", task_id)
            try:
                self.journal.update_phase(
                    task_id=task_id,
                    expected_version=task.version,
                    new_phase=Phase.BOUNDED_DEV_REWORK,
                    last_failure="Unfinished in-flight execution recovered on reconciliation",
                )
                return Phase.BOUNDED_DEV_REWORK
            except Exception:
                pass

        return task.phase

    def reconcile_all_active_tasks(self) -> List[tuple[str, Phase]]:
        """Scan all active tasks and execute reconciliation."""
        results = []
        # Get pending intents across all tasks
        intents = self.journal.get_pending_intents()
        affected_tasks = {intent.task_id for intent in intents}

        for task_id in affected_tasks:
            try:
                final_phase = self.reconcile_task(task_id)
                results.append((task_id, final_phase))
            except Exception as exc:
                logger.error("Failed reconciling task %s: %s", task_id, exc)

        return results
