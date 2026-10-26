"""Portable role transports. Drivers are explicitly provided by an operator.

No driver implementation in this repository creates ChatGPT/Codex UI threads
or bypasses login, CAPTCHA, 2FA, or provider permissions. Live smoke is NOT_RUN.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, Any
from .core import TaskPacket, Target

STATES = frozenset({"accepted", "running", "completed", "failed", "unknown", "cancelled"})


@dataclass(frozen=True)
class Receipt:
    request_id: str
    target_identity: str
    provider_turn_id: str
    provider_message_id: str

    def __post_init__(self):
        if not all((self.request_id, self.target_identity,
                    self.provider_turn_id, self.provider_message_id)):
            raise ValueError("Provider receipt must identify request, target, turn, message")


@dataclass(frozen=True)
class Observation:
    request_id: str
    target_identity: str
    state: str
    result_ref: str | None = None
    output_sha256: str | None = None

    def __post_init__(self):
        if self.state not in STATES or not self.request_id or not self.target_identity:
            raise ValueError("Invalid transport observation")
        if self.state == "completed" and (
                not self.result_ref or not re.fullmatch(r"[a-f0-9]{64}", self.output_sha256 or "")):
            raise ValueError("Completed transport needs a stable result ref and output digest")


class RoleTransport(Protocol):
    def dispatch(self, target: Target, packet: TaskPacket) -> Receipt: ...
    def read_status(self, target: Target, receipt: Receipt) -> Observation: ...
    def cancel(self, target: Target, receipt: Receipt) -> Observation: ...


class UnavailableTransport:
    """Honest fail-closed adapter until a provider offers a real interface."""
    def dispatch(self, target: Target, packet: TaskPacket) -> Receipt:
        raise RuntimeError("No authenticated writable thread/browser transport configured")
    def read_status(self, target: Target, receipt: Receipt) -> Observation:
        return Observation(receipt.request_id, target.identity, "unknown")
    def cancel(self, target: Target, receipt: Receipt) -> Observation:
        return Observation(receipt.request_id, target.identity, "unknown")


class CodexThreadBridge:
    """Driver interface: send_thread_message/thread_status/cancel_thread_turn.

    The caller must supply a genuine, permissioned bridge implementation; the
    connected Codex workspace inspection interface is NOT such a bridge.
    """
    def __init__(self, driver: Any):
        self.driver = driver

    def dispatch(self, target: Target, packet: TaskPacket) -> Receipt:
        if target.transport != "codex_thread" or packet.target_identity != target.identity:
            raise ValueError("Codex target mismatch")
        record = self.driver.send_thread_message(
            thread_id=target.identity, workspace=target.workspace,
            request_id=packet.request_id, content=packet.brief())
        if (not isinstance(record, dict) or
                str(record.get("thread_id")) != target.identity or
                str(record.get("request_id")) != packet.request_id):
            raise ValueError("Bridge did not acknowledge the registered target/request")
        return Receipt(packet.request_id, target.identity,
                       str(record.get("turn_id") or ""),
                       str(record.get("message_id") or ""))

    def lookup_by_request(self, target: Target, request_id: str) -> Receipt | None:
        """Only a provider-supported unique lookup can recover an unknown send."""
        lookup = getattr(self.driver, "thread_lookup_by_request", None)
        if not callable(lookup):
            return None
        result = lookup(thread_id=target.identity, workspace=target.workspace,
                        request_id=request_id)
        if not isinstance(result, dict):
            return None
        if result.get("thread_id") != target.identity or result.get("request_id") != request_id:
            return None
        return Receipt(request_id,target.identity,
                       str(result.get("turn_id") or ""),str(result.get("message_id") or ""))

    def read_status(self, target: Target, receipt: Receipt) -> Observation:
        if target.identity != receipt.target_identity:
            raise ValueError("Codex receipt target drift")
        report = self.driver.thread_status(
            thread_id=target.identity, turn_id=receipt.provider_turn_id)
        if (not isinstance(report, dict) or
                str(report.get("thread_id")) != target.identity or
                str(report.get("turn_id")) != receipt.provider_turn_id):
            raise ValueError("Bridge status is not bound to requested turn")
        return Observation(receipt.request_id, target.identity,
                           str(report.get("state") or "unknown"),
                           report.get("result_ref"), report.get("output_sha256"))

    def cancel(self, target: Target, receipt: Receipt) -> Observation:
        result = self.driver.cancel_thread_turn(
            thread_id=target.identity, turn_id=receipt.provider_turn_id)
        if result is not True:
            return Observation(receipt.request_id, target.identity, "unknown")
        return Observation(receipt.request_id, target.identity, "cancelled")


class ChatGPTWebTransport:
    """Driver must affirm visibility on registered conversation, not page load alone.

    An operator-provided browser driver must do its own authentication,
    DOM/message verification, response extraction, and secure navigation.
    No browser automation or existing ChatGPT thread access is shipped here.
    """
    def __init__(self, driver: Any):
        self.driver = driver

    def dispatch(self, target: Target, packet: TaskPacket) -> Receipt:
        if target.transport != "chatgpt_web" or packet.target_identity != target.identity:
            raise ValueError("ChatGPT conversation target mismatch")
        msg = self.driver.send_visible_message(
            conversation_url=target.identity, request_id=packet.request_id,
            content=packet.brief())
        if (not isinstance(msg, dict) or msg.get("conversation_url") != target.identity or
                msg.get("request_id") != packet.request_id or
                msg.get("message_visible") is not True):
            raise ValueError("Browser did not prove message visible in registered thread")
        return Receipt(packet.request_id, target.identity,
                       str(msg.get("turn_id") or ""),
                       str(msg.get("message_id") or ""))

    def lookup_by_request(self, target: Target, request_id: str) -> Receipt | None:
        lookup=getattr(self.driver,"message_lookup_by_request",None)
        if not callable(lookup):
            return None
        result=lookup(conversation_url=target.identity,request_id=request_id)
        if not isinstance(result,dict) or result.get("conversation_url") != target.identity or result.get("request_id") != request_id or result.get("message_visible") is not True:
            return None
        return Receipt(request_id,target.identity,
                       str(result.get("turn_id") or ""),str(result.get("message_id") or ""))

    def read_status(self, target: Target, receipt: Receipt) -> Observation:
        if target.identity != receipt.target_identity:
            raise ValueError("ChatGPT receipt target drift")
        value = self.driver.read_visible_reply(
            conversation_url=target.identity, message_id=receipt.provider_message_id)
        if not isinstance(value, dict) or value.get("conversation_url") != target.identity:
            raise ValueError("Browser reply from unregistered conversation")
        return Observation(receipt.request_id, target.identity,
                           str(value.get("state") or "unknown"),
                           value.get("result_ref"), value.get("output_sha256"))

    def cancel(self, target: Target, receipt: Receipt) -> Observation:
        # Do not invent browser cancellation semantics.
        return Observation(receipt.request_id, target.identity, "unknown")
