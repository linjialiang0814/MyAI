from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSettings:
    database_path: Path
    database_busy_timeout_ms: int = 5_000
    memory_maintenance_enabled: bool = True
    memory_maintenance_debounce_seconds: float = 30.0
    memory_maintenance_idle_poll_seconds: float = 1.0
    memory_maintenance_max_users: int = 10_000
    memory_maintenance_worker_count: int = 2
    memory_maintenance_deadline_seconds: float = 60.0
    memory_maintenance_shutdown_timeout_seconds: float = 5.0
    circuit_failure_threshold: int = 3
    circuit_recovery_seconds: float = 30.0
    retry_base_delay_seconds: float = 0.25
    retry_max_delay_seconds: float = 2.0
    retry_jitter_ratio: float = 0.2
    task_max_pending_runs: int = 100
    task_shutdown_timeout_seconds: float = 5.0
    chat_deadline_seconds: float = 150.0
    task_deadline_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.retry_max_delay_seconds < self.retry_base_delay_seconds:
            raise ValueError("retry_max_delay_seconds must be >= retry_base_delay_seconds")


def load_runtime_settings() -> RuntimeSettings:
    database_path = Path(
        os.getenv("MYAI_RUNTIME_DB_PATH", "./.runtime/runtime.db")
    ).expanduser().resolve()
    return RuntimeSettings(
        database_path=database_path,
        database_busy_timeout_ms=_get_int("MYAI_RUNTIME_DB_BUSY_TIMEOUT_MS", 5_000, minimum=1),
        memory_maintenance_enabled=_get_bool("MYAI_MEMORY_MAINTENANCE_ENABLED", True),
        memory_maintenance_debounce_seconds=_get_float(
            "MYAI_MEMORY_MAINTENANCE_DEBOUNCE_SECONDS", 30.0, minimum=0.0
        ),
        memory_maintenance_idle_poll_seconds=_get_float(
            "MYAI_MEMORY_MAINTENANCE_IDLE_POLL_SECONDS", 1.0, minimum=0.001
        ),
        memory_maintenance_max_users=_get_int(
            "MYAI_MEMORY_MAINTENANCE_MAX_USERS", 10_000, minimum=1
        ),
        memory_maintenance_worker_count=_get_int(
            "MYAI_MEMORY_MAINTENANCE_WORKER_COUNT", 2, minimum=1
        ),
        memory_maintenance_deadline_seconds=_get_float(
            "MYAI_MEMORY_MAINTENANCE_DEADLINE_SECONDS", 60.0, minimum=0.001
        ),
        memory_maintenance_shutdown_timeout_seconds=_get_float(
            "MYAI_MEMORY_MAINTENANCE_SHUTDOWN_TIMEOUT_SECONDS", 5.0, minimum=0.0
        ),
        circuit_failure_threshold=_get_int(
            "MYAI_CIRCUIT_FAILURE_THRESHOLD", 3, minimum=1
        ),
        circuit_recovery_seconds=_get_float(
            "MYAI_CIRCUIT_RECOVERY_SECONDS", 30.0, minimum=0.001
        ),
        retry_base_delay_seconds=_get_float(
            "MYAI_RETRY_BASE_DELAY_SECONDS", 0.25, minimum=0.0
        ),
        retry_max_delay_seconds=_get_float(
            "MYAI_RETRY_MAX_DELAY_SECONDS", 2.0, minimum=0.0
        ),
        retry_jitter_ratio=_get_float(
            "MYAI_RETRY_JITTER_RATIO", 0.2, minimum=0.0, maximum=1.0
        ),
        task_max_pending_runs=_get_int("MYAI_TASK_MAX_PENDING_RUNS", 100, minimum=1),
        task_shutdown_timeout_seconds=_get_float(
            "MYAI_TASK_SHUTDOWN_TIMEOUT_SECONDS", 5.0, minimum=0.0
        ),
        chat_deadline_seconds=_get_float(
            "MYAI_CHAT_DEADLINE_SECONDS", 150.0, minimum=0.001
        ),
        task_deadline_seconds=_get_float(
            "MYAI_TASK_DEADLINE_SECONDS", 120.0, minimum=0.001
        ),
    )


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _get_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw is None or not raw.strip() else int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _get_float(
    name: str,
    default: float,
    *,
    minimum: float,
    maximum: float | None = None,
) -> float:
    raw = os.getenv(name)
    try:
        value = default if raw is None or not raw.strip() else float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        bounds = f"between {minimum} and {maximum}" if maximum is not None else f">= {minimum}"
        raise ValueError(f"{name} must be finite and {bounds}")
    return value
