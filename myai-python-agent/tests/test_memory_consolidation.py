import copy
import json
import unittest

import numpy as np

from app.memory.maintenance.consolidation import MemoryConsolidator
from app.memory.maintenance.decay import MemoryDecay
from app.memory.mem_service import MemoryService
from app.memory.model.mem_item import MemoryItem
from app.memory.model.mem_types import MemoryStatus
from app.memory.store.in_mem_store import MemoryStore
from app.memory.writer.extractor import MemoryToWrite


def vec(values):
    return np.array(values, dtype=np.float32)


class DummyEmbedding:
    def embed(self, text: str):
        if "python" in text.lower():
            return vec([1, 0, 0])
        if "javascript" in text.lower():
            return vec([0, 1, 0])
        return vec([0.5, 0.5, 0])


class CopyingFailureStore(MemoryStore):
    """Mimic a persistence store and fail one selected update call."""

    def __init__(self, *, fail_update_call: int | None = None):
        super().__init__()
        self.fail_update_call = fail_update_call
        self.update_calls = 0

    def add_item(self, user_id: str, memory_item: MemoryItem) -> str:
        return super().add_item(user_id, copy.deepcopy(memory_item))

    def get_all(self, user_id: str, active_only: bool = False):
        return copy.deepcopy(super().get_all(user_id, active_only=active_only))

    def update_memory(self, user_id: str, memory_item: MemoryItem) -> bool:
        self.update_calls += 1
        if self.update_calls == self.fail_update_call:
            raise RuntimeError("injected storage interruption")
        return super().update_memory(user_id, copy.deepcopy(memory_item))


def memory(content: str, *, mem_type: str, slot: str, value: str, vector=None, status="active", current=True):
    return MemoryItem(
        content=content,
        vector=vec(vector or [1, 0, 0]),
        mem_type=mem_type,
        status=status,
        score=0.8,
        importance=5,
        metadata={
            "slot": slot,
            "value": value,
            "review_status": "accepted",
            "sensitivity": "personal",
            "source": "user_explicit",
            "confidence": 0.9,
            "raw_confidence": 0.9,
            "calibrated_confidence": 0.9,
            "is_current": current,
            "valid_from": "2025-01-01T00:00:00+00:00",
            "valid_to": "" if current else "2025-06-01T00:00:00+00:00",
        },
    )


