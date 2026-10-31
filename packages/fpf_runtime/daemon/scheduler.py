# -*- coding: utf-8 -*-
"""FPF Autonomous Engineering Coordinator Heartbeat Scheduler.

Drives multi-task periodic compensation inspection, lease management,
and state machine progression.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from packages.fpf_coordinator.dispatch.journal import StateJournal, TaskRecord
from packages.fpf_coordinator.dispatch.states import (
    HUMAN_GATE_PHASES,
    IN_FLIGHT_PHASES,
    TERMINAL_PHASES,
    Phase,
)
from packages.fpf_runtime.daemon.config import DaemonConfig
from packages.fpf_runtime.daemon.reconciliation import ReconciliationEngine

logger = logging.getLogger("fpf.daemon.scheduler")


class HeartbeatScheduler:
    """Manages periodic heartbeat loops, task leases, and progression across tasks."""

    def __init__(
        self,
        journal: StateJournal,
        config: DaemonConfig,
        reconciliation_engine: Optional[ReconciliationEngine] = None,
        dispatch_handler: Optional[Callable[[TaskRecord], None]] = None,
    ) -> None:
        self.journal = journal
        self.config = config
        self.reconciler = reconciliation_engine or ReconciliationEngine(journal, config.max_reconciliation_attempts)
        self.dispatch_handler = dispatch_handler

        self._managed_tasks: Set[str] = set()
        self._owned_leases: Dict[str, str] = {}  # task_id -> lease_token
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def register_task(self, task_id: str) -> bool:
        """Register a task to be tracked and managed by this scheduler."""
        acquired, token = self.journal.acquire_lease(
            task_id=task_id,
            owner_id=self.config.daemon_id,
            ttl_seconds=self.config.lease_ttl_seconds,
        )
        if acquired and token:
            self._managed_tasks.add(task_id)
            self._owned_leases[task_id] = token
            logger.info("Registered and leased task %s for daemon %s", task_id, self.config.daemon_id)
            return True
        logger.warning("Could not acquire lease for task %s (held by another daemon)", task_id)
        return False

    def unregister_task(self, task_id: str) -> None:
        """Release lease and stop managing task."""
        if task_id in self._owned_leases:
            token = self._owned_leases.pop(task_id)
            self.journal.release_lease(task_id, self.config.daemon_id, token)
        self._managed_tasks.discard(task_id)

    def tick_once(self) -> Dict[str, Any]:
        """Perform a single heartbeat pass across all registered tasks.

        Returns execution telemetry.
        """
        # 1. Run reconciliation across pending intents
        reconciled = self.reconciler.reconcile_all_active_tasks()

        processed_tasks = []
        terminal_tasks = []

        # 2. Iterate through managed tasks
        for task_id in list(self._managed_tasks):
            try:
                task = self.journal.get_task(task_id)
            except Exception:
                self.unregister_task(task_id)
                continue

            # If task entered terminal state, release and unregister
            if task.phase in TERMINAL_PHASES:
                logger.info("Task %s entered terminal phase %s, unregistering", task_id, task.phase.value)
                self.unregister_task(task_id)
                terminal_tasks.append((task_id, task.phase.value))
                continue

            # Renew lease
            token = self._owned_leases.get(task_id)
            if token:
                renewed = self.journal.renew_lease(
                    task_id=task_id,
                    owner_id=self.config.daemon_id,
                    lease_token=token,
                    ttl_seconds=self.config.lease_ttl_seconds,
                )
                if not renewed:
                    # Re-acquire if expired
                    ok, new_token = self.journal.acquire_lease(
                        task_id, self.config.daemon_id, self.config.lease_ttl_seconds
                    )
                    if ok and new_token:
                        self._owned_leases[task_id] = new_token
                    else:
                        logger.warning("Lost lease on task %s, unregistering", task_id)
                        self._managed_tasks.discard(task_id)
                        continue

            # Handle phase dispatch
            if task.phase in HUMAN_GATE_PHASES:
                logger.debug("Task %s awaiting human gate: %s", task_id, task.phase.value)
            elif task.phase in IN_FLIGHT_PHASES:
                logger.debug("Task %s in flight: %s", task_id, task.phase.value)
            elif self.dispatch_handler:
                try:
                    self.dispatch_handler(task)
                except Exception as exc:
                    logger.error("Dispatch handler failed for task %s: %s", task_id, exc)

            processed_tasks.append(task_id)

        return {
            "timestamp": time.time(),
            "daemon_id": self.config.daemon_id,
            "processed_tasks": processed_tasks,
            "reconciled": reconciled,
            "terminal_tasks": terminal_tasks,
        }

    def start_loop(self) -> None:
        """Start background heartbeat thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name=f"Heartbeat-{self.config.daemon_id}", daemon=True)
        self._thread.start()

    def stop_loop(self, timeout: float = 5.0) -> None:
        """Stop background heartbeat thread and release all owned leases."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        # Release all leases on shutdown
        for task_id in list(self._managed_tasks):
            self.unregister_task(task_id)

    def _run_loop(self) -> None:
        logger.info("Heartbeat loop started for daemon %s", self.config.daemon_id)
        while not self._stop_event.is_set():
            try:
                self.tick_once()
            except Exception as exc:
                logger.error("Heartbeat tick encountered unhandled exception: %s", exc)
            self._stop_event.wait(self.config.interval_seconds)
        logger.info("Heartbeat loop stopped for daemon %s", self.config.daemon_id)
