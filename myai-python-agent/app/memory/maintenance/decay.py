from datetime import datetime, timezone
from typing import Callable, List

from app.memory.model.mem_item import MemoryItem
from app.memory.store.in_mem_store import MemoryStore
from app.memory.store.chroma_store import ChromaMemoryStore

class MemoryDecay:
    """
    memory decay and forget policy
    """
    def __init__(self,
                 max_memories: int = 100,
                 min_score: float = 0.20,
                 decay_rate: float = 0.98,
                 memory_store: ChromaMemoryStore | None = None,
                 now_provider: Callable[[], datetime] | None = None):
        self.max_memories = max_memories
        self.min_score = min_score
        self.decay_rate = decay_rate
        self.memory_store = memory_store or ChromaMemoryStore()
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def apply_decay_by_user(self, user_id: str) -> List[MemoryItem]:
        memories = self.memory_store.get_all(user_id)
        decayed = self.apply_decay(memories)
        kept_ids = {memory.memory_id for memory in decayed}
        # Update/delete individual records instead of clearing the whole user
        # collection. A concurrent write can no longer be erased by maintenance.
        for memory in decayed:
            self.memory_store.update_memory(user_id, memory)
        for memory in memories:
            if memory.memory_id not in kept_ids:
                self.memory_store.delete_by_id(user_id, memory.memory_id)
        return decayed

    def apply_decay(self, memories: List[MemoryItem]) -> List[MemoryItem]:
        now = self.now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        for mem in memories:
            baselines = [
                parsed
                for parsed in (
                    self._parse_timestamp(mem.metadata.get("last_decay_at")),
                    self._parse_timestamp(mem.last_accessed_at),
                )
                if parsed is not None
            ]
            baseline = max(baselines) if baselines else (self._parse_timestamp(mem.created_at) or now)
            days_gap = max((now - baseline).days, 0)
            if days_gap > 0:
                daily_rate = self.decay_rate * self._type_factor(mem.mem_type)
                mem.score *= daily_rate ** days_gap
            # Preserve the baseline until a full day elapses. Moving the
            # watermark forward on every same-day run could postpone decay
            # forever when a scheduler runs slightly more often than daily.
            watermark = now if days_gap > 0 else baseline
            try:
                mem.metadata["last_decay_at"] = watermark.isoformat()
            except (AttributeError, TypeError):
                mem.metadata = {"last_decay_at": watermark.isoformat()}

        historical = [mem for mem in memories if mem.status not in ("active", "deleted")]
        active_kept = [mem for mem in memories if mem.score >= self.min_score and mem.status == "active"]
        active_kept.sort(
            key = lambda x : (x.score, x.importance, x.access_count),
            reverse = True
        )
        return historical + active_kept[:self.max_memories]


    @staticmethod
    def _type_factor(mem_type: str) -> float:
        factors = {
            "preference": 1.0,
            "fact": 0.997,
            "decision": 0.992,
            "opinion": 0.990,
            "general": 0.985
        }
        return factors.get(mem_type, 0.985)

    @staticmethod
    def _parse_timestamp(value) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
