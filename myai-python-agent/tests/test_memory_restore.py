import unittest

import numpy as np

from app.memory.mem_service import MemoryService
from app.memory.model.mem_item import MemoryItem
from app.memory.model.mem_types import MemoryStatus
from app.memory.store.in_mem_store import MemoryStore


class StubEmbedding:
    def embed(self, text: str) -> np.ndarray:
        return np.array([1.0, 0.0, 0.0], dtype=np.float32)


class MemoryRestoreTest(unittest.TestCase):
    def test_marking_superseded_memory_current_restores_active_status(self):
        user_id = "u-memory-restore"
        store = MemoryStore()
        memory = MemoryItem(
            user_id=user_id,
            content="I prefer concise answers",
            vector=np.array([1.0, 0.0, 0.0], dtype=np.float32),
            mem_type="preference",
            status=MemoryStatus.SUPERSEDED.value,
            metadata={"is_current": False, "valid_to": "2026-01-01T00:00:00+00:00"},
        )
        store.add_item(user_id, memory)
        service = MemoryService(embedding_client=StubEmbedding(), memory_store=store)

        restored = service.edit_memory(user_id, memory.memory_id, is_current=True)

        self.assertIsNotNone(restored)
        self.assertEqual(restored.status, MemoryStatus.ACTIVE.value)
        self.assertTrue(restored.metadata["is_current"])
        self.assertEqual(restored.metadata["valid_to"], "")


if __name__ == "__main__":
    unittest.main()
