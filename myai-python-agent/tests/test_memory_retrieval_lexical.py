import unittest
from dataclasses import dataclass, field

import numpy as np

from app.memory.retrieval.retriever import MemoryRetriever


@dataclass
class FakeMemory:
    content: str
    mem_type: str
    memory_id: str
    vector: np.ndarray
    user_id: str = "u1"
    status: str = "active"
    score: float = 0.5
    importance: float = 1.0
    metadata: dict = field(default_factory=dict)


class TinyStore:
    def __init__(self, memories, vector_hits=None):
        self.memories = memories
        self.vector_hits = vector_hits

    def query_similar(self, user_id, query_vector, top_k):
        return self.vector_hits if self.vector_hits is not None else [(self.memories[0], 0.4)]

    def get_all(self, user_id):
        return self.memories


class MemoryRetrievalLexicalTest(unittest.TestCase):
    def test_lexical_match_is_merged_with_vector_candidates(self):
        first = FakeMemory(
            content="I like Obsidian",
            mem_type="preference",
            memory_id="m1",
            vector=np.ones(4),
        )
        second = FakeMemory(
            content="Phase8 frontend memory smoke marker",
            mem_type="general",
            memory_id="m2",
            vector=np.ones(4),
        )
        retriever = MemoryRetriever(TinyStore([first, second]), top_k=3)

        results = retriever.retrieve("u1", np.ones(4), query_text="Phase8 frontend memory smoke marker")

        contents = [item.content for item in results]
        self.assertIn("Phase8 frontend memory smoke marker", contents)
        matched = next(item for item in results if item.content == "Phase8 frontend memory smoke marker")
        self.assertGreaterEqual(matched.similarity, 0.99)

    def test_lexical_match_boosts_existing_vector_candidate(self):
        first = FakeMemory(
            content="Phase8 frontend memory smoke marker",
            mem_type="general",
            memory_id="m1",
            vector=np.ones(4),
        )
        retriever = MemoryRetriever(TinyStore([first], vector_hits=[(first, 0.3)]), top_k=3)

        results = retriever.retrieve("u1", np.ones(4), query_text="Phase8 frontend memory smoke marker")

        self.assertEqual(results[0].content, "Phase8 frontend memory smoke marker")
        self.assertGreaterEqual(results[0].similarity, 0.99)


if __name__ == "__main__":
    unittest.main()
