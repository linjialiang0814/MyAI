import numpy as np
from typing import List, Tuple

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(
        np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)
    )

class MemoryRetriever:
    """
    基于余弦相似度的长期记忆检索器 Step8
    """
    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def retrieve_v1(
            self,
            query_vector: np.ndarray,
            vectors: List[np.ndarray],
            texts: List[str]
    ) -> List[Tuple[str, float]]:

        if not vectors:
            return []

        scores = [
            (texts[i], cosine_similarity(query_vector, vectors[i]))
            for i in range(len(vectors))
        ]

        scores.sort(key=lambda x: x[1], reverse=True) #按余弦相似度排序 取前top_k
        return scores[:self.top_k]
