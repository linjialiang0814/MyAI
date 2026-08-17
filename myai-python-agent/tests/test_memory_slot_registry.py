import unittest
import json

import numpy as np

from app.memory.maintenance.conflict import MemoryConflictResolver
from app.memory.maintenance.dedup import MemoryDeduplicator
from app.memory.model.mem_item import MemoryItem
from app.memory.model.mem_types import MemoryStatus
from app.memory.model.slot_registry import (
    enrich_metadata_with_slot_policy,
    get_slot_definition,
    normalize_slot,
    normalize_value,
)
from app.memory.store.in_mem_store import MemoryStore


def vec(values):
    return np.array(values, dtype=np.float32)


class MemorySlotRegistryTest(unittest.TestCase):
    def test_slot_and_value_normalization(self):
        self.assertEqual(normalize_slot("fact", "profession"), "job")
        self.assertEqual(normalize_slot("fact", "专业"), "major")
        self.assertEqual(normalize_value(" CS "), "computer science")

        definition = get_slot_definition("fact", "profession")
        self.assertEqual(definition.slot, "job")
        self.assertEqual(definition.cardinality, "single")
        self.assertEqual(definition.conflict_policy, "supersede")

    def test_enrich_metadata_with_slot_policy(self):
        metadata = enrich_metadata_with_slot_policy(
            "fact",
            {"slot": "profession", "value": "Engineer"},
        )

        self.assertEqual(metadata["slot"], "job")
        self.assertEqual(metadata["value"], "engineer")
        self.assertEqual(metadata["slot_cardinality"], "single")
        self.assertEqual(metadata["conflict_policy"], "supersede")
        self.assertEqual(metadata["slot_review_confidence_threshold"], 0.7)
        self.assertEqual(metadata["slot_multi_candidate_confidence_threshold"], 0.85)
        self.assertEqual(metadata["slot_retrieval_weight"], 1.1)
        self.assertEqual(metadata["slot_consolidation_policy"], "replace_evidence")
        self.assertNotIn("slot_low_importance_review_threshold", metadata)

    def test_preference_slot_policy_keeps_evidence_when_consolidated(self):
        metadata = enrich_metadata_with_slot_policy(
            "preference",
            {"slot": "like", "value": "Python"},
        )

        self.assertEqual(metadata["slot"], "preference")
        self.assertEqual(metadata["slot_consolidation_policy"], "coexist_with_evidence")

    def test_decision_slot_policy_requires_review_for_low_importance(self):
        metadata = enrich_metadata_with_slot_policy(
            "decision",
            {"slot": "plan", "value": "try a new workflow"},
        )

        self.assertEqual(metadata["slot"], "decision")
        self.assertEqual(metadata["conflict_policy"], "append")
        self.assertEqual(metadata["slot_retrieval_weight"], 1.25)
        self.assertEqual(metadata["slot_low_importance_review_threshold"], 4)

    def test_dedup_uses_normalized_slot_and_value(self):
        store = MemoryStore()
        dedup = MemoryDeduplicator(store)
        user_id = "u-slot-dedup"

        existing = MemoryItem(
            user_id=user_id,
            content="my major is computer science",
            vector=vec([1, 0, 0]),
            mem_type="fact",
            metadata={"slot": "major", "value": "computer science"},
        )
        store.add_item(user_id, existing)

        new = MemoryItem(
            user_id=user_id,
            content="my major is CS",
            vector=vec([0, 1, 0]),
            mem_type="fact",
            metadata={"slot": "专业", "value": "CS"},
        )

        result = dedup.resolve(user_id, new)

        self.assertEqual(result.action, "merge")
        self.assertEqual(result.target_memory_id, existing.memory_id)
        merged = store.get_by_id(user_id, existing.memory_id)
        self.assertEqual(merged.metadata["merged_count"], 1)
        self.assertEqual(merged.metadata["last_merge_type"], "exact")
        self.assertEqual(merged.metadata["last_merge_reason"], "same slot and same value")
        self.assertEqual(json.loads(merged.metadata["merged_from"]), [new.memory_id])
        events = json.loads(merged.metadata["merge_events"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["merged_memory_id"], new.memory_id)
        self.assertEqual(events[0]["incoming_content"], "my major is CS")

    def test_semantic_dedup_records_merge_audit(self):
        store = MemoryStore()
        dedup = MemoryDeduplicator(store, semantic_threshold=0.9)
        user_id = "u-slot-dedup-semantic-audit"

        existing = MemoryItem(
            user_id=user_id,
            content="I prefer concise answers",
            vector=vec([1, 0, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": ""},
        )
        store.add_item(user_id, existing)

        new = MemoryItem(
            user_id=user_id,
            content="Please keep answers concise",
            vector=vec([0.98, 0.02, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": "", "source": "chat_extraction"},
        )

        result = dedup.resolve(user_id, new)
        merged = store.get_by_id(user_id, existing.memory_id)

        self.assertEqual(result.action, "merge")
        self.assertEqual(merged.metadata["merged_count"], 1)
        self.assertEqual(merged.metadata["last_merge_type"], "semantic")
        self.assertIn("semantic duplicate", merged.metadata["last_merge_reason"])
        events = json.loads(merged.metadata["merge_events"])
        self.assertEqual(events[0]["merge_type"], "semantic")
        self.assertIn("similarity", events[0])

    def test_dedup_bypasses_negation_candidates(self):
        store = MemoryStore()
        dedup = MemoryDeduplicator(store)
        user_id = "u-slot-dedup-negation"

        existing = MemoryItem(
            user_id=user_id,
            content="I like Python",
            vector=vec([1, 0, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": "python"},
        )
        store.add_item(user_id, existing)

        new = MemoryItem(
            user_id=user_id,
            content="I no longer like Python",
            vector=vec([0, 1, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": "python", "update_intent": "negation"},
        )

        result = dedup.resolve(user_id, new)

        self.assertEqual(result.action, "add")
        self.assertIn("negation", result.reason)

    def test_conflict_policy_supersedes_single_value_fact(self):
        store = MemoryStore()
        resolver = MemoryConflictResolver(store)
        user_id = "u-slot-conflict"

        existing = MemoryItem(
            user_id=user_id,
            content="my major is computer science",
            vector=vec([1, 0, 0]),
            mem_type="fact",
            metadata={"slot": "major", "value": "computer science"},
        )
        store.add_item(user_id, existing)

        new = MemoryItem(
            user_id=user_id,
            content="my major is artificial intelligence",
            vector=vec([0, 1, 0]),
            mem_type="fact",
            metadata={"slot": "major", "value": "artificial intelligence"},
        )

        result = resolver.resolve(user_id, new)
        old = store.get_by_id(user_id, existing.memory_id)

        self.assertEqual(result.action, "supersede")
        self.assertEqual(old.status, MemoryStatus.SUPERSEDED.value)
        self.assertEqual(old.metadata["is_current"], False)
        self.assertTrue(old.metadata["valid_to"])
        self.assertEqual(new.metadata["is_current"], True)
        self.assertEqual(new.metadata["previous_memory_id"], existing.memory_id)

    def test_correction_intent_is_preserved_in_conflict_history(self):
        store = MemoryStore()
        resolver = MemoryConflictResolver(store)
        user_id = "u-slot-correction"

        existing = MemoryItem(
            user_id=user_id,
            content="I live in Chengdu",
            vector=vec([1, 0, 0]),
            mem_type="fact",
            metadata={"slot": "location", "value": "chengdu", "is_current": True},
        )
        store.add_item(user_id, existing)

        new = MemoryItem(
            user_id=user_id,
            content="I moved to Shanghai",
            vector=vec([0, 1, 0]),
            mem_type="fact",
            metadata={"slot": "location", "value": "shanghai", "update_intent": "correction"},
        )

        result = resolver.resolve(user_id, new)
        old = store.get_by_id(user_id, existing.memory_id)

        self.assertEqual(result.action, "supersede")
        self.assertIn("correction", result.reason)
        self.assertEqual(old.metadata["historical_reason"], "corrected by newer value for slot 'location'")
        self.assertEqual(new.metadata["correction_applied"], True)

    def test_conflict_policy_allows_multi_value_preference(self):
        store = MemoryStore()
        resolver = MemoryConflictResolver(store)
        user_id = "u-slot-preference"

        existing = MemoryItem(
            user_id=user_id,
            content="I like Python",
            vector=vec([1, 0, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": "python"},
        )
        store.add_item(user_id, existing)

        new = MemoryItem(
            user_id=user_id,
            content="I like JavaScript",
            vector=vec([0, 1, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": "javascript"},
        )

        result = resolver.resolve(user_id, new)
        old = store.get_by_id(user_id, existing.memory_id)

        self.assertEqual(result.action, "add")
        self.assertEqual(old.status, MemoryStatus.ACTIVE.value)

    def test_negation_supersedes_matching_multi_value_preference(self):
        store = MemoryStore()
        resolver = MemoryConflictResolver(store)
        user_id = "u-slot-preference-negation"

        existing = MemoryItem(
            user_id=user_id,
            content="I like Python",
            vector=vec([1, 0, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": "python", "is_current": True},
        )
        store.add_item(user_id, existing)

        new = MemoryItem(
            user_id=user_id,
            content="I no longer like Python",
            vector=vec([0, 1, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": "python", "update_intent": "negation"},
        )

        result = resolver.resolve(user_id, new)
        old = store.get_by_id(user_id, existing.memory_id)

        self.assertEqual(result.action, "negate")
        self.assertEqual(result.target_memory_id, existing.memory_id)
        self.assertEqual(old.status, MemoryStatus.SUPERSEDED.value)
        self.assertEqual(old.metadata["is_current"], False)
        self.assertEqual(old.metadata["historical_reason"], "negated by user for slot 'preference'")
        self.assertEqual(new.metadata["negation_applied"], True)

    def test_negation_without_matching_value_stays_pending(self):
        store = MemoryStore()
        resolver = MemoryConflictResolver(store)
        user_id = "u-slot-preference-negation-miss"

        new = MemoryItem(
            user_id=user_id,
            content="I no longer like Python",
            vector=vec([0, 1, 0]),
            mem_type="preference",
            metadata={"slot": "preference", "value": "python", "update_intent": "negation"},
        )

        result = resolver.resolve(user_id, new)

        self.assertEqual(result.action, "add")
        self.assertEqual(new.metadata["review_status"], "pending")
        self.assertIn("negation found no existing value", new.metadata["review_reason"])


if __name__ == "__main__":
    unittest.main()
