from typing import Any

from pydantic import BaseModel, Field


class KnowledgeQueryHit(BaseModel):
    chunk_id: str
    file_id: str
    file_name: str
    chunk_index: int
    char_start: int = 0
    char_end: int = 0
    page_start: str = ""
    page_end: str = ""
    section_title: str = ""
    token_estimate: int = 0
    content: str
    score: float
    citation_id: str = ""
    snippet: str = ""
    citation: dict[str, Any] = Field(default_factory=dict)
    retrieval_mode: str = ""
    retrieval_score: float = 0.0
    retrieval_strategy: str = "hybrid_rerank"
    rerank_applied: bool = True
    fusion_version: str = ""
    vector_score: float = 0.0
    keyword_score: float = 0.0
    filename_score: float = 0.0
    recency_score: float = 0.0
    file_filter_score: float = 0.0
    retrieval_explanation: dict[str, Any] = Field(default_factory=dict)
    candidate_rank: int = 0
    final_rank: int = 0
    rerank_score: float = 0.0
    query_coverage: float = 0.0
    length_quality: float = 0.0
    duplicate_penalty: float = 0.0
    diversity_penalty: float = 0.0
    selection_status: str = ""
    selection_reason: str = ""
    selection_explanation: dict[str, Any] = Field(default_factory=dict)


class KnowledgeQueryResponse(BaseModel):
    hits: list[KnowledgeQueryHit]
