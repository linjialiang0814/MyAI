import json
import math
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from app.memory.mem_service import MemoryService
from app.memory.governance import normalize_governance_metadata
from app.memory.retrieval.policy import MemoryPolicy
from app.memory.retrieval.retriever import RetrievedMemory
from app.memory.store.in_mem_store import MemoryStore
from app.memory.writer.extractor import MemoryToWrite
from app.memory.writer.smart_writer import RuleBasedMemoryExtractor, SmartMemoryWriter


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "memory_governance_eval.json"


class EvalEmbedding:
    def embed(self, text: str):
        normalized = text.lower()
        if normalized.startswith("what is"):
            return _unit([0.98, 0.18, 0.0, 0.0])
        if "major" in normalized or "computer science" in normalized or "cs" in normalized:
            return _unit([1.0, 0.0, 0.0, 0.0])
        if "python" in normalized or "javascript" in normalized:
            return _unit([0.0, 1.0, 0.0, 0.0])
        if "password" in normalized:
            return _unit([0.0, 0.0, 1.0, 0.0])
        return _unit([0.0, 0.0, 0.0, 1.0])


def _unit(values):
    vector = np.array(values, dtype=np.float32)
    norm = math.sqrt(float(np.dot(vector, vector)))
    if norm == 0:
        return vector
    return vector / norm


def _retrieved_memory_from_fixture(item: dict) -> RetrievedMemory:
    observed_at = item.get("observed_at", "")
    if "observed_age_days" in item:
        observed_at = (datetime.now(timezone.utc) - timedelta(days=item["observed_age_days"])).isoformat()
    return RetrievedMemory(
        memory_id=item["memory_id"],
        content=item["content"],
        similarity=item["similarity"],
        mem_type=item["mem_type"],
        mem_status=item["mem_status"],
        score=item["score"],
        importance=item.get("importance", 1),
        confidence=item.get("confidence", 1),
        raw_confidence=item.get("raw_confidence", item.get("confidence", 1)),
        slot=item.get("slot", ""),
        retrieval_weight=item.get("retrieval_weight", 1),
        scope=item.get("scope", "global"),
        sensitivity=item.get("sensitivity", "normal"),
        review_status=item.get("review_status", "accepted"),
        source=item.get("source", ""),
        observed_at=observed_at,
        is_current=item.get("is_current", True),
    )


def load_fixture():
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


class FixtureExtractor:
    def __init__(self, candidates: list[dict]):
        self._candidates = candidates

    def extract(self, user_input: str):
        candidates = self.extract_many(user_input)
        return candidates[0] if candidates else None

    def extract_many(self, user_input: str):
        return [
            MemoryToWrite(
                content=item["content"],
                mem_type=item["mem_type"],
                importance=item.get("importance", 1),
                confidence=item.get("confidence", 0.8),
                canonical_key=item.get("canonical_key"),
                canonical_value=item.get("canonical_value"),
                metadata=dict(item.get("metadata", {})),
            )
            for item in self._candidates
        ]


class MemoryGovernanceEvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture()

    def setUp(self):
        self.store = MemoryStore()
        self.service = MemoryService(
            embedding_client=EvalEmbedding(),
            memory_store=self.store,
            writer=SmartMemoryWriter(extractors=[RuleBasedMemoryExtractor()]),
        )

    def test_write_slot_and_pending_cases(self):
        for case in self.fixture["write_cases"]:
            with self.subTest(case=case["id"]):
                user_id = f"eval-write-{case['id']}"
                result = self.service.process_user_input(user_id, case["input"])

                self.assertEqual(result["written"], case["expect_written"])
                if not case["expect_written"]:
                    self.assertEqual(self.store.size(user_id), 0)
                    continue

                memory = self.store.get_by_id(user_id, result["memory_id"])
                self.assertIsNotNone(memory)
                self.assertEqual(memory.mem_type, case["expect_mem_type"])
                self.assertEqual(memory.metadata["slot"], case["expect_slot"])
                self.assertEqual(memory.metadata["value"], case["expect_value"])
                self.assertEqual(memory.metadata["review_status"], case["expect_review_status"])
                if "expect_sensitivity" in case:
                    self.assertEqual(memory.metadata["sensitivity"], case["expect_sensitivity"])
                if "expect_sensitive_category" in case:
                    self.assertEqual(memory.metadata["sensitive_category"], case["expect_sensitive_category"])
                self.assertIn("slot_cardinality", memory.metadata)
                self.assertIn("conflict_policy", memory.metadata)
                self.assertIn("slot_review_confidence_threshold", memory.metadata)
                self.assertIn("slot_multi_candidate_confidence_threshold", memory.metadata)
                self.assertIn("slot_retrieval_weight", memory.metadata)
                if "expect_slot_retrieval_weight" in case:
                    self.assertEqual(memory.metadata["slot_retrieval_weight"], case["expect_slot_retrieval_weight"])
                if "expect_slot_review_confidence_threshold" in case:
                    self.assertEqual(
                        memory.metadata["slot_review_confidence_threshold"],
                        case["expect_slot_review_confidence_threshold"],
                    )
                if "expect_review_reason_contains" in case:
                    self.assertIn(
                        case["expect_review_reason_contains"],
                        memory.metadata.get("review_reason", ""),
                    )
                if "expect_calibrated_confidence_min" in case:
                    self.assertGreaterEqual(
                        memory.metadata["calibrated_confidence"],
                        case["expect_calibrated_confidence_min"],
                    )
                if "expect_calibrated_confidence_max" in case:
                    self.assertLessEqual(
                        memory.metadata["calibrated_confidence"],
                        case["expect_calibrated_confidence_max"],
                    )
                for expected_factor in case.get("expect_calibration_factors_contains", []):
                    self.assertIn(expected_factor, memory.metadata["confidence_calibration_factors"])

    def test_sensitive_cases(self):
        for case in self.fixture["sensitive_cases"]:
            with self.subTest(case=case["id"]):
                metadata = normalize_governance_metadata(
                    base_metadata=case.get("base_metadata", {}),
                    content=case["content"],
                    mem_type=case["mem_type"],
                    confidence=case["confidence"],
                    source=case["source"],
                    importance=case["importance"],
                )

                self.assertEqual(metadata["review_status"], case["expect_review_status"])
                self.assertEqual(metadata["sensitivity"], case["expect_sensitivity"])
                self.assertEqual(metadata["sensitive_category"], case["expect_sensitive_category"])
                self.assertIn(case["expect_review_reason_contains"], metadata["review_reason"])

    def test_multi_candidate_cases(self):
        for case in self.fixture["multi_candidate_cases"]:
            with self.subTest(case=case["id"]):
                service = self.service
                if case.get("mode") == "fixture":
                    service = MemoryService(
                        embedding_client=EvalEmbedding(),
                        memory_store=MemoryStore(),
                        writer=SmartMemoryWriter(extractors=[FixtureExtractor(case["candidates"])]),
                    )
                user_id = f"eval-multi-{case['id']}"
                result = service.process_user_input(user_id, case["input"])

                self.assertEqual(result["candidate_count"], case["expect_candidate_count"])
                self.assertEqual(result["written_count"], case["expect_written_count"])
                memories = service.memory_store.get_all(user_id)
                by_key = {
                    (memory.mem_type, memory.metadata.get("slot"), memory.metadata.get("value")): memory
                    for memory in memories
                }
                for expected in case["expect_memories"]:
                    key = (expected["mem_type"], expected["slot"], expected["value"])
                    self.assertIn(key, by_key)
                    memory = by_key[key]
                    self.assertEqual(memory.metadata["review_status"], expected["review_status"])
                    self.assertEqual(memory.metadata["candidate_count"], case["expect_candidate_count"])
                    self.assertTrue(memory.metadata["multi_candidate"])
                    if "calibrated_confidence_min" in expected:
                        self.assertGreaterEqual(
                            memory.metadata["calibrated_confidence"],
                            expected["calibrated_confidence_min"],
                        )
                    if "calibrated_confidence_max" in expected:
                        self.assertLessEqual(
                            memory.metadata["calibrated_confidence"],
                            expected["calibrated_confidence_max"],
                        )
                    if "review_reason_contains" in expected:
                        self.assertIn(expected["review_reason_contains"], memory.metadata["review_reason"])

    def test_dedup_cases(self):
        for case in self.fixture["dedup_cases"]:
            with self.subTest(case=case["id"]):
                user_id = f"eval-dedup-{case['id']}"
                first = self.service.process_user_input(user_id, case["seed"])
                second = self.service.process_user_input(user_id, case["input"])

                self.assertTrue(first["written"])
                self.assertEqual(second["action"], case["expect_action"])
                self.assertEqual(self.store.size(user_id, active_only=True), case["expect_active_count"])
                if "expect_merged_count" in case:
                    merged = self.store.get_by_id(user_id, second["target_memory_id"])
                    self.assertEqual(merged.metadata["merged_count"], case["expect_merged_count"])
                    self.assertEqual(merged.metadata["last_merge_type"], case["expect_last_merge_type"])
                    self.assertTrue(merged.metadata["last_merged_at"])
                    self.assertTrue(merged.metadata["merge_events"])

    def test_conflict_cases(self):
        for case in self.fixture["conflict_cases"]:
            with self.subTest(case=case["id"]):
                user_id = f"eval-conflict-{case['id']}"
                first = self.service.process_user_input(user_id, case["seed"])
                second = self.service.process_user_input(user_id, case["input"])

                old_memory = self.store.get_by_id(user_id, first["memory_id"])
                new_memory = None
                if second.get("memory_id"):
                    new_memory = self.store.get_by_id(user_id, second["memory_id"])

                self.assertEqual(second["action"], case["expect_action"])
                self.assertEqual(old_memory.status, case["expect_old_status"])
                if case["expect_new_status"] is None:
                    self.assertIsNone(new_memory)
                else:
                    self.assertIsNotNone(new_memory)
                    self.assertEqual(new_memory.status, case["expect_new_status"])
                if "expect_old_current" in case:
                    self.assertEqual(old_memory.metadata["is_current"], case["expect_old_current"])
                    self.assertTrue(old_memory.metadata["valid_to"])
                if "expect_new_current" in case:
                    self.assertEqual(new_memory.metadata["is_current"], case["expect_new_current"])
                    self.assertEqual(new_memory.metadata["previous_memory_id"], old_memory.memory_id)
                if "expect_active_count" in case:
                    self.assertEqual(self.store.size(user_id, active_only=True), case["expect_active_count"])

    def test_temporal_cases(self):
        for case in self.fixture["temporal_cases"]:
            with self.subTest(case=case["id"]):
                user_id = f"eval-temporal-{case['id']}"
                first = self.service.process_user_input(user_id, case["seed"])
                second = self.service.process_user_input(user_id, case["input"])

                old_memory = self.store.get_by_id(user_id, first["memory_id"])
                new_memory = self.store.get_by_id(user_id, second["memory_id"])

                self.assertEqual(second["action"], case["expect_action"])
                self.assertEqual(old_memory.status, case["expect_old_status"])
                self.assertEqual(old_memory.metadata["is_current"], case["expect_old_current"])
                self.assertTrue(old_memory.metadata["valid_to"])
                self.assertEqual(new_memory.status, case["expect_new_status"])
                self.assertEqual(new_memory.metadata["is_current"], case["expect_new_current"])
                if case.get("expect_previous_link"):
                    self.assertEqual(new_memory.metadata["previous_memory_id"], old_memory.memory_id)
                if "expect_old_historical_reason_contains" in case:
                    self.assertIn(
                        case["expect_old_historical_reason_contains"],
                        old_memory.metadata["historical_reason"],
                    )

    def test_citation_cases(self):
        for case in self.fixture["citation_cases"]:
            with self.subTest(case=case["id"]):
                user_id = f"eval-citation-{case['id']}"
                self.service.process_user_input(user_id, case["seed"])
                selected_memories = self.service.retrieve_for_context(user_id, case["query"])
                citations = [
                    {
                        "memory_id": memory.memory_id,
                        "content": memory.content,
                        "mem_type": memory.mem_type,
                        "source": memory.source,
                        "confidence": round(memory.confidence, 4),
                        "scope": memory.scope,
                    }
                    for memory in selected_memories
                ]

                self.assertTrue(citations)
                self.assertEqual(citations[0]["content"], case["expect_citation_content"])
                self.assertEqual(citations[0]["mem_type"], case["expect_citation_type"])

    def test_retrieval_policy_cases(self):
        for case in self.fixture["retrieval_policy_cases"]:
            with self.subTest(case=case["id"]):
                memories = [_retrieved_memory_from_fixture(item) for item in case["memories"]]
                decisions = MemoryPolicy.explain_memories(memories)
                by_id = {decision.memory.memory_id: decision for decision in decisions}
                high = by_id[case["expect_higher_score"]]
                low = by_id[case["expect_lower_score"]]

                self.assertGreater(high.final_score, low.final_score)
                self.assertIn(case["expect_factor"], high.factors)

    def test_calibration_cases(self):
        for case in self.fixture["calibration_cases"]:
            with self.subTest(case=case["id"]):
                metadata = normalize_governance_metadata(
                    base_metadata=case.get("base_metadata", {}),
                    content=case["content"],
                    mem_type=case["mem_type"],
                    confidence=case["confidence"],
                    source=case["source"],
                    importance=case["importance"],
                )

                self.assertEqual(metadata["raw_confidence"], case["confidence"])
                self.assertEqual(metadata["review_status"], case["expect_review_status"])
                if "expect_slot_retrieval_weight" in case:
                    self.assertEqual(metadata["slot_retrieval_weight"], case["expect_slot_retrieval_weight"])
                if "expect_slot_low_importance_review_threshold" in case:
                    self.assertEqual(
                        metadata.get("slot_low_importance_review_threshold"),
                        case["expect_slot_low_importance_review_threshold"],
                    )
                if "expect_calibrated_confidence_min" in case:
                    self.assertGreaterEqual(
                        metadata["calibrated_confidence"],
                        case["expect_calibrated_confidence_min"],
                    )
                if "expect_calibrated_confidence_max" in case:
                    self.assertLessEqual(
                        metadata["calibrated_confidence"],
                        case["expect_calibrated_confidence_max"],
                    )
                for expected_factor in case.get("expect_calibration_factors_contains", []):
                    self.assertIn(expected_factor, metadata["confidence_calibration_factors"])


if __name__ == "__main__":
    unittest.main()
