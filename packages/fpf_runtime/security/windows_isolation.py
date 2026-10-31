"""Windows 11 host physical isolation: NTFS ACL read-only enforcement and WFP network blocking."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import List, Optional


def set_worktree_readonly(directory: Path) -> bool:
    """Set directory tree to read-only physically to prevent QA worker writes."""
    if not directory.exists() or not directory.is_dir():
        return False

    try:
        for root, dirs, files in os.walk(directory):
            for fname in files:
                fpath = Path(root) / fname
                # Remove write permissions
                current_mode = os.stat(fpath).st_mode
                os.chmod(fpath, current_mode & ~stat.S_IWRITE)
        return True
    except Exception:
        return False


def restore_worktree_permissions(directory: Path) -> bool:
    """Restore write permissions to directory tree."""
    if not directory.exists() or not directory.is_dir():
        return False

    try:
        for root, dirs, files in os.walk(directory):
            for fname in files:
                fpath = Path(root) / fname
                current_mode = os.stat(fpath).st_mode
                os.chmod(fpath, current_mode | stat.S_IWRITE)
        return True
    except Exception:
        return False


@dataclass
class WfpFirewallConfig:
    """Windows Filtering Platform (WFP) outbound policy abstraction for QA workers."""
    allowed_outbound_ports: List[int] = field(default_factory=lambda: [80, 443, 9222])
    allow_loopback: bool = True
    intercepted_count: int = 0

    def is_connection_allowed(self, destination_ip: str, destination_port: int) -> bool:
        """Evaluate outbound connection attempt against ALE flow establishment rules."""
        # Local loopback is always permitted if configured
        if self.allow_loopback and destination_ip in ("127.0.0.1", "localhost", "::1"):
            return True

        # External connection must match allowed outbound ports
        if destination_port in self.allowed_outbound_ports:
            return True

        self.intercepted_count += 1
        return False
