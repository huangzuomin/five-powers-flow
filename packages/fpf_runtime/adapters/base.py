"""Standard ProviderAdapter protocol and unified data contracts for FPF-AEC."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
import uuid
import time


class ObservationStatus(str, Enum):
    """Normalized observation status across all physical execution endpoints."""
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ArtifactRef:
    """Reference to an execution artifact produced by a provider."""
    name: str
    path: str
    digest_sha256: Optional[str] = None
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Receipt:
    """Cryptographic and temporal proof of dispatch to an execution endpoint."""
    request_id: str
    task_id: str
    version: int
    target_role: str
    endpoint_identity: str
    session_id: str
    dispatched_at: float
    status: ObservationStatus = ObservationStatus.ACCEPTED
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Observation:
    """Observed result from an execution endpoint."""
    status: ObservationStatus
    receipt: Receipt
    output_text: str = ""
    yaml_card: Optional[Dict[str, Any]] = None
    card_kind: Optional[str] = None
    error_message: Optional[str] = None
    elapsed_seconds: float = 0.0
    artifacts: List[ArtifactRef] = field(default_factory=list)


@dataclass(frozen=True)
class CancellationObservation:
    """Outcome of an attempted cancellation."""
    cancelled: bool
    receipt: Receipt
    reason: str
    timestamp: float = field(default_factory=time.time)


@runtime_checkable
class ProviderAdapter(Protocol):
    """Standard abstraction for all FPF execution endpoints.
    
    Enforces the 5 standard primitives:
      1. dispatch(task_packet, idempotency_key) -> Receipt
      2. lookup(request_id) -> Optional[Receipt]
      3. observe(receipt) -> Observation
      4. fetch_artifacts(receipt) -> List[ArtifactRef]
      5. cancel(receipt) -> CancellationObservation
    """

    def dispatch(
        self,
        task_packet: Any,
        idempotency_key: str,
        timeout_seconds: Optional[int] = None,
    ) -> Receipt:
        """Dispatch a task packet to the underlying provider."""
        ...

    def lookup(self, request_id: str) -> Optional[Receipt]:
        """Look up an existing dispatch by its unique request_id."""
        ...

    def observe(self, receipt: Receipt) -> Observation:
        """Poll or observe the current execution state and capture output."""
        ...

    def fetch_artifacts(self, receipt: Receipt) -> List[ArtifactRef]:
        """Retrieve any physical files or logs produced during execution."""
        ...

    def cancel(self, receipt: Receipt, reason: str = "") -> CancellationObservation:
        """Attempt graceful cancellation of a running task."""
        ...
