from typing import Any

from pydantic import BaseModel, Field

from app.schemas.knowledge_query_response import KnowledgeQueryHit


class KnowledgeQAResponse(BaseModel):
    file_id: str
    file_name: str = ""
    question: str
    answer: str
    answer_status: str
    evidence_count: int = 0
    citations: list[dict[str, Any]] = Field(default_factory=list)
    hits: list[KnowledgeQueryHit] = Field(default_factory=list)
