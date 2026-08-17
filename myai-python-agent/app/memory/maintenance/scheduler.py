from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import threading
import time
from typing import Any, Callable, Protocol

from app.runtime.error_model import ErrorInfo, classify_exception
from app.runtime.resilience import BackoffPolicy, Deadline, bounded_exponential_backoff


logger = logging.getLogger(__name__)


class MemoryMaintainer(Protocol):
    def maintenance(self, user_id: str) -> dict[str, Any]:
        ...


@dataclass
class MaintenanceStatus:
    user_id: str
    requested_generation: int = 0
    completed_generation: int = 0
    running: bool = False
    due_at: float = 0.0
    attempts: int = 0
    last_started_at: float | None = None
    last_completed_at: float | None = None
    last_result: dict[str, Any] | None = None
    last_error: ErrorInfo | None = None

    @property
    def pending(self) -> bool:
        return self.requested_generation > self.completed_generation

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "requested_generation": self.requested_generation,
            "completed_generation": self.completed_generation,
            "pending": self.pending,
            "running": self.running,
            "due_at": self.due_at,
            "attempts": self.attempts,
            "last_started_at": self.last_started_at,
            "last_completed_at": self.last_completed_at,
            "last_result": self.last_result,
            "last_error": self.last_error.to_dict() if self.last_error else None,
        }


