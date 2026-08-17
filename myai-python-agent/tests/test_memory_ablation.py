import unittest
from pathlib import Path
from uuid import uuid4

import numpy as np

from app.experiments.memory_ablation import retrieve_memory_evidence
from tests import TEST_DATA_ROOT


class LocationEmbedding:
    def __init__(self):
        self.calls = 0

    def embed(self, text: str):
        self.calls += 1
        normalized = text.lower()
        if any(token in normalized for token in ("live", "moved", "where")):
            return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        return np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)


CASE = {
    "id": "location",
    "query": "Where do I live now?",
    "observations": [
        {
            "id": "old",
            "content": "I live in Suzhou",
            "mem_type": "fact",
            "slot": "location",
            "value": "suzhou",
            "confidence": 0.95,
            "importance": 5,
        },
        {
            "id": "new",
            "content": "I moved to Nanjing",
            "mem_type": "fact",
            "slot": "location",
            "value": "nanjing",
            "confidence": 0.97,
            "importance": 5,
            "metadata": {"update_intent": "correction"},
        },
    ],
}


class MemoryAblationTest(unittest.TestCase):
    def test_none_never_calls_embedding(self):
        embedding = LocationEmbedding()
        temp = TEST_DATA_ROOT / f"memory-none-{uuid4()}"
        temp.mkdir()
        result = retrieve_memory_evidence(
            variant="none",
            case=CASE,
            embedding_client=embedding,
            top_k=3,
            settings_dir=temp,
        )

        self.assertEqual(result["evidence"], [])
        self.assertEqual(embedding.calls, 0)

    def test_basic_keeps_conflicting_flat_memories(self):
        temp = TEST_DATA_ROOT / f"memory-basic-{uuid4()}"
        temp.mkdir()
        result = retrieve_memory_evidence(
            variant="basic",
            case=CASE,
            embedding_client=LocationEmbedding(),
            top_k=3,
            settings_dir=temp,
        )

        selected = {item["observation_id"] for item in result["evidence"]}
        self.assertEqual(selected, {"old", "new"})

    def test_governed_selects_current_fact_only(self):
        temp = TEST_DATA_ROOT / f"memory-governed-{uuid4()}"
        temp.mkdir()
        result = retrieve_memory_evidence(
            variant="governed",
            case=CASE,
            embedding_client=LocationEmbedding(),
            top_k=3,
            settings_dir=temp,
        )

        selected = [item["observation_id"] for item in result["evidence"]]
        self.assertEqual(selected, ["new"])
        self.assertTrue(result["evidence"][0]["is_current"])


if __name__ == "__main__":
    unittest.main()
