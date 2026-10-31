"""Codex Worker adapter implementing ProviderAdapter for isolated CLI execution."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import uuid

from packages.fpf_runtime.adapters.base import (
    ArtifactRef,
    CancellationObservation,
    Observation,
    ObservationStatus,
    ProviderAdapter,
    Receipt,
)


WHITELIST_ENV_VARS = frozenset({
    "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "PATH", "TEMP", "TMP",
    "USERPROFILE", "LOCALAPPDATA", "APPDATA",
    "PYTHONPATH", "PYTHONHOME",
    "FPF_TASK_ID", "FPF_WORKTREE_PATH",
    "LANG", "LC_ALL", "HOME",
})

SENSITIVE_KEYWORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL")


def sanitize_subprocess_env(custom_injections: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Strip sensitive variables and return a clean environment whitelist."""
    clean_env = {}
    for k, v in os.environ.items():
        upper = k.upper()
        if upper in WHITELIST_ENV_VARS:
            if not any(kw in upper for kw in SENSITIVE_KEYWORDS):
                clean_env[k] = v

    if custom_injections:
        for k, v in custom_injections.items():
            clean_env[k] = v

    return clean_env


class CodexWorkerAdapter:
    """ProviderAdapter driving isolated local Codex / test worker executions."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        read_only: bool = False,
        endpoint_identity: str = "codex-cli-worker",
        default_timeout: int = 600,
    ):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.read_only = read_only
        self.endpoint_identity = endpoint_identity
        self.default_timeout = default_timeout
        self._receipts: Dict[str, Receipt] = {}
        self._idempotency_map: Dict[str, str] = {}
        self._execution_results: Dict[str, Dict[str, Any]] = {}

    def dispatch(
        self,
        task_packet: Any,
        idempotency_key: str,
        timeout_seconds: Optional[int] = None,
    ) -> Receipt:
        """Register dispatch intent for local execution."""
        if idempotency_key in self._idempotency_map:
            existing_req_id = self._idempotency_map[idempotency_key]
            return self._receipts[existing_req_id]

        task_id = getattr(task_packet, "task_id", None) or (task_packet.get("task_id") if isinstance(task_packet, dict) else str(uuid.uuid4()))
        version = getattr(task_packet, "version", 1) if not isinstance(task_packet, dict) else task_packet.get("version", 1)
        target_role = getattr(task_packet, "target_role", "DEV_WORKER") if not isinstance(task_packet, dict) else task_packet.get("target_role", "DEV_WORKER")

        request_id = f"worker-{uuid.uuid4().hex[:12]}"
        worktree_path = getattr(task_packet, "worktree_path", None) or (task_packet.get("worktree_path") if isinstance(task_packet, dict) else str(self.workspace_root))
        command = getattr(task_packet, "command", None) or (task_packet.get("command") if isinstance(task_packet, dict) else None)

        receipt = Receipt(
            request_id=request_id,
            task_id=str(task_id),
            version=int(version),
            target_role=str(target_role),
            endpoint_identity=self.endpoint_identity,
            session_id=str(worktree_path),
            dispatched_at=time.time(),
            status=ObservationStatus.ACCEPTED,
            idempotency_key=idempotency_key,
            metadata={
                "worktree_path": str(worktree_path),
                "command": command,
                "read_only": self.read_only,
                "timeout_seconds": timeout_seconds or self.default_timeout,
            },
        )

        self._receipts[request_id] = receipt
        self._idempotency_map[idempotency_key] = request_id
        return receipt

    def lookup(self, request_id: str) -> Optional[Receipt]:
        return self._receipts.get(request_id)

    def observe(self, receipt: Receipt) -> Observation:
        """Execute the command in the target worktree and observe output."""
        meta = receipt.metadata
        worktree = Path(meta.get("worktree_path", self.workspace_root))
        command = meta.get("command")
        timeout = meta.get("timeout_seconds", self.default_timeout)
        start_time = time.time()

        if not worktree.is_dir():
            return Observation(
                status=ObservationStatus.FAILED,
                receipt=receipt,
                error_message=f"Worktree directory does not exist: {worktree}",
                elapsed_seconds=0.0,
            )

        if not command:
            return Observation(
                status=ObservationStatus.FAILED,
                receipt=receipt,
                error_message="No command specified in task packet",
                elapsed_seconds=0.0,
            )

        clean_env = sanitize_subprocess_env({
            "FPF_TASK_ID": receipt.task_id,
            "FPF_WORKTREE_PATH": str(worktree),
        })

        # Pre-execution clean check if QA worker (read-only)
        if self.read_only:
            pre_status = subprocess.run(["git", "status", "--porcelain"], cwd=worktree, capture_output=True, text=True, check=False)
            if pre_status.stdout.strip():
                return Observation(
                    status=ObservationStatus.FAILED,
                    receipt=receipt,
                    error_message=f"QA read-only worktree is initially dirty: {pre_status.stdout.strip()[:200]}",
                    elapsed_seconds=0.0,
                )

        try:
            if isinstance(command, str):
                cmd_args = [command]
                shell = True
            else:
                cmd_args = list(command)
                shell = False

            proc = subprocess.run(
                cmd_args,
                cwd=worktree,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=shell,
                check=False,
            )
            elapsed = time.time() - start_time
            output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")

            # Post-execution read-only check for QA
            if self.read_only:
                post_status = subprocess.run(["git", "status", "--porcelain"], cwd=worktree, capture_output=True, text=True, check=False)
                if post_status.stdout.strip():
                    return Observation(
                        status=ObservationStatus.FAILED,
                        receipt=receipt,
                        output_text=output,
                        error_message="QA read-only violation: worker modified files in tested repository",
                        elapsed_seconds=elapsed,
                    )

            self._execution_results[receipt.request_id] = {
                "exit_code": proc.returncode,
                "output": output,
                "elapsed": elapsed,
            }

            status = ObservationStatus.COMPLETED if proc.returncode == 0 else ObservationStatus.FAILED
            return Observation(
                status=status,
                receipt=receipt,
                output_text=output,
                error_message=None if proc.returncode == 0 else f"Process exited with non-zero code {proc.returncode}",
                elapsed_seconds=elapsed,
            )

        except subprocess.TimeoutExpired as err:
            elapsed = time.time() - start_time
            return Observation(
                status=ObservationStatus.FAILED,
                receipt=receipt,
                error_message=f"Command timed out after {timeout}s",
                elapsed_seconds=elapsed,
            )
        except Exception as err:
            elapsed = time.time() - start_time
            return Observation(
                status=ObservationStatus.FAILED,
                receipt=receipt,
                error_message=f"Execution error: {err}",
                elapsed_seconds=elapsed,
            )

    def fetch_artifacts(self, receipt: Receipt) -> List[ArtifactRef]:
        res = self._execution_results.get(receipt.request_id)
        if not res:
            return []
        output = res.get("output", "")
        digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
        return [
            ArtifactRef(
                name=f"worker-{receipt.request_id}-output.log",
                path=f"memory://worker-logs/{receipt.request_id}.log",
                digest_sha256=digest,
                size_bytes=len(output.encode("utf-8")),
                metadata={"exit_code": res.get("exit_code")},
            )
        ]

    def cancel(self, receipt: Receipt, reason: str = "") -> CancellationObservation:
        return CancellationObservation(
            cancelled=True,
            receipt=receipt,
            reason=reason or "Worker cancellation completed",
        )
