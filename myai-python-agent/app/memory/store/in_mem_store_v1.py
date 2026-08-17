from typing import Dict, List

from app.memory.model.mem_item_v0 import MemoryItem

#step11 引入记忆衰减之后的store

class MemoryStore:
    """
    Long-term memory storage
    """
    def __init__(self):
        self._store: Dict[str, List[MemoryItem]] = {}

    def add(
            self,
            user_id: str,
            content: str,
            vector,
            mem_type: str = "general",
            score: float = 1.0
    ):
        memory_item = MemoryItem(
            content=content,
            vector=vector,
            mem_type=mem_type,
            score=score
        )

        if user_id not in self._store:
            self._store[user_id] = []

        self._store[user_id].append(memory_item)

    def add_item(self, user_id: str, memory_item: MemoryItem):
        if user_id not in self._store:
            self._store[user_id] = []

        self._store[user_id].append(memory_item)

    def get_all(self, user_id: str) -> List[MemoryItem]:
        return self._store.get(user_id, []).copy()

    def replace_all(self, user_id: str, memories: List[MemoryItem]):
        self._store[user_id] = memories.copy()

    def size(self, user_id: str) -> int:
        return len(self._store.get(user_id, []))

    def clear_user_memories(self, user_id: str):
        if user_id in self._store:
            self._store[user_id].clear()

    def get_user_ids(self) -> List[str]:
        return list(self._store.keys())

    def has_user(self, user_id: str) -> bool:
        return user_id in self._store