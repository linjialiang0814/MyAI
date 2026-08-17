from typing import List

from app.memory.model.mem_item_v0 import MemoryItem
from app.memory.store.in_mem_store_v1 import MemoryStore

#step11 引入记忆衰减

class MemoryDecay:
    """
    Memory decay and forgetting policy.
    """

    def __init__(
            self,
            max_memories: int = 100,
            min_score: float = 0.20,
            decay_rate: float = 0.98,
            memory_store: MemoryStore = MemoryStore()
    ):
        """
        max_memories: maximum memories per user
        min_score: memories below this score will be removed
        decay_rate: multiplicative decay applied per access
        """
        self.max_memories = max_memories
        self.min_score = min_score
        self.decay_rate = decay_rate
        self.memory_store = memory_store

    def apply_decay_by_user(self, user_id: str) -> List[MemoryItem]:
        """
        Apply decay to memory scores.
        """
        memories = self.memory_store.get_all(user_id)

        for mem in memories:
            mem.score *= self.decay_rate

        """
        Remove low-score and overflow memories.
        """
        # Step 1: remove low-score memories
        memories = [
            mem for mem in memories if mem.score >= self.min_score
        ]

        # Step 2: enforce capacity (keep the highest score)
        memories.sort(key=lambda x: x.score, reverse=True) #x:x["score"]
        return memories[: self.max_memories]

    def apply_decay(self, memories: List[MemoryItem]) -> List[MemoryItem]:
        """
        Apply decay to memory scores.
        """
        for mem in memories:
            mem.score *= self.decay_rate

        """
        Remove low-score and overflow memories.
        """
        # Step 1: remove low-score memories
        memories = [
            mem for mem in memories if mem.score >= self.min_score
        ]

        # Step 2: enforce capacity (keep the highest score)
        memories.sort(key=lambda x: x.score, reverse=True) #x:x["score"]
        return memories[: self.max_memories]