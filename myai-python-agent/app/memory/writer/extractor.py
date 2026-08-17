from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol


@dataclass
class MemoryToWrite:
    content: str
    mem_type: str
    importance: int = 1
    confidence: float = 0.8
    canonical_key: Optional[str] = None
    canonical_value: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class StructuredMemoryExtractor(Protocol):
    def extract(self, user_input: str) -> Optional[MemoryToWrite]:
        """Return one structured memory candidate, or None when input should not be written."""
        ...

    def extract_many(self, user_input: str) -> list[MemoryToWrite]:
        """Return zero or more structured memory candidates."""
        ...
