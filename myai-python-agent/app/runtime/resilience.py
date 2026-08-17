from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import random
import threading
import time
from typing import Callable

from app.runtime.error_model import AppError, ErrorCode, ErrorInfo, classify_exception


@dataclass(frozen=True)
class BackoffPolicy:
    max_attempts: int = 2
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        for name, value in (
            ("base_delay_seconds", self.base_delay_seconds),
            ("max_delay_seconds", self.max_delay_seconds),
            ("jitter_ratio", self.jitter_ratio),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        if self.jitter_ratio > 1:
            raise ValueError("jitter_ratio must be <= 1")


def bounded_exponential_backoff(
    retry_number: int,
    policy: BackoffPolicy,
    *,
    random_value: float | None = None,
) -> float:
    """Return the delay before retry_number (1 means the first retry)."""

    if retry_number < 1:
        raise ValueError("retry_number must be >= 1")
    base = min(policy.max_delay_seconds, policy.base_delay_seconds * (2 ** (retry_number - 1)))
    if base == 0 or policy.jitter_ratio == 0:
        return base
    sample = random.random() if random_value is None else min(1.0, max(0.0, random_value))
    lower = base * (1 - policy.jitter_ratio)
    return min(policy.max_delay_seconds, lower + (base - lower) * sample)


@dataclass(frozen=True)
class Deadline:
    expires_at: float
    clock: Callable[[], float] = time.monotonic

    @classmethod
    def after(cls, timeout_seconds: float, *, clock: Callable[[], float] = time.monotonic) -> "Deadline":
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and > 0")
        return cls(expires_at=clock() + timeout_seconds, clock=clock)

    def remaining_seconds(self) -> float:
        return max(0.0, self.expires_at - self.clock())

    def raise_if_expired(self, *, operation: str | None = None) -> None:
        if self.remaining_seconds() <= 0:
            raise AppError(
                ErrorInfo(
                    code=ErrorCode.OPERATION_TIMEOUT,
                    message="The operation deadline was exceeded.",
                    retryable=True,
                    operation=operation,
                )
            )


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitPermit:
    generation: int
    half_open_probe: bool = False


class CircuitBreaker:
    """Small thread-safe consecutive-failure circuit breaker."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if not math.isfinite(recovery_timeout_seconds) or recovery_timeout_seconds <= 0:
            raise ValueError("recovery_timeout_seconds must be finite and > 0")
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._half_open_probe_active = False
        self._generation = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._refresh_state_locked()
            return self._state

    def before_call(
        self,
        *,
        operation: str | None = None,
        dependency: str | None = None,
    ) -> CircuitPermit:
        with self._lock:
            self._refresh_state_locked()
            if self._state == CircuitState.OPEN:
                retry_after = max(0.0, self.recovery_timeout_seconds - (self._clock() - self._opened_at))
                raise AppError(
                    ErrorInfo(
                        code=ErrorCode.CIRCUIT_OPEN,
                        message="The dependency circuit is open.",
                        retryable=True,
                        operation=operation,
                        dependency=dependency,
                        details={"retry_after_seconds": round(retry_after, 3)},
                    )
                )
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_probe_active:
                    raise AppError(
                        ErrorInfo(
                            code=ErrorCode.CIRCUIT_OPEN,
                            message="The dependency circuit is awaiting a recovery probe.",
                            retryable=True,
                            operation=operation,
                            dependency=dependency,
                        )
                    )
                self._half_open_probe_active = True
                return CircuitPermit(self._generation, half_open_probe=True)
            return CircuitPermit(self._generation)

    def record_success(self, permit: CircuitPermit | None = None) -> bool:
        with self._lock:
            if permit is not None:
                if permit.generation != self._generation:
                    return False
                if self._state == CircuitState.OPEN:
                    return False
                if self._state == CircuitState.HALF_OPEN and not permit.half_open_probe:
                    return False
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._opened_at = 0.0
            self._half_open_probe_active = False
            return True

    def record_failure(self, permit: CircuitPermit | None = None) -> bool:
        with self._lock:
            if permit is not None and permit.generation != self._generation:
                return False
            self._half_open_probe_active = False
            self._consecutive_failures += 1
            if self._state == CircuitState.HALF_OPEN or self._consecutive_failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                self._generation += 1
            return True

    def release_probe(self, permit: CircuitPermit | None) -> bool:
        """Release a half-open permit when the outcome says nothing about health."""
        if permit is None:
            return False
        with self._lock:
            if permit.generation != self._generation:
                return False
            if self._state == CircuitState.HALF_OPEN and permit.half_open_probe:
                self._half_open_probe_active = False
                return True
            return False

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            self._refresh_state_locked()
            return {
                "state": self._state.value,
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout_seconds,
                "generation": self._generation,
            }

    def _refresh_state_locked(self) -> None:
        if self._state == CircuitState.OPEN and self._clock() - self._opened_at >= self.recovery_timeout_seconds:
            self._state = CircuitState.HALF_OPEN
            self._half_open_probe_active = False


class CircuitBreakerRegistry:
    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, key: str) -> CircuitBreaker:
        normalized = str(key or "").strip()
        if not normalized:
            raise ValueError("circuit breaker key cannot be blank")
        with self._lock:
            breaker = self._breakers.get(normalized)
            if breaker is None:
                breaker = CircuitBreaker(
                    failure_threshold=self.failure_threshold,
                    recovery_timeout_seconds=self.recovery_timeout_seconds,
                    clock=self._clock,
                )
                self._breakers[normalized] = breaker
            return breaker

    def snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            items = list(self._breakers.items())
        return {key: breaker.snapshot() for key, breaker in sorted(items)}


class CircuitProtectedEmbeddingClient:
    """Adds the shared runtime circuit to an embedding client without retrying writes."""

    def __init__(self, client, breaker: CircuitBreaker, dependency: str):
        self.client = client
        self.breaker = breaker
        self.dependency = dependency
        self._closed = False

    def embed(self, text: str):
        if not str(text or "").strip():
            raise AppError(
                ErrorInfo(
                    code=ErrorCode.INVALID_ARGUMENT,
                    message="Embedding text cannot be empty.",
                    operation="embedding.embed",
                )
            )
        permit = self.breaker.before_call(
            operation="embedding.embed",
            dependency=self.dependency,
        )
        try:
            vector = self.client.embed(text)
        except Exception as exc:
            if is_transient_dependency_error(exc):
                self.breaker.record_failure(permit)
            else:
                self.breaker.release_probe(permit)
            raise
        self.breaker.record_success(permit)
        return vector

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self.client, "close", None)
        if callable(close):
            close()


def is_transient_dependency_error(exc: BaseException) -> bool:
    info = classify_exception(exc)
    return info.code in {
        ErrorCode.OPERATION_TIMEOUT,
        ErrorCode.RATE_LIMITED,
        ErrorCode.DEPENDENCY_UNAVAILABLE,
        ErrorCode.CIRCUIT_OPEN,
    }
