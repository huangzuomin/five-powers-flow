"""Configuration data structures for FPF Autonomous Engineering Coordinator Daemon."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import uuid


@dataclass
class DaemonConfig:
    """Runtime configuration for background coordinator daemon."""
    daemon_id: str = field(default_factory=lambda: f"fpf-daemon-{uuid.uuid4().hex[:12]}")
    state_db_path: Path = field(default_factory=lambda: Path(".fpf-runtime/coordinator.sqlite3"))
    interval_seconds: float = 2.0
    lease_ttl_seconds: int = 30
    max_reconciliation_attempts: int = 3
    pid_file: Path = field(default_factory=lambda: Path(".fpf-runtime/daemon.pid"))

    def resolve_paths(self, base_dir: Path | None = None) -> DaemonConfig:
        root = base_dir or Path.cwd()
        if not self.state_db_path.is_absolute():
            self.state_db_path = root / self.state_db_path
        if not self.pid_file.is_absolute():
            self.pid_file = root / self.pid_file
        return self
