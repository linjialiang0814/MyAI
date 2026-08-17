from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import field

class TaskResponse(BaseModel):
    task_run_id: str | None = None
    agent_run_id: str | None = None
    conversation_id: int | None = None
    status: str | None = None
    content: str
    plan: Dict[str, Any] | None = None
    result: Dict[str, Any] | None = None
    reward: Optional[float] = None
    success: bool | None = None
    error: str | None = None
    error_code: str | None = None
    retryable: bool | None = None
    latency_ms: float | None = None
    events: list[Dict[str, Any]] | None = None
