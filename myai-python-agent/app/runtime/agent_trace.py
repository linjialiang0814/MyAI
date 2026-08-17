from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentStep:
    name: str
    status: str
    started_at: str
    finished_at: str
    latency_ms: float
    input_summary: str | None = None
    output_summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRun:
    user_id: str
    conversation_id: int | None = None
    kind: str = "chat"
    idempotency_key: str | None = None
    request_hash: str | None = None
    response: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool | None = None
    run_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "running"
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str | None = None
    steps: list[AgentStep] = field(default_factory=list)

    def add_step(
        self,
        name: str,
        status: str,
        started_at: str,
        started_perf: float,
        input_summary: str | None = None,
        output_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        finished_at = utc_now_iso()
        self.steps.append(
            AgentStep(
                name=name,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=round((perf_counter() - started_perf) * 1000, 3),
                input_summary=input_summary,
                output_summary=output_summary,
                metadata=metadata or {},
            )
        )

    def finish(self, status: str = "completed") -> None:
        self.status = status
        self.finished_at = utc_now_iso()


def start_step() -> tuple[str, float]:
    return utc_now_iso(), perf_counter()
