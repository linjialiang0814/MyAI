from typing import Any

from pydantic import BaseModel, Field


class KnowledgeMaintenanceResponse(BaseModel):
    user_id: str
    dry_run: bool = True
    file_id: str = ""
    rebuild: bool = False
    status: str
    checked_at: str
    summary: dict[str, Any] = Field(default_factory=dict)
    files: list[dict[str, Any]] = Field(default_factory=list)
    orphan_chunk_ids: list[str] = Field(default_factory=list)
    duplicate_groups: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
