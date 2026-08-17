from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

import numpy as np

from app.memory.model.mem_types import MemoryType, MemoryStatus

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class MemoryItem:
    memory_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    content: str = ""
    vector: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    mem_type: str = MemoryType.GENERAL.value
    score: float = 1.0 # used for decay

    importance: float = 1.0
    created_at: str = field(default_factory=utc_now_iso)
    last_accessed_at: str = field(default_factory=utc_now_iso)
    access_count: int = 0
    status: str = MemoryStatus.ACTIVE.value

    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self, reinforcement: float = 0.1, max_score: float = 1.0) -> None:
        self.last_accessed_at = utc_now_iso()
        self.access_count += 1
        self.score = min(max_score, self.score + reinforcement)

    def to_metadata(self) -> Dict[str, Any]:
        meta = dict(self.metadata) if self.metadata else {}
        meta.update(
            {
                "memory_id": self.memory_id,
                "user_id": self.user_id,
                "mem_type": self.mem_type,
                "score": float(self.score),
                "importance": float(self.importance),
                "created_at": self.created_at,
                "last_accessed_at": self.last_accessed_at,
                "access_count": int(self.access_count),
                "status": self.status,
            }
        )
        return meta

    @classmethod
    def from_metadata(cls,
                      *,
                      content: str,
                      vector: np.ndarray,
                      metadata: Dict[str, Any] | None,
                      ) -> "MemoryItem":
        meta = dict(metadata or {})
        reserved = {
            "memory_id",
            "user_id",
            "mem_type",
            "score",
            "importance",
            "created_at",
            "last_accessed_at",
            "access_count",
            "status",
        }
        extra = {k: v for k, v in meta.items() if k not in reserved}
        return cls(
            memory_id = str(meta.get("memory_id", str(uuid4()))),
            user_id = str(meta.get("user_id", "")),
            content = content,
            vector = np.array(vector, dtype = np.float32),
            mem_type = str(meta.get("mem_type", "general")),
            score = float(meta.get("score", 1.0)),
            importance = float(meta.get("importance", 1.0)),
            created_at = str(meta.get("created_at", utc_now_iso())),
            last_accessed_at = str(meta.get("last_accessed_at", utc_now_iso())),
            access_count = int(meta.get("access_count", 0)),
            status = str(meta.get("status", "active")),
            metadata = extra,
        )