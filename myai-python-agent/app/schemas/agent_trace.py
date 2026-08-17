from typing import Any

from pydantic import BaseModel, Field


class AgentStepResponse(BaseModel):
    name: str
    status: str
    started_at: str
    finished_at: str
    latency_ms: float
    input_summary: str | None = None
    output_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    steps: list[AgentStepResponse] = Field(default_factory=list)

