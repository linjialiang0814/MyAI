from dataclasses import dataclass
from typing import Any, List
import numpy as np

@dataclass
class RetrievedMemory:
    memory_id: str
    content: str
    similarity: float
    mem_type: str
    mem_status: str
    score: float
    importance: float = 1.0
    confidence: float = 1.0
    raw_confidence: float = 1.0
    slot: str = ""
    retrieval_weight: float = 1.0
    scope: str = "global"
    sensitivity: str = "normal"
    review_status: str = "accepted"
    source: str = ""
    source_conversation_id: str = ""
    created_at: str = ""
    last_accessed_at: str = ""
    observed_at: str = ""
    valid_from: str = ""
    valid_to: str = ""
    is_current: bool = True
    retrieval_enabled: bool = True
    user_hidden: bool = False
    pinned: bool = False
    final_score: float = 0.0

class MemoryRetriever:
    def __init__(self, memory_store: Any, top_k: int = 5):
        self.memory_store = memory_store
        self.top_k = top_k

    def retrieve(self, user_id: str, embed_vec: np.ndarray, query_text: str | None = None) -> List[RetrievedMemory]:
        """
        retrieve top_k candidate memories. Governance policy decides which
        memories are allowed to enter context and receive reinforcement.
        """
        if hasattr(self.memory_store, "query_similar"):
            top_memories = self.memory_store.query_similar(user_id, embed_vec, self.top_k)
        else:
            memories = self.memory_store.get_all(user_id)
            mem_similarity = []
            for mem in memories:
                similarity = self.cosine_similarity(embed_vec, mem.vector)
                mem_similarity.append((mem, similarity))
            top_memories = sorted(mem_similarity, key=lambda x: x[1], reverse=True)[:self.top_k]

        if query_text:
            boosted_memories = []
            for mem, similarity in top_memories:
                lexical_score = self.lexical_match_score(query_text, mem.content)
                boosted_memories.append((mem, max(float(similarity), lexical_score)))
            top_memories = boosted_memories

        if query_text and hasattr(self.memory_store, "get_all"):
            existing_ids = {mem.memory_id for mem, _ in top_memories}
            for mem in self.memory_store.get_all(user_id):
                if mem.memory_id in existing_ids:
                    continue
                lexical_score = self.lexical_match_score(query_text, mem.content)
                if lexical_score > 0:
                    top_memories.append((mem, lexical_score))
                    existing_ids.add(mem.memory_id)

        top_memories = sorted(top_memories, key=lambda item: item[1], reverse=True)[: self.top_k]

        results: List[RetrievedMemory] = []
        for mem, similarity in top_memories:
            metadata = mem.metadata or {}
            results.append(
                RetrievedMemory(
                    memory_id=mem.memory_id,
                    content=mem.content,
                    similarity=float(similarity),
                    mem_type=mem.mem_type,
                    mem_status=mem.status,
                    score=float(mem.score),
                    importance=float(mem.importance),
                    confidence=_as_float(
                        metadata.get("calibrated_confidence", metadata.get("confidence")),
                        default=1.0,
                    ),
                    raw_confidence=_as_float(metadata.get("confidence"), default=1.0),
                    slot=str(metadata.get("slot", "") or ""),
                    retrieval_weight=_as_float(metadata.get("slot_retrieval_weight"), default=1.0),
                    scope=str(metadata.get("scope", "global") or "global"),
                    sensitivity=str(metadata.get("sensitivity", "normal") or "normal"),
                    review_status=str(metadata.get("review_status", "accepted") or "accepted"),
                    source=str(metadata.get("source", "") or ""),
                    source_conversation_id=str(metadata.get("source_conversation_id", "") or ""),
                    created_at=str(getattr(mem, "created_at", "") or metadata.get("created_at", "") or ""),
                    last_accessed_at=str(
                        getattr(mem, "last_accessed_at", "") or metadata.get("last_accessed_at", "") or ""
                    ),
                    observed_at=str(metadata.get("observed_at", "") or ""),
                    valid_from=str(metadata.get("valid_from", "") or ""),
                    valid_to=str(metadata.get("valid_to", "") or ""),
                    is_current=_as_bool(metadata.get("is_current"), default=True),
                    retrieval_enabled=_as_bool(metadata.get("retrieval_enabled"), default=True),
                    user_hidden=_as_bool(metadata.get("user_hidden"), default=False),
                    pinned=_as_bool(metadata.get("pinned"), default=False),
                )
            )
        return results

    @staticmethod
    def lexical_match_score(query_text: str, content: str) -> float:
        query = _normalize_text(query_text)
        target = _normalize_text(content)
        if not query or not target:
            return 0.0
        if query == target or query in target or target in query:
            return 0.999
        query_tokens = set(query.split())
        target_tokens = set(target.split())
        if not query_tokens or not target_tokens:
            return 0.0
        overlap = len(query_tokens & target_tokens) / max(1, len(query_tokens))
        return 0.92 if overlap >= 0.6 and len(query_tokens & target_tokens) >= 2 else 0.0

    @staticmethod
    def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        return np.dot(v1, v2) / (
            np.linalg.norm(v1) * np.linalg.norm(v2)
        )


def _as_float(value, default: float) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().strip().split())
