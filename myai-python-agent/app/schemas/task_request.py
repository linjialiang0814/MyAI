from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=100_000)
    conversation_id: int | None = None
    agent_run_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)
