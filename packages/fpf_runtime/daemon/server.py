# -*- coding: utf-8 -*-
"""FPF Autonomous Engineering Coordinator Daemon Server.

Manages process lifecycle, PID files, graceful shutdown, and task recovery.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any, Dict, Optional

from packages.fpf_coordinator.dispatch.journal import StateJournal
from packages.fpf_coordinator.dispatch.states import TERMINAL_PHASES, Phase
from packages.fpf_runtime.daemon.config import DaemonConfig
from packages.fpf_runtime.daemon.reconciliation import ReconciliationEngine
from packages.fpf_runtime.daemon.scheduler import HeartbeatScheduler

logger = logging.getLogger("fpf.daemon.server")


def is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is actively running."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class DaemonServer:
    """Central daemon server managing FPF engineering tasks persistently."""

    def __init__(
        self,
        config: Optional[DaemonConfig] = None,
        journal: Optional[StateJournal] = None,
    ) -> None:
        self.config = (config or DaemonConfig()).resolve_paths()
        self.journal = journal or StateJournal(self.config.state_db_path)
        self.reconciler = ReconciliationEngine(self.journal, self.config.max_reconciliation_attempts)
        self.scheduler = HeartbeatScheduler(self.journal, self.config, self.reconciler)

        self._started_at: Optional[float] = None
        self._is_running = False

    def start(self, background: bool = False) -> None:
        """Start the daemon server, acquire PID file, recover tasks, and launch heartbeat."""
        if self._is_running:
            return

        # 1. Single instance check via PID file
        self._acquire_pid_file()

        # 2. Crash recovery: discover active tasks from journal
        recovered = self.recover_on_startup()
        logger.info("Daemon %s recovered %d active tasks on startup", self.config.daemon_id, len(recovered))

        # 3. Setup signal handling
        self._setup_signals()

        self._started_at = time.time()
        self._is_running = True

        if background:
            self.scheduler.start_loop()
        else:
            self.scheduler.start_loop()
            try:
                while self._is_running:
                    time.sleep(1.0)
            except (KeyboardInterrupt, SystemExit):
                self.stop()

    def stop(self) -> None:
        """Gracefully stop heartbeat loop, release leases, and delete PID file."""
        if not self._is_running:
            return

        logger.info("Stopping DaemonServer %s...", self.config.daemon_id)
        self.scheduler.stop_loop()
        self._release_pid_file()
        self._is_running = False
        logger.info("DaemonServer %s stopped successfully", self.config.daemon_id)

    def close(self) -> None:
        """Close daemon server and release underlying database resources."""
        self.stop()
        if hasattr(self.journal, "_conn"):
            try:
                self.journal._conn.close()
            except Exception:
                pass

    def tick_once(self) -> Dict[str, Any]:
        """Execute a single heartbeat and reconciliation step synchronously."""
        return self.scheduler.tick_once()

    def status(self) -> Dict[str, Any]:
        """Return operational status and metrics."""
        pid = None
        if self.config.pid_file.exists():
            try:
                pid = int(self.config.pid_file.read_text(encoding="utf-8").strip())
            except Exception:
                pass

        uptime = time.time() - self._started_at if self._started_at else 0.0

        return {
            "status": "RUNNING" if self._is_running else "STOPPED",
            "daemon_id": self.config.daemon_id,
            "pid": pid,
            "pid_alive": is_pid_alive(pid) if pid else False,
            "uptime_seconds": round(uptime, 2),
            "state_db": str(self.config.state_db_path),
            "managed_tasks": list(self.scheduler._managed_tasks),
            "owned_leases": dict(self.scheduler._owned_leases),
        }

    def recover_on_startup(self) -> list[str]:
        """Scan state journal for unfinished tasks and register them with scheduler."""
        recovered = []
        try:
            cur = self.journal._conn.cursor()
            cur.execute("SELECT task_id, phase FROM tasks;")
            rows = cur.fetchall()
            for row in rows:
                task_id = row["task_id"]
                phase = Phase(row["phase"])
                if phase not in TERMINAL_PHASES:
                    # Run reconciliation on unfinished task
                    self.reconciler.reconcile_task(task_id)
                    # Register into scheduler
                    if self.scheduler.register_task(task_id):
                        recovered.append(task_id)
        except Exception as exc:
            logger.error("Error during startup recovery scan: %s", exc)

        return recovered

    def _acquire_pid_file(self) -> None:
        self.config.pid_file.parent.mkdir(parents=True, exist_ok=True)
        if self.config.pid_file.exists():
            try:
                old_pid = int(self.config.pid_file.read_text(encoding="utf-8").strip())
                if is_pid_alive(old_pid):
                    raise RuntimeError(f"Daemon already running with PID {old_pid}")
                else:
                    logger.warning("Stale PID file found (%d). Overwriting.", old_pid)
            except ValueError:
                pass

        self.config.pid_file.write_text(str(os.getpid()), encoding="utf-8")

    def _release_pid_file(self) -> None:
        if self.config.pid_file.exists():
            try:
                self.config.pid_file.unlink()
            except Exception:
                pass

    def _setup_signals(self) -> None:
        def handler(sig, frame):
            logger.info("Received signal %s, initiating graceful shutdown", sig)
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, handler)
            signal.signal(signal.SIGTERM, handler)
        except (ValueError, AttributeError):
            pass
