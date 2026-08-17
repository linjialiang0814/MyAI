from typing import Dict, List
import numpy as np

class MemoryStore:
    """
    内存级长期记忆存储 Step8
    """
    def __init__(self):
        self.vectors: Dict[str, List[np.ndarray]] = {}
        self.texts: Dict[str, List[str]] = {}

    def add(self, user_id: str, vector: np.ndarray, text: str):
        if user_id not in self.vectors:
            self.vectors[user_id] = []
            self.texts[user_id] = []

        self.vectors[user_id].append(vector)
        self.texts[user_id].append(text)

    def get_user_memory(self, user_id: str):
        return self.vectors.get(user_id, []), self.texts.get(user_id, [])
