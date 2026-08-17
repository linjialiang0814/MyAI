from dataclasses import dataclass
import json
from typing import List, Optional

import numpy as np

from app.memory.model.mem_item import MemoryItem, utc_now_iso
from app.memory.model.mem_types import MemoryStatus
from app.memory.model.slot_registry import normalize_slot, normalize_value
from app.memory.store.in_mem_store import MemoryStore
from app.memory.store.chroma_store import ChromaMemoryStore

@dataclass
class ResolutionResult:
    action: str #add merge or supersede
    target_memory_id: Optional[str] = None
    reason: str = ""
    target_memory: Optional[MemoryItem] = None

class MemoryDeduplicator:
    """
    the same canonical key & value
    similar semantic
    """
    def __init__(self,
                 memory_store: ChromaMemoryStore,
                 semantic_threshold: float = 0.90):
        self.memory_store = memory_store
        self.sematic_threshold = semantic_threshold

    def resolve(self, user_id: str, new_memory: MemoryItem) -> ResolutionResult:
        if str(new_memory.metadata.get("update_intent", "") or "") == "negation":
            return ResolutionResult("add", reason="negation candidate bypasses dedup")

        existing = self.memory_store.get_all(user_id)

        new_key = normalize_slot(new_memory.mem_type, new_memory.metadata.get("slot"))
        new_value = normalize_value(str(new_memory.metadata.get("value", "")))
        for mem in existing:
            old_key = normalize_slot(mem.mem_type, mem.metadata.get("slot"))
            old_value = normalize_value(str(mem.metadata.get("value", "")))
            if new_memory.mem_type == mem.mem_type and new_key and new_key == old_key and new_value and new_value == old_value:
                reason = "same slot and same value"
                self._merge(mem, new_memory, reason=reason, merge_type="exact")
                self.memory_store.update_memory(user_id, mem)
                return ResolutionResult("merge", mem.memory_id, reason)

        for mem in existing:
            if new_memory.mem_type != mem.mem_type:
                continue
            old_key = normalize_slot(mem.mem_type, mem.metadata.get("slot"))
            old_value = normalize_value(str(mem.metadata.get("value", "")))
            if self._has_structured_value_mismatch(new_key, new_value, old_key, old_value):
                continue
            similarity = self._cosine_similarity(new_memory.vector, mem.vector)
            if similarity >= self.sematic_threshold:
                reason = f"semantic duplicate ({similarity:.3f})"
                self._merge(mem, new_memory, reason=reason, merge_type="semantic", similarity=similarity)
                self.memory_store.update_memory(user_id, mem)
                return ResolutionResult("merge", mem.memory_id, reason)

        return ResolutionResult("add", reason = "no duplicate found")

    @staticmethod
    def _has_structured_value_mismatch(
        new_key: str,
        new_value: str,
        old_key: str,
        old_value: str,
    ) -> bool:
        return bool(new_key and old_key and new_key == old_key and new_value and old_value and new_value != old_value)

    @staticmethod
    def _merge(
        existing: MemoryItem,
        new: MemoryItem,
        *,
        reason: str,
        merge_type: str,
        similarity: float | None = None,
    ) -> None:
        merged_at = utc_now_iso()
        previous_content = existing.content
        existing.score = min(1.0, max(existing.score, new.score) + 0.05)
        existing.importance = max(existing.importance, new.importance)
        existing.access_count += 1
        existing.last_accessed_at = merged_at
        existing.metadata.update(new.metadata)
        _record_merge_audit(
            existing,
            new,
            merged_at=merged_at,
            reason=reason,
            merge_type=merge_type,
            previous_content=previous_content,
            similarity=similarity,
        )
        if len(new.content) > len(existing.content):
            existing.content = new.content
            existing.vector = new.vector

    @staticmethod
    def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        v1 = np.array(v1, dtype=np.float32)
        v2 = np.array(v2, dtype=np.float32)
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        return np.dot(v1, v2) / (
                np.linalg.norm(v1) * np.linalg.norm(v2)
        )


def _record_merge_audit(
    existing: MemoryItem,
    new: MemoryItem,
    *,
    merged_at: str,
    reason: str,
    merge_type: str,
    previous_content: str,
    similarity: float | None,
) -> None:
    existing.metadata["merged_count"] = int(existing.metadata.get("merged_count", 0) or 0) + 1
    existing.metadata["last_merged_at"] = merged_at
    existing.metadata["last_merge_reason"] = reason
    existing.metadata["last_merge_type"] = merge_type
    existing.metadata["last_merged_memory_id"] = new.memory_id

    merged_from = _read_json_list(existing.metadata.get("merged_from"))
    if new.memory_id not in merged_from:
        merged_from.append(new.memory_id)
    existing.metadata["merged_from"] = json.dumps(merged_from[-20:], ensure_ascii=False)

    event = {
        "merged_at": merged_at,
        "merged_memory_id": new.memory_id,
        "merge_type": merge_type,
        "reason": reason,
        "incoming_content": new.content,
        "previous_content": previous_content,
        "incoming_source": str(new.metadata.get("source", "") or ""),
        "incoming_conversation_id": str(new.metadata.get("source_conversation_id", "") or ""),
        "incoming_message_id": str(new.metadata.get("source_message_id", "") or ""),
    }
    if similarity is not None:
        event["similarity"] = round(float(similarity), 4)

    events = _read_json_list(existing.metadata.get("merge_events"))
    events.append(event)
    existing.metadata["merge_events"] = json.dumps(events[-10:], ensure_ascii=False)


def _read_json_list(value) -> list:
    if isinstance(value, list):
        return list(value)
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    if isinstance(parsed, list):
        return parsed
    return []
