from __future__ import annotations

import time
from dataclasses import dataclass, field


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and the call should not proceed."""


@dataclass
class CircuitBreaker:
    """Simple in-memory circuit breaker per LLM provider.

    States: closed → open (after failure_threshold failures) → half-open (after
    recovery_timeout seconds) → closed (on first success) or back to open (on failure).
    """

    failure_threshold: int = 3
    recovery_timeout: float = 60.0

    _failures: int = field(default=0, init=False, repr=False)
    _state: str = field(default="closed", init=False, repr=False)
    _opened_at: float = field(default=0.0, init=False, repr=False)

    @property
    def state(self) -> str:
        if self._state == "open" and time.monotonic() - self._opened_at >= self.recovery_timeout:
            self._state = "half_open"
        return self._state

    def before_call(self, provider: str = "") -> None:
        """Raise CircuitOpenError if the circuit is open."""
        if self.state == "open":
            remaining = round(self.recovery_timeout - (time.monotonic() - self._opened_at), 1)
            raise CircuitOpenError(
                f"Circuit open for provider '{provider}'. Retry in {remaining}s."
            )

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.monotonic()
