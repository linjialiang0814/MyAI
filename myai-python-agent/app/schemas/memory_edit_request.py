from pydantic import BaseModel, Field


class MemoryEditRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    mem_type: str | None = None
    scope: str | None = None
    sensitivity: str | None = None
    importance: float | None = None
    retrieval_enabled: bool | None = None
    pinned: bool | None = None
    user_hidden: bool | None = None
    user_locked: bool | None = None
    is_current: bool | None = None
    user_control_reason: str | None = None