class MemoryConsolidationTest(unittest.TestCase):
    def test_repeated_observations_create_audited_summary_and_supersede_evidence(self):
        store = MemoryStore()
        user_id = "u-consolidate-repeat"
        first = memory("my major is computer science", mem_type="fact", slot="major", value="computer science")
        second = memory("I study CS", mem_type="fact", slot="major", value="computer science", vector=[0.9, 0.1, 0])
        store.add_item(user_id, first)
        store.add_item(user_id, second)

        report = MemoryConsolidator(store).consolidate_user(user_id)
        memories = store.get_all(user_id)
        summaries = [mem for mem in memories if mem.metadata.get("consolidation_summary")]

        self.assertEqual(report.created_count, 1)
        self.assertEqual(len(summaries), 1)
        summary = summaries[0]
        self.assertEqual(summary.metadata["consolidation_kind"], "repeated_observation")
        self.assertEqual(summary.metadata["consolidation_policy"], "replace_evidence")
        self.assertEqual(summary.metadata["consolidation_evidence_action"], "supersede_evidence")
        self.assertEqual(summary.metadata["consolidated_count"], 2)
        self.assertEqual(set(json.loads(summary.metadata["consolidated_from"])), {first.memory_id, second.memory_id})
        self.assertTrue(json.loads(summary.metadata["consolidation_events"]))
        self.assertEqual(first.status, MemoryStatus.SUPERSEDED.value)
        self.assertEqual(second.status, MemoryStatus.SUPERSEDED.value)
        self.assertEqual(first.metadata["consolidated_into"], summary.memory_id)
        self.assertEqual(first.metadata["consolidation_policy"], "replace_evidence")
        self.assertFalse(first.metadata["is_current"])

    def test_long_term_preferences_create_summary_and_keep_evidence_current(self):
        store = MemoryStore()
        user_id = "u-consolidate-preference"
        first = memory("I like Python", mem_type="preference", slot="preference", value="python")
        second = memory("I like JavaScript", mem_type="preference", slot="preference", value="javascript", vector=[0, 1, 0])
        store.add_item(user_id, first)
        store.add_item(user_id, second)

        report = MemoryConsolidator(store).consolidate_user(user_id)
        summaries = [mem for mem in store.get_all(user_id) if mem.metadata.get("consolidation_summary")]

        self.assertEqual(report.created_count, 1)
        self.assertEqual(summaries[0].metadata["consolidation_kind"], "long_term_preference")
        self.assertEqual(summaries[0].metadata["consolidation_policy"], "coexist_with_evidence")
        self.assertEqual(summaries[0].metadata["consolidation_evidence_action"], "link_evidence_only")
        self.assertIn("javascript", summaries[0].content)
        self.assertIn("python", summaries[0].content)
        self.assertEqual(first.status, MemoryStatus.ACTIVE.value)
        self.assertEqual(second.status, MemoryStatus.ACTIVE.value)
        self.assertTrue(first.metadata["is_current"])
        self.assertEqual(first.metadata["consolidated_into"], summaries[0].memory_id)
        self.assertEqual(first.metadata["consolidation_policy"], "coexist_with_evidence")

    def test_historical_fact_chain_summary_preserves_current_fact(self):
        store = MemoryStore()
        user_id = "u-consolidate-history"
        old = memory(
            "I lived in Shanghai",
            mem_type="fact",
            slot="location",
            value="shanghai",
            status="superseded",
            current=False,
        )
        current = memory("I live in Beijing", mem_type="fact", slot="location", value="beijing")
        store.add_item(user_id, old)
        store.add_item(user_id, current)

        report = MemoryConsolidator(store).consolidate_user(user_id)
        summaries = [mem for mem in store.get_all(user_id) if mem.metadata.get("consolidation_summary")]

        self.assertEqual(report.created_count, 1)
        self.assertEqual(summaries[0].metadata["consolidation_kind"], "historical_fact_chain")
        self.assertEqual(summaries[0].metadata["consolidation_policy"], "coexist_with_evidence")
        self.assertIn("shanghai -> beijing", summaries[0].content)
        self.assertEqual(current.status, MemoryStatus.ACTIVE.value)
        self.assertTrue(current.metadata["is_current"])

    def test_decay_preserves_historical_evidence(self):
        store = MemoryStore()
        user_id = "u-consolidate-decay"
        historical = memory(
            "old fact",
            mem_type="fact",
            slot="location",
            value="old",
            status="superseded",
            current=False,
        )
        low_score = memory("low score", mem_type="fact", slot="job", value="x")
        low_score.score = 0.01
        store.add_item(user_id, historical)
        store.add_item(user_id, low_score)

        remaining = MemoryDecay(memory_store=store).apply_decay_by_user(user_id)

        self.assertIn(historical.memory_id, {mem.memory_id for mem in remaining})
        self.assertNotIn(low_score.memory_id, {mem.memory_id for mem in remaining})

    def test_service_maintenance_returns_consolidation_report(self):
        store = MemoryStore()
        user_id = "u-consolidate-service"
        store.add_item(user_id, memory("I like Python", mem_type="preference", slot="preference", value="python"))
        store.add_item(
            user_id,
            memory("I like JavaScript", mem_type="preference", slot="preference", value="javascript", vector=[0, 1, 0]),
        )
        service = MemoryService(embedding_client=DummyEmbedding(), memory_store=store)

        result = service.maintenance(user_id)

        self.assertEqual(result["consolidation"]["created_count"], 1)
        action = result["consolidation"]["actions"][0]
        self.assertEqual(action["policy"], "coexist_with_evidence")
        self.assertEqual(action["evidence_action"], "link_evidence_only")
        self.assertEqual(action["replaced_evidence_count"], 0)
        self.assertEqual(action["linked_evidence_count"], 2)
        self.assertGreaterEqual(result["memory_count"], 3)

    def test_interrupted_summary_is_repaired_without_duplicate(self):
        store = CopyingFailureStore(fail_update_call=2)
        user_id = "u-consolidate-repair"
        first = memory("my major is computer science", mem_type="fact", slot="major", value="computer science")
        second = memory("I study CS", mem_type="fact", slot="major", value="computer science", vector=[0.9, 0.1, 0])
        store.add_item(user_id, first)
        store.add_item(user_id, second)

        with self.assertRaisesRegex(RuntimeError, "storage interruption"):
            MemoryConsolidator(store).consolidate_user(user_id)

        interrupted = store.get_all(user_id)
        summaries = [item for item in interrupted if item.metadata.get("consolidation_summary")]
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].metadata["consolidation_state"], "pending")
        self.assertFalse(summaries[0].metadata["retrieval_enabled"])
        self.assertEqual(
            sum(item.status == MemoryStatus.SUPERSEDED.value for item in interrupted if not item.metadata.get("consolidation_summary")),
            1,
        )

        store.fail_update_call = None
        MemoryConsolidator(store).consolidate_user(user_id)

        repaired = store.get_all(user_id)
        summaries = [item for item in repaired if item.metadata.get("consolidation_summary")]
        evidence = [item for item in repaired if not item.metadata.get("consolidation_summary")]
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].metadata["consolidation_state"], "complete")
        self.assertTrue(summaries[0].metadata["retrieval_enabled"])
        self.assertTrue(all(item.status == MemoryStatus.SUPERSEDED.value for item in evidence))
        self.assertTrue(all(item.metadata["consolidated_into"] == summaries[0].memory_id for item in evidence))

    def test_degraded_summary_releases_evidence_and_allows_healthy_rebuild(self):
        store = CopyingFailureStore()
        user_id = "u-consolidate-degraded-rebuild"
        first = memory("my major is computer science", mem_type="fact", slot="major", value="computer science")
        lost = memory("I study CS", mem_type="fact", slot="major", value="computer science", vector=[0.9, 0.1, 0])
        store.add_item(user_id, first)
        store.add_item(user_id, lost)

        MemoryConsolidator(store).consolidate_user(user_id)
        original_summary = next(
            item for item in store.get_all(user_id) if item.metadata.get("consolidation_summary")
        )
        self.assertTrue(store.delete_by_id(user_id, lost.memory_id))

        MemoryConsolidator(store).consolidate_user(user_id)
        released = store.get_by_id(user_id, first.memory_id)
        degraded = store.get_by_id(user_id, original_summary.memory_id)
        self.assertEqual(degraded.metadata["consolidation_state"], "degraded")
        self.assertFalse(degraded.metadata["retrieval_enabled"])
        self.assertEqual(released.status, MemoryStatus.ACTIVE.value)
        self.assertTrue(released.metadata["is_current"])
        self.assertEqual(released.metadata["consolidated_into"], "")

        replacement = memory(
            "My field remains CS",
            mem_type="fact",
            slot="major",
            value="computer science",
            vector=[0.95, 0.05, 0],
        )
        store.add_item(user_id, replacement)
        report = MemoryConsolidator(store).consolidate_user(user_id)

        summaries = [
            item for item in store.get_all(user_id) if item.metadata.get("consolidation_summary")
        ]
        healthy = [item for item in summaries if item.metadata.get("consolidation_state") == "complete"]
        self.assertEqual(report.created_count, 1)
        self.assertEqual(len(summaries), 2)
        self.assertEqual(len(healthy), 1)
        self.assertTrue(healthy[0].metadata["retrieval_enabled"])
        self.assertEqual(
            set(json.loads(healthy[0].metadata["consolidated_from"])),
            {first.memory_id, replacement.memory_id},
        )
        rebuilt_evidence = [store.get_by_id(user_id, first.memory_id), store.get_by_id(user_id, replacement.memory_id)]
        self.assertTrue(all(item.status == MemoryStatus.SUPERSEDED.value for item in rebuilt_evidence))
        self.assertTrue(all(item.metadata["consolidated_into"] == healthy[0].memory_id for item in rebuilt_evidence))

    def test_conflict_update_failure_removes_new_value_and_keeps_old_current(self):
        store = CopyingFailureStore(fail_update_call=1)
        user_id = "u-conflict-compensation"
        old = memory("I live in Chengdu", mem_type="fact", slot="location", value="chengdu")
        store.add_item(user_id, old)
        service = MemoryService(embedding_client=DummyEmbedding(), memory_store=store)
        candidate = MemoryToWrite(
            content="I live in Shanghai",
            mem_type="fact",
            importance=5,
            confidence=0.95,
            canonical_key="location",
            canonical_value="shanghai",
            metadata={"slot": "location", "value": "shanghai", "update_intent": "correction"},
        )

        with self.assertRaisesRegex(RuntimeError, "storage interruption"):
            service._process_candidate(
                user_id,
                candidate,
                candidate_index=1,
                candidate_count=1,
                extraction_batch_id="",
                conversation_id=1,
                message_id="m-1",
                source="chat_extraction",
            )

        remaining = store.get_all(user_id)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].memory_id, old.memory_id)
        self.assertEqual(remaining[0].status, MemoryStatus.ACTIVE.value)
        self.assertTrue(remaining[0].metadata["is_current"])


if __name__ == "__main__":
    unittest.main()
