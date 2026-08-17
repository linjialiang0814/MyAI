from dataclasses import dataclass, field
from typing import Dict, Any
import numpy as np

@dataclass
class MemoryItem:
    content: str
    vector: np.ndarray
    mem_type: str  # e.g. "preference", "fact", "decision"
    score: float
    #引入metadata字段 确保后续系统可扩展性
    metadata: Dict[str, Any] = field(default_factory=dict) #默认为空字典