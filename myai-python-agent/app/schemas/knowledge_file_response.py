from pydantic import BaseModel, Field
from typing import Any


class KnowledgeFileResponse(BaseModel):
    file_id: str
    file_name: str
    file_type: str
    size_bytes: int = 0
    content_hash: str = ""
    chunk_count: int
    uploaded_at: str
    summary: str
    document_profile: dict[str, Any] = Field(default_factory=dict)
    parser: str = ""
    parser_version: str = ""
    text_length: int = 0
    embedding_provider: str = ""
    embedding_model: str = ""
    ingestion_status: str = "indexed"
    ingestion_warnings: list[str] = Field(default_factory=list)
    ingestion_report: dict[str, Any] | None = None
