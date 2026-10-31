"""Comprehensive unit tests for FPF-AEC Provider Adapters and Browser Transport."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from packages.fpf_runtime.adapters.base import (
    ArtifactRef,
    ObservationStatus,
    ProviderAdapter,
    Receipt,
)
from packages.fpf_runtime.adapters.chatgpt_web import ChatGPTWebAdapter
from packages.fpf_runtime.adapters.codex_worker import (
    CodexWorkerAdapter,
    sanitize_subprocess_env,
)
from packages.fpf_runtime.adapters.registry import (
    EndpointNotFoundError,
    EndpointRegistry,
)
from packages.fpf_runtime.adapters.smoke import ProviderSmokeVerifier
from packages.fpf_runtime.browser_transport.transport import (
    CDPBrowserTransport,
    ConvergenceTimeoutError,
    EndpointUnavailableError,
    MockBrowserTransport,
    TransportConfig,
)


SAMPLE_WORK_ORDER_RESPONSE = """Here is the work order plan:

```yaml
kind: WORK_ORDER
task_id: FPF-TEST-001
objective: Implement authentication middleware
boundaries:
  allowed_paths:
    - src/auth.py
acceptance_criteria:
  - 100% test pass
```

Please proceed with implementation.
"""

SAMPLE_QA_RESULT_RESPONSE = """QA adversarial testing has concluded.

