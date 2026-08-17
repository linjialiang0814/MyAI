import unittest
from datetime import datetime, timedelta, timezone

import numpy as np

from app.memory.maintenance.decay import MemoryDecay
from app.memory.model.mem_item import MemoryItem
from app.memory.store.in_mem_store import MemoryStore


class MemoryDecayScheduleTest(unittest.TestCase):
    def test_repeated_maintenance_on_same_day_does_not_decay_per_message(self):
        now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        store = MemoryStore()
        memory = MemoryItem(
            user_id="u1",
            content="stable preference",
            vector=np.array([1.0], dtype=np.float32),
            mem_type="preference",
            score=0.8,
            last_accessed_at=(now - timedelta(hours=1)).isoformat(),
        )
        store.add_item("u1", memory)
        decay = MemoryDecay(memory_store=store, now_provider=lambda: now)

        decay.apply_decay_by_user("u1")
        first_score = store.get_by_id("u1", memory.memory_id).score
        decay.apply_decay_by_user("u1")
        second_score = store.get_by_id("u1", memory.memory_id).score

        self.assertEqual(first_score, 0.8)
        self.assertEqual(second_score, first_score)
        self.assertEqual(
            store.get_by_id("u1", memory.memory_id).metadata["last_decay_at"],
            memory.last_accessed_at,
        )

    def test_elapsed_days_decay_once_and_second_run_is_idempotent(self):
        now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        store = MemoryStore()
        memory = MemoryItem(
            user_id="u1",
            content="old fact",
            vector=np.array([1.0], dtype=np.float32),
            mem_type="fact",
            score=0.8,
            last_accessed_at=(now - timedelta(days=2, hours=1)).isoformat(),
        )
        store.add_item("u1", memory)
        decay = MemoryDecay(memory_store=store, now_provider=lambda: now)

        decay.apply_decay_by_user("u1")
        first_score = store.get_by_id("u1", memory.memory_id).score
        decay.apply_decay_by_user("u1")

        self.assertAlmostEqual(first_score, 0.8 * ((0.98 * 0.997) ** 2))
        self.assertEqual(store.get_by_id("u1", memory.memory_id).score, first_score)


if __name__ == "__main__":
    unittest.main()
