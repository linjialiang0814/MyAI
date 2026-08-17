import hashlib
import numpy as np

class StubEmbedding:
    """
    占位式 Embedding模型
    将文本映射为固定维度向量
    """
    def __init__(self, dim: int = 64):
        self.dim = dim

    def embed(self, text: str):
        h = hashlib.md5(text.encode("utf-8")).hexdigest()
        nums = [int(h[i:i+2], 16) for i in range(0, len(h), 2)]

        if len(nums) < self.dim:
            nums = (nums * ((self.dim//len(nums)) + 1))[:self.dim]

        vec = np.array(nums[:self.dim], dtype = float)
        vec = vec / (np.linalg.norm(vec)+ 1e-8)
        return vec

