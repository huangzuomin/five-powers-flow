"""ChatGPT Web Thread adapter implementing ProviderAdapter via BrowserTransport."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import time
from typing import Any, Dict, List, Optional
import uuid
import yaml

from packages.fpf_coordinator.coordinator import extract_yaml_block
from packages.fpf_runtime.adapters.base import (
    ArtifactRef,
    CancellationObservation,
    Observation,
    ObservationStatus,
    ProviderAdapter,
    Receipt,
)
from packages.fpf_runtime.browser_transport.transport import (
    BrowserTransport,
    BrowserTransportError,
    CDPBrowserTransport,
    ConvergenceTimeoutError,
    EndpointUnavailableError,
)


class ChatGPTWebAdapter:
    """ProviderAdapter for driving ChatGPT Web conversations via clean session isolation."""

    def __init__(
        self,
        transport: Optional[BrowserTransport] = None,
        endpoint_identity: str = "chatgpt-web-default",
        default_timeout: int = 180,
    ):
        self.transport = transport or CDPBrowserTransport()
        self.endpoint_identity = endpoint_identity
        self.default_timeout = default_timeout
        self._receipts: Dict[str, Receipt] = {}
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> request_id
        self._session_transcripts: Dict[str, str] = {}  # request_id -> text

    def format_task_prompt(self, task_packet: Any) -> str:
        """Format an FPF task packet into a strict prompt for the LLM."""
        if isinstance(task_packet, str):
            return task_packet
        
        task_id = getattr(task_packet, "task_id", None) or (task_packet.get("task_id") if isinstance(task_packet, dict) else "UNKNOWN_TASK")
        target_role = getattr(task_packet, "target_role", None) or (task_packet.get("target_role") if isinstance(task_packet, dict) else "DEV")
        payload = getattr(task_packet, "payload", None) or (task_packet.get("payload") if isinstance(task_packet, dict) else {})
        
        lines = [
            f"### FPF Autonomous Task Order: [{target_role}] - {task_id}",
            "You are operating as a designated constitutional role in the Five Powers Flow system.",
            "Follow all governance constraints and return your primary outcome within a valid YAML block.",
            "",
            "#### Task Context & Inputs:",
            json.dumps(payload, indent=2, ensure_ascii=False) if isinstance(payload, dict) else str(payload),
            "",
            "#### Required Output Card:",
            f"Output must conclude with a markdown yaml block containing your official decision card.",
        ]
        return "\n".join(lines)

    def dispatch(
        self,
        task_packet: Any,
        idempotency_key: str,
        timeout_seconds: Optional[int] = None,
    ) -> Receipt:
        """Dispatch task to a fresh isolated ChatGPT Web conversation session."""
        if idempotency_key in self._idempotency_map:
            existing_req_id = self._idempotency_map[idempotency_key]
            return self._receipts[existing_req_id]

        task_id = getattr(task_packet, "task_id", None) or (task_packet.get("task_id") if isinstance(task_packet, dict) else str(uuid.uuid4()))
        version = getattr(task_packet, "version", 1) if not isinstance(task_packet, dict) else task_packet.get("version", 1)
        target_role = getattr(task_packet, "target_role", "DEV") if not isinstance(task_packet, dict) else task_packet.get("target_role", "DEV")

        request_id = f"req-{uuid.uuid4().hex[:12]}"
        prompt = self.format_task_prompt(task_packet)

        # Session isolation: Open a completely clean conversation
        try:
            session_id, session_url = self.transport.open_new_chat()
            self.transport.inject_prompt(prompt)
            status = ObservationStatus.RUNNING
        except EndpointUnavailableError as err:
            session_id = "unavailable"
            session_url = "none"
            status = ObservationStatus.FAILED

        receipt = Receipt(
            request_id=request_id,
            task_id=str(task_id),
            version=int(version),
            target_role=str(target_role),
            endpoint_identity=self.endpoint_identity,
            session_id=session_id,
            dispatched_at=time.time(),
            status=status,
            idempotency_key=idempotency_key,
            metadata={"session_url": session_url, "timeout_seconds": timeout_seconds or self.default_timeout},
        )

        self._receipts[request_id] = receipt
        self._idempotency_map[idempotency_key] = request_id
        return receipt

    def lookup(self, request_id: str) -> Optional[Receipt]:
        """Look up a previous dispatch by request_id."""
        return self._receipts.get(request_id)

    def observe(self, receipt: Receipt) -> Observation:
        """Observe output from ChatGPT Web, waiting for stream convergence."""
        start_time = time.time()
        timeout = receipt.metadata.get("timeout_seconds", self.default_timeout)

        if receipt.status == ObservationStatus.FAILED:
            return Observation(
                status=ObservationStatus.FAILED,
                receipt=receipt,
                error_message="Dispatch failed due to endpoint unavailability",
                elapsed_seconds=0.0,
            )

        try:
            converged_text = self.transport.wait_convergence(timeout_seconds=timeout)
            elapsed = time.time() - start_time
            self._session_transcripts[receipt.request_id] = converged_text

            # Card extraction and validation
            extracted_card = None
            detected_kind = None
            for kind in ("WORK_ORDER", "QA_ADMISSION", "DEV_HANDOFF", "QA_RESULT", "MAP_UPDATE", "SCOPE_GRANT"):
                raw_yaml = extract_yaml_block(converged_text, marker=kind)
                if raw_yaml:
                    try:
                        card = yaml.safe_load(raw_yaml)
                        if isinstance(card, dict) and card.get("kind") == kind:
                            extracted_card = card
                            detected_kind = kind
                            break
                    except Exception:
                        pass

            if not extracted_card:
                # Attempt to extract any YAML block
                raw_generic = extract_yaml_block(converged_text)
                if raw_generic:
                    try:
                        card = yaml.safe_load(raw_generic)
                        if isinstance(card, dict) and "kind" in card:
                            extracted_card = card
                            detected_kind = card["kind"]
                    except Exception:
                        pass

            if extracted_card:
                # Card found and parsed
                return Observation(
                    status=ObservationStatus.COMPLETED,
                    receipt=receipt,
                    output_text=converged_text,
                    yaml_card=extracted_card,
                    card_kind=detected_kind,
                    elapsed_seconds=elapsed,
                )
            else:
                return Observation(
                    status=ObservationStatus.FAILED,
                    receipt=receipt,
                    output_text=converged_text,
                    error_message="Output text converged but no standard YAML card could be extracted",
                    elapsed_seconds=elapsed,
                )

        except ConvergenceTimeoutError as err:
            return Observation(
                status=ObservationStatus.FAILED,
                receipt=receipt,
                error_message=f"Convergence timeout after {timeout}s: {err}",
                elapsed_seconds=time.time() - start_time,
            )
        except EndpointUnavailableError as err:
            return Observation(
                status=ObservationStatus.UNKNOWN,
                receipt=receipt,
                error_message=f"Browser connection lost: {err}",
                elapsed_seconds=time.time() - start_time,
            )
        except Exception as err:
            return Observation(
                status=ObservationStatus.FAILED,
                receipt=receipt,
                error_message=f"Unexpected error observing web output: {err}",
                elapsed_seconds=time.time() - start_time,
            )

    def fetch_artifacts(self, receipt: Receipt) -> List[ArtifactRef]:
        """Return references to session logs and captured output."""
        artifacts = []
        transcript = self._session_transcripts.get(receipt.request_id, "")
        if transcript:
            import hashlib
            digest = hashlib.sha256(transcript.encode("utf-8")).hexdigest()
            artifacts.append(
                ArtifactRef(
                    name=f"chatgpt-{receipt.request_id}-transcript.txt",
                    path=f"memory://transcripts/{receipt.request_id}.txt",
                    digest_sha256=digest,
                    size_bytes=len(transcript.encode("utf-8")),
                    metadata={"session_url": receipt.metadata.get("session_url")},
                )
            )
        return artifacts

    def cancel(self, receipt: Receipt, reason: str = "") -> CancellationObservation:
        """Cancel an in-flight conversation."""
        self.transport.close()
        return CancellationObservation(
            cancelled=True,
            receipt=receipt,
            reason=reason or "User or coordinator requested cancellation",
        )
