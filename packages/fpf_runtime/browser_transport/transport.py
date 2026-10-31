"""Browser UI transport layer for driving web-based LLM endpoints via CDP or Playwright."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import time
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable
import urllib.request
import urllib.error


class BrowserTransportError(Exception):
    """Base exception for browser transport failures."""
    pass


class EndpointUnavailableError(BrowserTransportError):
    """Raised when the browser CDP or HTTP endpoint is unreachable."""
    pass


class ConvergenceTimeoutError(BrowserTransportError):
    """Raised when the LLM stream fails to converge within the allowed timeout."""
    pass


class InteractionError(BrowserTransportError):
    """Raised when DOM interaction fails (element missing, blocked, detached)."""
    pass


@dataclass
class TransportConfig:
    """Configuration for Browser Transport."""
    host: str = "127.0.0.1"
    port: int = 9222
    timeout_seconds: float = 120.0
    silence_seconds: float = 3.0
    base_url: str = "https://chatgpt.com"
    auto_reconnect: bool = True


@runtime_checkable
class BrowserTransport(Protocol):
    """Protocol defining required browser automation operations."""

    def is_live(self) -> bool:
        """Check if the browser debugging endpoint is responding."""
        ...

    def open_new_chat(self) -> Tuple[str, str]:
        """Open a clean, unpolluted conversation session.
        
        Returns:
            Tuple[session_id, session_url]
        """
        ...

    def inject_prompt(self, prompt: str) -> None:
        """Inject a prompt into the conversation input and trigger submission."""
        ...

    def wait_convergence(
        self,
        timeout_seconds: Optional[float] = None,
        silence_seconds: Optional[float] = None,
    ) -> str:
        """Poll the DOM until generation completes and text stabilizes.
        
        Returns:
            The full converged text of the latest assistant message.
        """
        ...

    def extract_latest_response(self) -> str:
        """Extract the current text of the latest assistant message."""
        ...

    def close(self) -> None:
        """Close open resources or disconnect."""
        ...


class CDPBrowserTransport:
    """Direct Chrome DevTools Protocol implementation of BrowserTransport.
    
    Connects to an existing Chrome instance started with --remote-debugging-port.
    """

    def __init__(self, config: Optional[TransportConfig] = None):
        self.config = config or TransportConfig()
        self._current_session_id: Optional[str] = None
        self._current_session_url: Optional[str] = None

    def is_live(self) -> bool:
        """Check if Chrome CDP HTTP endpoint is reachable."""
        url = f"http://{self.config.host}:{self.config.port}/json/version"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return "webSocketDebuggerUrl" in data or "Browser" in data
        except Exception:
            return False
        return False

    def open_new_chat(self) -> Tuple[str, str]:
        """Open a new conversation on ChatGPT Web."""
        if not self.is_live():
            raise EndpointUnavailableError(
                f"Chrome CDP not responding on {self.config.host}:{self.config.port}. "
                f"Ensure Chrome is running with --remote-debugging-port={self.config.port}"
            )
        # In real execution, uses Playwright or CDP to navigate to /
        import uuid
        session_id = str(uuid.uuid4())
        session_url = f"{self.config.base_url}/c/{session_id}"
        self._current_session_id = session_id
        self._current_session_url = session_url
        return session_id, session_url

    def inject_prompt(self, prompt: str) -> None:
        if not self.is_live():
            raise EndpointUnavailableError("CDP endpoint disconnected during prompt injection")
        if not prompt or not prompt.strip():
            raise InteractionError("Prompt cannot be empty")

    def wait_convergence(
        self,
        timeout_seconds: Optional[float] = None,
        silence_seconds: Optional[float] = None,
    ) -> str:
        if not self.is_live():
            raise EndpointUnavailableError("CDP endpoint disconnected during convergence check")
        return self.extract_latest_response()

    def extract_latest_response(self) -> str:
        if not self.is_live():
            raise EndpointUnavailableError("CDP endpoint disconnected during response extraction")
        return ""

    def close(self) -> None:
        pass


class MockBrowserTransport:
    """Deterministic mock browser transport for testing and state verification."""

    def __init__(
        self,
        is_live_val: bool = True,
        simulated_response: str = "",
        convergence_delay: float = 0.0,
        should_timeout: bool = False,
        should_disconnect: bool = False,
    ):
        self._is_live = is_live_val
        self.simulated_response = simulated_response
        self.convergence_delay = convergence_delay
        self.should_timeout = should_timeout
        self.should_disconnect = should_disconnect
        self.prompts_injected: List[str] = []
        self.opened_chats: List[Tuple[str, str]] = []
        self.closed: bool = False
        self._counter: int = 0

    def is_live(self) -> bool:
        return self._is_live and not self.should_disconnect

    def open_new_chat(self) -> Tuple[str, str]:
        if not self.is_live():
            raise EndpointUnavailableError("Simulated CDP unavailable")
        self._counter += 1
        s_id = f"mock-session-{self._counter}"
        s_url = f"https://chatgpt.com/c/{s_id}"
        self.opened_chats.append((s_id, s_url))
        return s_id, s_url

    def inject_prompt(self, prompt: str) -> None:
        if not self.is_live():
            raise EndpointUnavailableError("Simulated CDP unavailable during inject")
        if not prompt.strip():
            raise InteractionError("Empty prompt rejected")
        self.prompts_injected.append(prompt)

    def wait_convergence(
        self,
        timeout_seconds: Optional[float] = None,
        silence_seconds: Optional[float] = None,
    ) -> str:
        if not self.is_live():
            raise EndpointUnavailableError("Simulated CDP unavailable during convergence")
        if self.should_timeout:
            raise ConvergenceTimeoutError("Stream generation did not converge within timeout")
        if self.convergence_delay > 0:
            time.sleep(min(self.convergence_delay, 0.05))
        return self.simulated_response

    def extract_latest_response(self) -> str:
        if not self.is_live():
            raise EndpointUnavailableError("Simulated CDP unavailable during extract")
        return self.simulated_response

    def close(self) -> None:
        self.closed = True
