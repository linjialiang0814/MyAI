from typing import Dict, List, Optional
import numpy as np
from app.memory.model.mem_item import MemoryItem
from app.memory.model.mem_types import MemoryStatus

class MemoryStore:
    """
    in memory storage
    """
    def __init__(self):
        self._store: Dict[str, List[MemoryItem]] = {}

    def add(self,
            user_id: str,
            content: str,
            vector: np.ndarray,
            mem_type: str = "general",
            score: float = 1.0,
            importance: float = 1.0,
            metadata: Optional[Dict[str, any]] = None,
            ) -> str:
        memory_item = MemoryItem(
            content=content,
            vector=np.array(vector, dtype=np.float32),
            mem_type=mem_type,
            score=score,
            user_id=user_id,
            importance=importance,
            metadata=metadata or {},
        )
        self.add_item(user_id, memory_item)
        return memory_item.memory_id

    def add_item(self, user_id: str, memory_item: MemoryItem) -> str:
        memory_item.user_id = user_id
        if user_id not in self._store:
            self._store[user_id] = []
        self._store[user_id].append(memory_item)
        return memory_item.memory_id

    def get_all(self, user_id: str, active_only: bool = False) -> List[MemoryItem]:
        memories = self._store.get(user_id, []).copy()
        if active_only:
            memories = [m for m in memories if m.status == MemoryStatus.ACTIVE.value]
        return memories

    def get_by_id(self, user_id: str, memory_id: str) -> Optional[MemoryItem]:
        for mem in self._store.get(user_id, []):
            if mem.memory_id == memory_id:
                return mem
        return None

    def replace_all(self, user_id: str, memories: List[MemoryItem])-> None:
        self._store[user_id] = memories.copy()

    def update_memory(self, user_id: str, memory_item: MemoryItem) -> bool:
        memories = self._store.get(user_id, [])
        for i, mem in enumerate(memories):
            if mem.memory_id == memory_item.memory_id:
                memories[i] = memory_item
                return True
        return False

    def update_score_by_id(self, user_id: str, memory_id: str, new_score: float) -> bool:
        memories = self.get_by_id(user_id, memory_id)
        if not memories:
            return False
        memories.score = float(new_score)
        return True

    def touch_memory(self, user_id: str, memory_id: str, score: float | None = None) -> bool:
        memories = self.get_by_id(user_id, memory_id)
        if not memories:
            return False
        memories.touch()
        if score is not None:
            memories.score = float(score)
        return True

    def delete_by_id(self, user_id: str, memory_id: str) -> bool:
        memories = self._store.get(user_id, [])
        original_length = len(memories)
        self._store[user_id] = [m for m in memories if m.memory_id != memory_id]
        return len(self._store[user_id]) != original_length

    def size(self, user_id: str, active_only: bool = False) -> int:
        return len(self.get_all(user_id, active_only=active_only))

    def clear_user_memories(self, user_id: str):
        if user_id in self._store:
            self._store[user_id].clear()

    def get_user_ids(self) -> List[str]:
        return list(self._store.keys())

    def has_user(self, user_id: str) -> bool:
        return user_id in self._store