```yaml
kind: QA_RESULT
task_id: FPF-TEST-001
tested_sha: 1234567890abcdef1234567890abcdef12345678
verdict: PASS
profile: Library
checks:
  - name: auth_unit_tests
    exit_code: 0
findings:
  p0: []
  p1: []
```
"""


class TestProviderAdapterProtocols(unittest.TestCase):
    """Verify standard protocol implementation."""

    def test_protocol_conformance(self):
        web_adapter = ChatGPTWebAdapter(transport=MockBrowserTransport())
        worker_adapter = CodexWorkerAdapter()
        self.assertIsInstance(web_adapter, ProviderAdapter)
        self.assertIsInstance(worker_adapter, ProviderAdapter)


class TestChatGPTWebAdapter(unittest.TestCase):
    """Unit tests for ChatGPTWebAdapter driving web sessions."""

    def test_successful_dispatch_and_observation(self):
        transport = MockBrowserTransport(simulated_response=SAMPLE_WORK_ORDER_RESPONSE)
        adapter = ChatGPTWebAdapter(transport=transport, endpoint_identity="chatgpt-dev-test")

        packet = {"task_id": "FPF-TEST-001", "version": 1, "target_role": "DEV", "payload": {"requirement": "Build auth"}}
        receipt = adapter.dispatch(packet, idempotency_key="idemp-key-1")

        self.assertEqual(receipt.task_id, "FPF-TEST-001")
        self.assertEqual(receipt.target_role, "DEV")
        self.assertEqual(receipt.status, ObservationStatus.RUNNING)
        self.assertTrue(receipt.request_id.startswith("req-"))
        self.assertIn("https://chatgpt.com/c/", receipt.metadata["session_url"])

        obs = adapter.observe(receipt)
        self.assertEqual(obs.status, ObservationStatus.COMPLETED)
        self.assertIsNotNone(obs.yaml_card)
        self.assertEqual(obs.card_kind, "WORK_ORDER")
        self.assertEqual(obs.yaml_card["task_id"], "FPF-TEST-001")
        self.assertIn("Implement authentication middleware", obs.yaml_card["objective"])

        # Verify artifact retrieval
        artifacts = adapter.fetch_artifacts(receipt)
        self.assertEqual(len(artifacts), 1)
        self.assertTrue(artifacts[0].name.endswith("-transcript.txt"))
        self.assertIsNotNone(artifacts[0].digest_sha256)

    def test_idempotent_dispatch_deduplication(self):
        transport = MockBrowserTransport(simulated_response=SAMPLE_QA_RESULT_RESPONSE)
        adapter = ChatGPTWebAdapter(transport=transport)

        packet = {"task_id": "FPF-TEST-002", "version": 1, "target_role": "QA", "payload": {}}
        receipt1 = adapter.dispatch(packet, idempotency_key="unique-idemp-123")
        receipt2 = adapter.dispatch(packet, idempotency_key="unique-idemp-123")

        # Identical key must return the exact same receipt
        self.assertEqual(receipt1.request_id, receipt2.request_id)
        self.assertEqual(receipt1.dispatched_at, receipt2.dispatched_at)
        self.assertEqual(len(transport.opened_chats), 1)

    def test_timeout_observation_handling(self):
        transport = MockBrowserTransport(should_timeout=True)
        adapter = ChatGPTWebAdapter(transport=transport)

        packet = {"task_id": "FPF-TEST-003", "version": 1, "target_role": "DEV", "payload": {}}
        receipt = adapter.dispatch(packet, idempotency_key="idemp-timeout")

        obs = adapter.observe(receipt)
        self.assertEqual(obs.status, ObservationStatus.FAILED)
        self.assertIn("Convergence timeout", obs.error_message)

    def test_endpoint_unavailable_observation_handling(self):
        transport = MockBrowserTransport(is_live_val=False)
        adapter = ChatGPTWebAdapter(transport=transport)

        packet = {"task_id": "FPF-TEST-004", "version": 1, "target_role": "DEV", "payload": {}}
        receipt = adapter.dispatch(packet, idempotency_key="idemp-unavail")

        self.assertEqual(receipt.status, ObservationStatus.FAILED)
        obs = adapter.observe(receipt)
        self.assertEqual(obs.status, ObservationStatus.FAILED)

    def test_no_card_extracted_handling(self):
        transport = MockBrowserTransport(simulated_response="I have reviewed your request. Everything looks fine!")
        adapter = ChatGPTWebAdapter(transport=transport)

        packet = {"task_id": "FPF-TEST-005", "version": 1, "target_role": "DEV", "payload": {}}
        receipt = adapter.dispatch(packet, idempotency_key="idemp-nocard")

        obs = adapter.observe(receipt)
        self.assertEqual(obs.status, ObservationStatus.FAILED)
        self.assertIn("no standard YAML card could be extracted", obs.error_message)

    def test_cancellation(self):
        transport = MockBrowserTransport(simulated_response=SAMPLE_WORK_ORDER_RESPONSE)
        adapter = ChatGPTWebAdapter(transport=transport)

        packet = {"task_id": "FPF-TEST-006", "version": 1, "target_role": "DEV", "payload": {}}
        receipt = adapter.dispatch(packet, idempotency_key="idemp-cancel")

        cancel_obs = adapter.cancel(receipt, reason="Operator abort")
        self.assertTrue(cancel_obs.cancelled)
        self.assertTrue(transport.closed)


class TestCodexWorkerAdapter(unittest.TestCase):
    """Unit tests for CodexWorkerAdapter and environment isolation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="fpf-worker-test-")
        self.worktree = Path(self.temp_dir.name)
        # Initialize a minimal git repository in temp worktree
        subprocess.run(["git", "init"], cwd=self.worktree, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=self.worktree, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.worktree, capture_output=True, check=True)
        (self.worktree / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.worktree, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.worktree, capture_output=True, check=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_command_execution(self):
        adapter = CodexWorkerAdapter(workspace_root=self.worktree)
        packet = {
            "task_id": "FPF-WORKER-001",
            "version": 1,
            "target_role": "DEV_WORKER",
            "worktree_path": str(self.worktree),
            "command": ["git", "rev-parse", "HEAD"],
        }

        receipt = adapter.dispatch(packet, idempotency_key="worker-idemp-1")
        self.assertEqual(receipt.status, ObservationStatus.ACCEPTED)

        obs = adapter.observe(receipt)
        self.assertEqual(obs.status, ObservationStatus.COMPLETED)
        self.assertEqual(len(obs.output_text.strip()), 40)  # Valid SHA-1

        artifacts = adapter.fetch_artifacts(receipt)
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].metadata["exit_code"], 0)

    def test_failed_command_execution(self):
        adapter = CodexWorkerAdapter(workspace_root=self.worktree)
        packet = {
            "task_id": "FPF-WORKER-002",
            "version": 1,
            "target_role": "DEV_WORKER",
            "worktree_path": str(self.worktree),
            "command": ["git", "checkout", "non_existent_branch_xyz"],
        }

        receipt = adapter.dispatch(packet, idempotency_key="worker-idemp-fail")
        obs = adapter.observe(receipt)
        self.assertEqual(obs.status, ObservationStatus.FAILED)
        self.assertIn("non-zero code", obs.error_message)

    def test_qa_worker_read_only_violation(self):
        adapter = CodexWorkerAdapter(workspace_root=self.worktree, read_only=True)
        # Command that maliciously writes to the repository
        malicious_cmd = [sys.executable, "-c", "open('tampered.txt', 'w').write('dirty')"]
        packet = {
            "task_id": "FPF-WORKER-003",
            "version": 1,
            "target_role": "QA_WORKER",
            "worktree_path": str(self.worktree),
            "command": malicious_cmd,
        }

        receipt = adapter.dispatch(packet, idempotency_key="worker-idemp-qa-violation")
        obs = adapter.observe(receipt)
        self.assertEqual(obs.status, ObservationStatus.FAILED)
        self.assertIn("read-only violation", obs.error_message)

    def test_environment_stripping(self):
        os.environ["GH_TOKEN"] = "ghp_super_secret_token_to_strip"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "aws_secret_key_to_strip"
        os.environ["SAFE_INJECTION"] = "custom_val"

        clean = sanitize_subprocess_env({"CUSTOM_ALLOW": "1"})
        self.assertNotIn("GH_TOKEN", clean)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", clean)
        self.assertEqual(clean.get("CUSTOM_ALLOW"), "1")


