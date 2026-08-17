from dataclasses import field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel


class DecisionRecord(BaseModel):
    task_run_id: str | None = None
    agent_run_id: str | None = None
    conversation_id: int | None = None
    status: str | None = None
    user_id: str | None = None
    content: str
    plan: Dict[str, Any] | None = None
    result: Dict[str, Any] | None = None
    reward: Optional[float] = None
    success: bool | None = None
    error: str | None = None
    error_code: str | None = None
    retryable: bool | None = None
    latency_ms: float | None = None
    step_results: list[Dict[str, Any]] | None = None
    events: list[Dict[str, Any]] | None = None
    timestamp: datetime = datetime.now(timezone.utc)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def finalize(self):
        if self.result is not None and self.success is None:
            self.success = bool(self.result.get("success", False))
