from typing import Literal

from pydantic import BaseModel


class KnowledgeQueryRequest(BaseModel):
    user_id: str
    query: str
    top_k: int = 3
    file_id: str | None = None
    retrieval_strategy: Literal["vector", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
