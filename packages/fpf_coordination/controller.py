"""A single safe coordination tick and explicit resume/poll operations."""
from __future__ import annotations
import json
from pathlib import Path
from .core import CanonicalSnapshot, Target, Decision, make_packet, next_action
from .journal import DispatchJournal, instance_lock
from .transports import Receipt, RoleTransport


class Coordinator:
    def __init__(self, journal: DispatchJournal, registry: dict[str, Target],
                 transports: dict[str, RoleTransport], max_polls: int = 8):
        if not 1 <= max_polls <= 100:
            raise ValueError("Invalid observation limit")
        self.journal, self.registry, self.transports = journal, dict(registry), dict(transports)
        self.max_polls = max_polls

    def dispatch_next(self, snapshot: CanonicalSnapshot) -> dict:
        decision = next_action(snapshot)
        if decision.phase != "DISPATCH":
            return {"phase":decision.phase, "reason":decision.reason, "request_id":None}
        target = self.registry.get(decision.role)
        if target is None:
            return {"phase":"BLOCKED", "reason":"No registered role target", "request_id":None}
        packet = make_packet(snapshot,target)
        transport = self.transports.get(target.transport)
        if transport is None:
            return {"phase":"BLOCKED", "reason":"No authorized transport driver", "request_id":None}
        with instance_lock(self.journal.path):
            existing = self.journal.create(packet,target)
            if existing["phase"] == "SENDING":
                return self.journal.set_phase(packet.request_id,"BLOCKED_RECONCILIATION",
                             reason="Restarted with unconfirmed outbound send; DO NOT resend")
            if existing["phase"] != "CREATED":
                return existing
            self.journal.set_phase(packet.request_id,"SENDING",
                                   reason="Persisted send intent before external effect")
            try:
                receipt = transport.dispatch(target,packet)
                if (not isinstance(receipt,Receipt) or
                        receipt.request_id != packet.request_id or
                        receipt.target_identity != target.identity):
                    raise ValueError("Unbound or malformed transport receipt")
            except Exception as exc:
                return self.journal.set_phase(packet.request_id,"BLOCKED_RECONCILIATION",
                    reason="Uncertain dispatch outcome: "+str(exc)[:350])
            return self.journal.set_phase(packet.request_id,"ACKNOWLEDGED",
                    receipt=receipt,reason="Provider receipt observed; task NOT complete")

    def observe(self, request_id: str) -> dict:
        with instance_lock(self.journal.path):
            state = self.journal.row(request_id)
            if not state:
                raise ValueError("Unknown request ID")
            if state["phase"] == "SENDING":
                return self.journal.set_phase(request_id,"BLOCKED_RECONCILIATION",
                                     reason="Restart after unconfirmed send")
            if state["phase"] not in ("ACKNOWLEDGED","RUNNING"):
                return state
            if state["poll_count"] >= self.max_polls:
                return self.journal.set_phase(request_id,"BLOCKED_RECONCILIATION",
                                     reason="Observation limit reached; do not assume failure")
            target = Target(**json.loads(state["target"]))
            receipt = Receipt(**json.loads(state["receipt"]))
            adapter = self.transports.get(target.transport)
            if adapter is None:
                return self.journal.set_phase(request_id,"BLOCKED_RECONCILIATION",
                                     reason="Transport driver missing after restart")
            try:
                observation = adapter.read_status(target,receipt)
                if observation.request_id != request_id or observation.target_identity != target.identity:
                    raise ValueError("Observation target/request mismatch")
            except Exception as exc:
                return self.journal.set_phase(request_id,"BLOCKED_RECONCILIATION",
                                     reason="Observation not trustworthy: "+str(exc)[:300])
            phase = {
                "accepted":"ACKNOWLEDGED", "running":"RUNNING",
                "completed":"TRANSPORT_COMPLETED_UNVERIFIED",
                "failed":"TRANSPORT_FAILED", "cancelled":"TRANSPORT_CANCELLED",
                "unknown":"BLOCKED_RECONCILIATION",
            }[observation.state]
            return self.journal.set_phase(
                request_id,phase,observation=observation,increment_poll=True,
                reason="Transport state only; re-read canonical GitHub validation")

    def cancel(self, request_id: str) -> dict:
        with instance_lock(self.journal.path):
            state = self.journal.row(request_id)
            if not state:
                raise ValueError("Unknown request ID")
            if state["phase"] not in ("ACKNOWLEDGED","RUNNING"):
                return state
            target=Target(**json.loads(state["target"]))
            receipt=Receipt(**json.loads(state["receipt"]))
            adapter=self.transports.get(target.transport)
            if not adapter:
                return self.journal.set_phase(request_id,"BLOCKED_RECONCILIATION",
                                              reason="Cannot confirm cancellation")
            try:
                observation=adapter.cancel(target,receipt)
                if observation.request_id != request_id or observation.target_identity != target.identity:
                    raise ValueError("Cancellation result mismatch")
            except Exception as exc:
                return self.journal.set_phase(request_id,"BLOCKED_RECONCILIATION",
                                              reason="Unknown cancellation result: "+str(exc)[:300])
            if observation.state != "cancelled":
                return self.journal.set_phase(request_id,"BLOCKED_RECONCILIATION",
                                              reason="Cancellation not confirmed")
            return self.journal.set_phase(request_id,"TRANSPORT_CANCELLED",observation=observation,
                                          reason="Provider acknowledged cancellation")
