from pydantic import BaseModel


class MemorySettingsRequest(BaseModel):
    memory_enabled: bool | None = None
    auto_write_enabled: bool | None = None
    sensitive_requires_confirmation: bool | None = None
    default_memory_view: str | None = None
