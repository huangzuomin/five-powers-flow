"""Real Provider Smoke verification and NOT_RUN evidence generator."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List

from packages.fpf_runtime.adapters.chatgpt_web import ChatGPTWebAdapter
from packages.fpf_runtime.adapters.codex_worker import CodexWorkerAdapter
from packages.fpf_runtime.browser_transport.transport import CDPBrowserTransport, TransportConfig


@dataclass
class SmokeCheckResult:
    name: str
    target_endpoint: str
    status: str  # PASS | FAIL | NOT_RUN
    message: str
    details: Dict[str, Any]


class ProviderSmokeVerifier:
    """Audits real physical connectivity and provides fail-closed NOT_RUN boundary evidence."""

    def __init__(self, cdp_port: int = 9222):
        self.cdp_port = cdp_port

    def check_chatgpt_web(self) -> SmokeCheckResult:
        """Audit live connection to local Chrome instance running ChatGPT Web."""
        transport = CDPBrowserTransport(TransportConfig(port=self.cdp_port))
        if not transport.is_live():
            return SmokeCheckResult(
                name="chatgpt_web_cdp_connectivity",
                target_endpoint=f"127.0.0.1:{self.cdp_port}",
                status="NOT_RUN",
                message=(
                    f"Chrome CDP debugging port {self.cdp_port} is not listening. "
                    "Start Chrome with '--remote-debugging-port=9222 --user-data-dir=...' to enable live browser UI."
                ),
                details={"cdp_port": self.cdp_port, "browser_live": False},
            )

        return SmokeCheckResult(
            name="chatgpt_web_cdp_connectivity",
            target_endpoint=f"127.0.0.1:{self.cdp_port}",
            status="PASS",
            message="Chrome CDP debugging port is active and responding to version queries",
            details={"cdp_port": self.cdp_port, "browser_live": True},
        )

    def check_codex_worker(self) -> SmokeCheckResult:
        """Audit local CLI execution environment."""
        codex_exe = shutil.which("codex.exe") or shutil.which("codex")
        git_exe = shutil.which("git.exe") or shutil.which("git")
        python_exe = sys.executable

        details = {
            "codex_executable": codex_exe,
            "git_executable": git_exe,
            "python_executable": python_exe,
        }

        if not git_exe:
            return SmokeCheckResult(
                name="codex_worker_prerequisites",
                target_endpoint="local-system",
                status="FAIL",
                message="Git executable missing from system PATH",
                details=details,
            )

        return SmokeCheckResult(
            name="codex_worker_prerequisites",
            target_endpoint="local-system",
            status="PASS",
            message="Execution tools available for isolated worktree operations",
            details=details,
        )

    def run_all(self) -> List[SmokeCheckResult]:
        return [self.check_chatgpt_web(), self.check_codex_worker()]


if __name__ == "__main__":
    verifier = ProviderSmokeVerifier()
    results = verifier.run_all()
    print(json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False))