class MemoryMaintenanceScheduler:
    """Coalesces memory maintenance by user and runs it outside request paths.

    The scheduler is deliberately lifecycle-neutral: FastAPI lifespan owns start/stop.
    Pending state is process-local; a durable job store can replace it in a later
    checkpoint without changing the scheduling API.
    """

    def __init__(
        self,
        maintainer: MemoryMaintainer | Callable[[str], dict[str, Any]],
        *,
        debounce_seconds: float = 1.0,
        backoff_policy: BackoffPolicy | None = None,
        idle_poll_seconds: float = 1.0,
        max_tracked_users: int = 10_000,
        worker_count: int = 2,
        maintenance_timeout_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        random_source: Callable[[], float] | None = None,
    ) -> None:
        if debounce_seconds < 0:
            raise ValueError("debounce_seconds must be >= 0")
        if idle_poll_seconds <= 0:
            raise ValueError("idle_poll_seconds must be > 0")
        if max_tracked_users < 1:
            raise ValueError("max_tracked_users must be >= 1")
        if worker_count < 1:
            raise ValueError("worker_count must be >= 1")
        if not math.isfinite(maintenance_timeout_seconds) or maintenance_timeout_seconds <= 0:
            raise ValueError("maintenance_timeout_seconds must be finite and > 0")
        if hasattr(maintainer, "try_maintenance"):
            self._maintenance = maintainer.try_maintenance
            self._maintenance_accepts_deadline = True
        else:
            self._maintenance = maintainer.maintenance if hasattr(maintainer, "maintenance") else maintainer
            self._maintenance_accepts_deadline = False
        if not callable(self._maintenance):
            raise TypeError("maintainer must be callable or expose maintenance(user_id)")
        self.debounce_seconds = float(debounce_seconds)
        self.backoff_policy = backoff_policy or BackoffPolicy(max_attempts=3, base_delay_seconds=1.0, max_delay_seconds=30.0)
        self.idle_poll_seconds = float(idle_poll_seconds)
        self.max_tracked_users = max_tracked_users
        self.worker_count = worker_count
        self.maintenance_timeout_seconds = float(maintenance_timeout_seconds)
        self._clock = clock
        self._random_source = random_source
        self._condition = threading.Condition()
        self._states: dict[str, MaintenanceStatus] = {}
        self._stopping = False
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        with self._condition:
            if any(thread.is_alive() for thread in self._threads):
                return
            self._stopping = False
            self._threads = [
                threading.Thread(
                    target=self._worker_loop,
                    name=f"myai-memory-maintenance-{index + 1}",
                    daemon=True,
                )
                for index in range(self.worker_count)
            ]
            for thread in self._threads:
                thread.start()

    def stop(self, *, timeout_seconds: float = 5.0) -> bool:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be >= 0")
        with self._condition:
            self._stopping = True
            threads = list(self._threads)
            self._condition.notify_all()
        deadline = time.monotonic() + timeout_seconds
        for thread in threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        stopped = all(not thread.is_alive() for thread in threads)
        if stopped:
            with self._condition:
                self._threads = []
        return stopped

    def schedule(self, user_id: str) -> dict[str, Any]:
        normalized = str(user_id or "").strip()
        if not normalized:
            raise ValueError("user_id cannot be blank")
        now = self._clock()
        with self._condition:
            state = self._states.get(normalized)
            if state is None:
                self._evict_completed_locked()
                if len(self._states) >= self.max_tracked_users:
                    raise RuntimeError("memory maintenance queue capacity exceeded")
                state = MaintenanceStatus(user_id=normalized)
                self._states[normalized] = state
            was_pending = state.pending
            if not was_pending and not state.running:
                state.attempts = 0
            state.requested_generation += 1
            requested_due_at = now + self.debounce_seconds
            if state.running:
                state.due_at = requested_due_at
            elif not was_pending or state.due_at <= 0:
                state.due_at = requested_due_at
            else:
                # Keep the earliest due time so continuous chat traffic cannot starve maintenance.
                state.due_at = min(state.due_at, requested_due_at)
            self._condition.notify_all()
            return state.to_dict()

    def run_due_once(self) -> bool:
        claimed = self._claim_due()
        if claimed is None:
            return False
        user_id, generation = claimed
        try:
            deadline = Deadline.after(self.maintenance_timeout_seconds)
            deadline.raise_if_expired(operation="memory.maintenance")
            if self._maintenance_accepts_deadline:
                result = self._maintenance(user_id, deadline=deadline)
            else:
                result = self._maintenance(user_id)
            deadline.raise_if_expired(operation="memory.maintenance")
            if not isinstance(result, dict):
                result = {"result": result}
        except Exception as exc:
            self._record_failure(user_id, generation, exc)
        else:
            if result.get("deferred"):
                self._record_deferred(user_id)
            else:
                self._record_success(user_id, generation, result)
        return True

    def status(self, user_id: str) -> dict[str, Any] | None:
        with self._condition:
            state = self._states.get(str(user_id or "").strip())
            return state.to_dict() if state else None

    def snapshot(self) -> list[dict[str, Any]]:
        with self._condition:
            return [self._states[user_id].to_dict() for user_id in sorted(self._states)]

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                if self._stopping:
                    return
            if self.run_due_once():
                continue
            with self._condition:
                if self._stopping:
                    return
                self._condition.wait(timeout=self._wait_seconds_locked())

    def _claim_due(self) -> tuple[str, int] | None:
        now = self._clock()
        with self._condition:
            candidates = [
                state
                for state in self._states.values()
                if state.pending and not state.running and state.due_at <= now
            ]
            if not candidates:
                return None
            state = min(candidates, key=lambda item: (item.due_at, item.user_id))
            state.running = True
            state.last_started_at = now
            return state.user_id, state.requested_generation

    def _record_success(self, user_id: str, generation: int, result: dict[str, Any]) -> None:
        now = self._clock()
        with self._condition:
            state = self._states[user_id]
            state.running = False
            state.completed_generation = max(state.completed_generation, generation)
            state.attempts = 0
            state.last_completed_at = now
            state.last_result = result
            state.last_error = None
            if state.pending:
                state.due_at = max(state.due_at, now + self.debounce_seconds)
            self._condition.notify_all()

    def _record_failure(self, user_id: str, generation: int, exc: Exception) -> None:
        error = classify_exception(exc, operation="memory.maintenance", dependency="memory_store")
        now = self._clock()
        with self._condition:
            state = self._states[user_id]
            state.running = False
            state.attempts += 1
            state.last_error = error
            if not error.retryable or state.attempts >= self.backoff_policy.max_attempts:
                # Mark this generation handled to prevent a tight permanent-failure loop.
                # A later schedule() call creates a new generation and retries it.
                state.completed_generation = max(state.completed_generation, generation)
                state.last_completed_at = now
            else:
                sample = self._random_source() if self._random_source else None
                state.due_at = now + bounded_exponential_backoff(
                    state.attempts,
                    self.backoff_policy,
                    random_value=sample,
                )
            logger.warning(
                "Memory maintenance failed for user=%s code=%s retryable=%s attempt=%s",
                user_id,
                error.code.value,
                error.retryable,
                state.attempts,
            )
            self._condition.notify_all()

    def _record_deferred(self, user_id: str) -> None:
        now = self._clock()
        with self._condition:
            state = self._states[user_id]
            state.running = False
            state.due_at = now + max(0.01, self.idle_poll_seconds)
            self._condition.notify_all()

    def _wait_seconds_locked(self) -> float:
        now = self._clock()
        due_times = [
            state.due_at
            for state in self._states.values()
            if state.pending and not state.running
        ]
        if not due_times:
            return self.idle_poll_seconds
        return max(0.001, min(self.idle_poll_seconds, min(due_times) - now))

    def _evict_completed_locked(self) -> None:
        completed = [
            user_id
            for user_id, state in self._states.items()
            if not state.pending and not state.running
        ]
        for user_id in completed:
            if len(self._states) < self.max_tracked_users:
                break
            self._states.pop(user_id, None)
