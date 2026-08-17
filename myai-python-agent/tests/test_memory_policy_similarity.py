import math
import unittest

from app.memory.retrieval.policy import MemoryPolicy
from app.memory.retrieval.retriever import RetrievedMemory


class MemoryPolicySimilarityTest(unittest.TestCase):
    def _memory(self, similarity: float) -> RetrievedMemory:
        return RetrievedMemory(
            memory_id="memory-1",
            content="my project code is ORION-742",
            similarity=similarity,
            mem_type="fact",
            mem_status="active",
            score=0.9,
            importance=5,
            confidence=0.95,
            review_status="accepted",
            source="user_explicit",
        )

    def test_exact_cosine_match_is_eligible(self):
        decisions = MemoryPolicy.explain_memories([self._memory(1.0)])

        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0].selected)

    def test_invalid_similarity_above_tolerance_is_rejected(self):
        decisions = MemoryPolicy.explain_memories([self._memory(1.01)])

        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0].selected)
        self.assertIn("outside", decisions[0].reason)

    def test_non_finite_similarity_is_rejected(self):
        for similarity in (math.nan, math.inf, -math.inf):
            with self.subTest(similarity=similarity):
                decisions = MemoryPolicy.explain_memories([self._memory(similarity)])

                self.assertEqual(len(decisions), 1)
                self.assertFalse(decisions[0].selected)
                self.assertIn("outside", decisions[0].reason)


if __name__ == "__main__":
    unittest.main()
