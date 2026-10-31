"""Multi-endpoint registry mapping constitutional roles to physical ProviderAdapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from packages.fpf_runtime.adapters.base import ProviderAdapter


class EndpointNotFoundError(Exception):
    """Raised when an execution endpoint is not registered for a role."""
    pass


class EndpointRegistry:
    """Central registry binding constitutional roles to physical execution endpoints."""

    def __init__(self):
        # (role, endpoint_identity) -> ProviderAdapter
        self._endpoints: Dict[Tuple[str, str], ProviderAdapter] = {}
        # role -> default endpoint_identity
        self._defaults: Dict[str, str] = {}

    def register(
        self,
        role: str,
        endpoint_identity: str,
        adapter: ProviderAdapter,
        is_default: bool = False,
    ) -> None:
        """Register an adapter for a specific role and endpoint identity."""
        key = (role.upper(), endpoint_identity)
        self._endpoints[key] = adapter
        if is_default or role.upper() not in self._defaults:
            self._defaults[role.upper()] = endpoint_identity

    def get(
        self,
        role: str,
        endpoint_identity: Optional[str] = None,
    ) -> ProviderAdapter:
        """Retrieve the appropriate adapter for a given role and optional endpoint."""
        role_key = role.upper()
        ident = endpoint_identity or self._defaults.get(role_key)
        if not ident:
            raise EndpointNotFoundError(f"No endpoint registered or default defined for role '{role}'")

        key = (role_key, ident)
        if key not in self._endpoints:
            raise EndpointNotFoundError(f"Endpoint '{ident}' not found for role '{role}'")

        return self._endpoints[key]

    def list_endpoints(self) -> List[Dict[str, Any]]:
        """List all registered endpoints with their role bindings."""
        results = []
        for (role, ident), adapter in self._endpoints.items():
            results.append({
                "role": role,
                "endpoint_identity": ident,
                "adapter_type": adapter.__class__.__name__,
                "is_default": self._defaults.get(role) == ident,
            })
        return results