class TestEndpointRegistry(unittest.TestCase):
    """Unit tests for multi-endpoint role registry."""

    def test_registry_registration_and_lookup(self):
        registry = EndpointRegistry()
        web_adapter = ChatGPTWebAdapter(transport=MockBrowserTransport(), endpoint_identity="chatgpt-dev")
        worker_adapter = CodexWorkerAdapter(endpoint_identity="codex-worker-dev")

        registry.register("DEV", "chatgpt-dev", web_adapter, is_default=True)
        registry.register("DEV_WORKER", "codex-worker-dev", worker_adapter, is_default=True)

        self.assertEqual(registry.get("DEV"), web_adapter)
        self.assertEqual(registry.get("DEV", "chatgpt-dev"), web_adapter)
        self.assertEqual(registry.get("DEV_WORKER"), worker_adapter)

        with self.assertRaises(EndpointNotFoundError):
            registry.get("NON_EXISTENT_ROLE")

        with self.assertRaises(EndpointNotFoundError):
            registry.get("DEV", "unknown-endpoint")

        endpoints = registry.list_endpoints()
        self.assertEqual(len(endpoints), 2)


class TestSmokeVerifier(unittest.TestCase):
    """Unit tests for live provider smoke audit."""

    def test_cdp_offline_returns_not_run(self):
        # Port 59999 should not have Chrome listening
        verifier = ProviderSmokeVerifier(cdp_port=59999)
        res = verifier.check_chatgpt_web()
        self.assertEqual(res.status, "NOT_RUN")
        self.assertIn("not listening", res.message)

    def test_worker_prerequisites(self):
        verifier = ProviderSmokeVerifier()
        res = verifier.check_codex_worker()
        self.assertEqual(res.status, "PASS")


if __name__ == "__main__":
    unittest.main()
