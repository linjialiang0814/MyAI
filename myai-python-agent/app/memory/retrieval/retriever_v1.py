from typing import List
import numpy as np
from dataclasses import dataclass

from app.memory.store.in_mem_store_v1 import MemoryStore

@dataclass
class RetrievedMemory:
    content: str
    similarity: float
    mem_type: str


class MemoryRetriever:
    def __init__(
            self,
            memory_store: MemoryStore,
            top_k: int = 5
    ):
        self.memory_store = memory_store
        self.top_k = top_k

    def retrieve(self, user_id:str, embed_vec: np.ndarray) -> List[RetrievedMemory]:
        """
        根据用户输入，从长期记忆中检索相似内容，将取出内容的记忆分数置为1
        """
        memories = self.memory_store.get_all(user_id)

        mem_similarity = []

        for mem in memories:
            similarity = self._cosine_similarity(embed_vec, mem.vector)
            mem_similarity.append((mem, similarity))

        top_memories = sorted(mem_similarity, key=lambda x: x[1], reverse=True)[:self.top_k]

        results: List[RetrievedMemory] = []

        for mem, similarity in top_memories:
            mem.score = 1.0
            results.append(
                RetrievedMemory(
                    content=mem.content,
                    similarity=similarity,
                    mem_type=mem.mem_type
                )
            )

        return results

    @staticmethod
    def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        return float(
            np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        )

#完成step9 控制性注入后的 retriever
#在step11 记忆衰减之后做了修改
#记忆分数 score按0.98衰减，且只管内存，这一步将排在前top_k的记忆分数score重新置为 1
