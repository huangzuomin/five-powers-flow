# -*- coding: utf-8 -*-
"""Comprehensive unit tests for FPF Autonomous Engineering Coordinator Daemon, Scheduler & Reconciliation."""
from __future__ import annotations

import gc
import os
from pathlib import Path
import tempfile
import time
import unittest

from packages.fpf_coordinator.dispatch.core import make_idempotency_key
from packages.fpf_coordinator.dispatch.journal import StateJournal
from packages.fpf_coordinator.dispatch.states import Phase
from packages.fpf_runtime.cli import handle_daemon_command
from packages.fpf_runtime.daemon.config import DaemonConfig
from packages.fpf_runtime.daemon.reconciliation import ReconciliationEngine
from packages.fpf_runtime.daemon.scheduler import HeartbeatScheduler
from packages.fpf_runtime.daemon.server import DaemonServer, is_pid_alive


class TestDaemonConfigAndLifecycle(unittest.TestCase):
    """Test suite for DaemonConfig, PID management, and server lifecycle."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.db_path = self.root / "state.sqlite3"
        self.pid_path = self.root / "daemon.pid"
        self.server = None

    def tearDown(self):
        if self.server:
            self.server.close()
        gc.collect()
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_config_resolves_paths(self):
        cfg = DaemonConfig(
            state_db_path=Path("rel_db.sqlite3"),
            pid_file=Path("rel_daemon.pid"),
        )
        resolved = cfg.resolve_paths(self.root)
        self.assertTrue(resolved.state_db_path.is_absolute())
        self.assertTrue(resolved.pid_file.is_absolute())
        self.assertEqual(resolved.state_db_path, self.root / "rel_db.sqlite3")

    def test_daemon_start_and_stop_lifecycle(self):
        cfg = DaemonConfig(
            state_db_path=self.db_path,
            pid_file=self.pid_path,
            interval_seconds=0.1,
        )
        self.server = DaemonServer(cfg)

        # Before start
        status_before = self.server.status()
        self.assertEqual(status_before["status"], "STOPPED")
        self.assertFalse(self.pid_path.exists())

        # Start background
        self.server.start(background=True)
        self.assertTrue(self.server._is_running)
        self.assertTrue(self.pid_path.exists())

        status_running = self.server.status()
        self.assertEqual(status_running["status"], "RUNNING")
        self.assertTrue(status_running["pid_alive"])
        self.assertEqual(status_running["pid"], os.getpid())

        # Stop
        self.server.stop()
        self.assertFalse(self.server._is_running)
        self.assertFalse(self.pid_path.exists())
        self.assertEqual(self.server.status()["status"], "STOPPED")

    def test_duplicate_daemon_prevention(self):
        cfg = DaemonConfig(state_db_path=self.db_path, pid_file=self.pid_path)
        self.server = DaemonServer(cfg)
        self.server.start(background=True)

        # Second server instance attempting start with same active PID file
        server2 = DaemonServer(cfg)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                server2.start(background=True)
            self.assertIn("Daemon already running", str(ctx.exception))
        finally:
            server2.close()


class TestHeartbeatAndLeases(unittest.TestCase):
    """Test suite for HeartbeatScheduler and distributed lease management."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.journal = StateJournal(self.root / "state.sqlite3")
        self.task = self.journal.create_task("TASK-H01", "PROJ-1", "a" * 40, Phase.DEV_DISPATCH_PENDING)

    def tearDown(self):
        if hasattr(self.journal, "_conn"):
            self.journal._conn.close()
        gc.collect()
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_lease_acquisition_and_renewal_on_tick(self):
        cfg = DaemonConfig(
            daemon_id="daemon-worker-1",
            state_db_path=self.root / "state.sqlite3",
            lease_ttl_seconds=10,
        )
        scheduler = HeartbeatScheduler(self.journal, cfg)

        # Register task
        ok = scheduler.register_task("TASK-H01")
        self.assertTrue(ok)
        self.assertIn("TASK-H01", scheduler._managed_tasks)

        active, owner = self.journal.is_lease_active("TASK-H01")
        self.assertTrue(active)
        self.assertEqual(owner, "daemon-worker-1")

        # Tick renews lease
        telemetry = scheduler.tick_once()
        self.assertIn("TASK-H01", telemetry["processed_tasks"])

        # Unregister releases lease
        scheduler.unregister_task("TASK-H01")
        active_after, _ = self.journal.is_lease_active("TASK-H01")
        self.assertFalse(active_after)

    def test_lease_contention_by_second_daemon(self):
        cfg1 = DaemonConfig(daemon_id="daemon-1", lease_ttl_seconds=60)
        cfg2 = DaemonConfig(daemon_id="daemon-2", lease_ttl_seconds=60)

        sched1 = HeartbeatScheduler(self.journal, cfg1)
        sched2 = HeartbeatScheduler(self.journal, cfg2)

        self.assertTrue(sched1.register_task("TASK-H01"))
        # Second daemon cannot steal active lease
        self.assertFalse(sched2.register_task("TASK-H01"))


