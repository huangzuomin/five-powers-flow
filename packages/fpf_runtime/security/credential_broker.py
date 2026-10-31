"""Credential Broker for dynamic, time-bounded, and scope-restricted credential dispatch."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import secrets
import time
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ScopedCredential:
    """Time-bounded and action-scoped credential issued to a specific execution worker."""
    token_id: str
    task_id: str
    role: str
    allowed_actions: List[str]
    allowed_paths: List[str] = field(default_factory=list)
    issued_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 1800)
    secret_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))

    def is_valid(self) -> bool:
        """Check if credential has not expired."""
        return time.time() < self.expires_at

    def is_action_permitted(self, action: str, path: Optional[str] = None) -> bool:
        """Verify if the requested action and path are permitted under this credential."""
        if not self.is_valid():
            return False
        if "*" not in self.allowed_actions and action not in self.allowed_actions:
            return False
        if path and self.allowed_paths:
            norm_p = path.replace("\\", "/").strip().lower()
            match = False
            for allowed in self.allowed_paths:
                norm_allowed = allowed.replace("\\", "/").strip().lower()
                if norm_p == norm_allowed or norm_p.startswith(norm_allowed.rstrip("/") + "/"):
                    match = True
                    break
            if not match:
                return False
        return True


class CredentialBroker:
    """Central authority issuing and auditing short-lived, least-privilege credentials."""

    def __init__(self):
        self._active_credentials: Dict[str, ScopedCredential] = {}
        self._revoked_tokens: set[str] = set()

    def issue_credential(
        self,
        role: str,
        task_id: str,
        allowed_actions: List[str],
        ttl_seconds: int = 1800,
        allowed_paths: Optional[List[str]] = None,
    ) -> ScopedCredential:
        """Issue a new scoped, time-bounded credential."""
        token_id = f"fpf-tok-{secrets.token_hex(8)}"
        now = time.time()
        cred = ScopedCredential(
            token_id=token_id,
            task_id=task_id,
            role=role.upper(),
            allowed_actions=allowed_actions,
            allowed_paths=allowed_paths or [],
            issued_at=now,
            expires_at=now + ttl_seconds,
        )
        self._active_credentials[token_id] = cred
        return cred

    def revoke_credential(self, token_id: str) -> bool:
        """Immediately revoke an issued credential."""
        if token_id in self._active_credentials:
            del self._active_credentials[token_id]
            self._revoked_tokens.add(token_id)
            return True
        return False

    def revoke_all_for_task(self, task_id: str) -> int:
        """Revoke all credentials associated with a given task (on task close/cancel)."""
        to_revoke = [
            tok_id for tok_id, cred in self._active_credentials.items()
            if cred.task_id == task_id
        ]
        for tok_id in to_revoke:
            self.revoke_credential(tok_id)
        return len(to_revoke)

    def validate(
        self,
        token_id: str,
        action: str,
        path: Optional[str] = None,
    ) -> bool:
        """Validate whether a token can perform the requested action."""
        if token_id in self._revoked_tokens or token_id not in self._active_credentials:
            return False
        cred = self._active_credentials[token_id]
        return cred.is_action_permitted(action, path)