class TestReconciliationEngine(unittest.TestCase):
    """Test suite for intent reconciliation, crash recovery, and BLOCKED_RECONCILIATION."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.journal = StateJournal(self.root / "state.sqlite3")
        self.server = None

    def tearDown(self):
        if self.server:
            self.server.close()
        if hasattr(self.journal, "_conn"):
            self.journal._conn.close()
        gc.collect()
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_reconcile_settles_completed_intent(self):
        task = self.journal.create_task("TASK-R01", "PROJ-1", "b" * 40, Phase.DEV_RUNNING)
        idem_key = make_idempotency_key("TASK-R01", 1, "b" * 40, "edit")

        self.journal.record_intent(
            task_id="TASK-R01",
            request_id="req-001",
            idempotency_key=idem_key,
            role="dev_worker",
            action="edit",
            phase=Phase.DEV_RUNNING,
            payload={"files": ["src/app.py"]},
        )
        self.journal.mark_intent_dispatched(
            request_id="req-001",
            receipt={"receipt_id": "rcpt-1", "observation": {"status": "completed"}},
        )

        engine = ReconciliationEngine(self.journal)
        intents = self.journal.get_pending_intents("TASK-R01")
        self.assertEqual(len(intents), 1)

        outcome = engine.reconcile_intent(intents[0])
        self.assertEqual(outcome, "SETTLED")

        # Intent is no longer pending
        self.assertEqual(len(self.journal.get_pending_intents("TASK-R01")), 0)

    def test_reconcile_unknown_outcome_transitions_to_blocked_reconciliation(self):
        task = self.journal.create_task("TASK-UNKNOWN", "PROJ-1", "c" * 40, Phase.DEV_RUNNING)
        idem_key = make_idempotency_key("TASK-UNKNOWN", 1, "c" * 40, "remote_mutation")

        self.journal.record_intent(
            task_id="TASK-UNKNOWN",
            request_id="req-unk-1",
            idempotency_key=idem_key,
            role="dev_worker",
            action="remote_mutation",
            phase=Phase.DEV_RUNNING,
            payload={"action": "push"},
        )
        # Marked as dispatched with unknown observation
        self.journal.mark_intent_dispatched(
            request_id="req-unk-1",
            receipt={"receipt_id": "rcpt-unk", "observation": {"status": "unknown"}},
        )

        # Provider lookup always returns unknown (e.g. gateway timeout)
        mock_lookup = lambda req_id: {"status": "unknown"}
        engine = ReconciliationEngine(self.journal, max_attempts=3, provider_lookup=mock_lookup)

        intent = self.journal.get_intent("req-unk-1")
        self.assertIsNotNone(intent)

        # Attempts 1 and 2 return UNKNOWN
        self.assertEqual(engine.reconcile_intent(intent), "UNKNOWN")
        self.assertEqual(engine.reconcile_intent(intent), "UNKNOWN")

        # Attempt 3 reaches max_attempts: triggers fail-closed BLOCKED_RECONCILIATION
        outcome_3 = engine.reconcile_intent(intent)
        self.assertEqual(outcome_3, "BLOCKED_RECONCILIATION")

        # Verify task phase in journal transitioned to BLOCKED_RECONCILIATION
        updated_task = self.journal.get_task("TASK-UNKNOWN")
        self.assertEqual(updated_task.phase, Phase.BLOCKED_RECONCILIATION)
        self.assertIn("entering BLOCKED_RECONCILIATION to protect against double dispatch", updated_task.last_failure)

    def test_crash_recovery_on_startup(self):
        # Setup task in progress before crash
        self.journal.create_task("TASK-CRASH-1", "PROJ-1", "d" * 40, Phase.DEV_DISPATCH_PENDING)
        self.journal.create_task("TASK-CRASH-2", "PROJ-1", "d" * 40, Phase.CLOSED)

        cfg = DaemonConfig(state_db_path=self.root / "state.sqlite3", pid_file=self.root / "daemon.pid")
        self.server = DaemonServer(cfg, journal=self.journal)

        recovered = self.server.recover_on_startup()
        self.assertIn("TASK-CRASH-1", recovered)
        # Closed task must not be recovered
        self.assertNotIn("TASK-CRASH-2", recovered)


class TestMultiTaskScheduling(unittest.TestCase):
    """Test suite for concurrent multi-task tracking and terminal unregistration."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.journal = StateJournal(self.root / "state.sqlite3")

    def tearDown(self):
        if hasattr(self.journal, "_conn"):
            self.journal._conn.close()
        gc.collect()
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_multi_task_tick_handles_human_gate_and_terminal(self):
        t1 = self.journal.create_task("TASK-ACTIVE", "PROJ-1", "e" * 40, Phase.DEV_DISPATCH_PENDING)
        t2 = self.journal.create_task("TASK-HUMAN", "PROJ-1", "e" * 40, Phase.HUMAN_GATE_MERGE)
        t3 = self.journal.create_task("TASK-TERM", "PROJ-1", "e" * 40, Phase.CLOSED)

        cfg = DaemonConfig(daemon_id="scheduler-daemon", state_db_path=self.root / "state.sqlite3")
        scheduler = HeartbeatScheduler(self.journal, cfg)

        scheduler.register_task("TASK-ACTIVE")
        scheduler.register_task("TASK-HUMAN")
        scheduler.register_task("TASK-TERM")

        res = scheduler.tick_once()

        self.assertIn("TASK-ACTIVE", res["processed_tasks"])
        self.assertIn("TASK-HUMAN", res["processed_tasks"])
        # Closed task was unmanaged and reported terminal
        self.assertEqual(res["terminal_tasks"], [("TASK-TERM", "CLOSED")])
        self.assertNotIn("TASK-TERM", scheduler._managed_tasks)


class TestCliDaemonCommands(unittest.TestCase):
    """Test suite for CLI `fpf daemon` commands."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.db_path = self.root / "cli_state.sqlite3"
        self.pid_path = self.root / "cli_daemon.pid"

    def tearDown(self):
        gc.collect()
        try:
            self.tmpdir.cleanup()
        except Exception:
            pass

    def test_cli_daemon_status_and_tick(self):
        argv_status = ["status", "--state-db", str(self.db_path), "--pid-file", str(self.pid_path)]
        code_status = handle_daemon_command(argv_status)
        self.assertEqual(code_status, 0)

        argv_tick = ["tick", "--state-db", str(self.db_path), "--pid-file", str(self.pid_path)]
        code_tick = handle_daemon_command(argv_tick)
        self.assertEqual(code_tick, 0)


if __name__ == "__main__":
    unittest.main()
