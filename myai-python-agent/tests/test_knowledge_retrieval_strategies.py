import copy
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import chromadb
import numpy as np

from app.knowledge.service import HYBRID_FUSION_VERSION, KnowledgeService
from tests import TEST_DATA_ROOT


def _candidate(
    chunk_id: str,
    *,
    vector_score: float = 0.0,
    keyword_score: float = 0.0,
    source: str,
    file_id: str = "file-a",
    content: str = "background text",
) -> dict:
    return {
        "chunk_id": chunk_id,
        "content": content,
        "metadata": {
            "file_id": file_id,
            "file_name": f"{file_id}.txt",
            "chunk_index": 0,
            "char_start": 0,
            "char_end": len(content),
            "token_estimate": 80,
            "uploaded_at": "",
        },
        "vector_score": vector_score,
        "keyword_score": keyword_score,
        "retrieval_sources": {source},
    }


class _StrategyService(KnowledgeService):
    def __init__(self, vector_candidates: list[dict], keyword_candidates: list[dict]):
        self.vector_fixture = vector_candidates
        self.keyword_fixture = keyword_candidates
        self.keyword_calls = 0

    def _vector_candidates(self, query, where, top_k):
        return copy.deepcopy(self.vector_fixture)

    def _keyword_candidates(self, user_id, query, file_id=None):
        self.keyword_calls += 1
        return copy.deepcopy(self.keyword_fixture)


class _ExplicitEmbedding:
    def embed(self, text):
        vector = np.array([len(text) + 1, 2.0, 3.0, 4.0], dtype=np.float32)
        return vector / np.linalg.norm(vector)


class KnowledgeRetrievalStrategyTest(unittest.TestCase):
    def setUp(self):
        self.vector_candidates = [
            _candidate("vector-low", vector_score=0.2, source="vector"),
            _candidate("vector-high", vector_score=0.9, source="vector"),
        ]
        self.keyword_candidates = [
            _candidate(
                "keyword-only",
                keyword_score=1.0,
                source="keyword",
                file_id="file-b",
                content="ZXQ9000 exact keyword evidence",
            )
        ]

    def test_vector_uses_only_vector_candidates_and_vector_ranking(self):
        service = _StrategyService(self.vector_candidates, self.keyword_candidates)

        hits = service.query("user-1", "ZXQ9000", top_k=2, retrieval_strategy="vector")

        self.assertEqual([hit["chunk_id"] for hit in hits], ["vector-high", "vector-low"])
        self.assertEqual(service.keyword_calls, 0)
        for hit in hits:
            self.assertEqual(hit["retrieval_strategy"], "vector")
            self.assertFalse(hit["rerank_applied"])
            self.assertEqual(hit["fusion_version"], "none")
            self.assertEqual(hit["retrieval_score"], hit["vector_score"])
            self.assertEqual(hit["selection_explanation"]["ranking_field"], "vector_score")

    def test_hybrid_fuses_vector_and_keyword_candidates_without_rerank(self):
        service = _StrategyService(self.vector_candidates, self.keyword_candidates)

        hits = service.query("user-1", "ZXQ9000", top_k=3, retrieval_strategy="hybrid")

        self.assertEqual(service.keyword_calls, 1)
        self.assertEqual(hits[0]["chunk_id"], "keyword-only")
        self.assertEqual({hit["chunk_id"] for hit in hits}, {"vector-low", "vector-high", "keyword-only"})
        for hit in hits:
            self.assertEqual(hit["retrieval_strategy"], "hybrid")
            self.assertFalse(hit["rerank_applied"])
            self.assertEqual(hit["fusion_version"], HYBRID_FUSION_VERSION)
            self.assertEqual(hit["rerank_score"], 0.0)
            self.assertEqual(hit["selection_explanation"]["ranking_field"], "retrieval_score")
            self.assertEqual(hit["selection_explanation"]["max_context_tokens"], 1350)

    def test_default_strategy_matches_explicit_hybrid_rerank(self):
        service = _StrategyService(self.vector_candidates, self.keyword_candidates)

        default_hits = service.query("user-1", "ZXQ9000", top_k=2)
        explicit_hits = service.query("user-1", "ZXQ9000", top_k=2, retrieval_strategy="hybrid_rerank")

        self.assertEqual(default_hits, explicit_hits)
        self.assertTrue(all(hit["rerank_applied"] for hit in default_hits))
        self.assertTrue(all(hit["retrieval_strategy"] == "hybrid_rerank" for hit in default_hits))
        self.assertTrue(all(hit["fusion_version"] == HYBRID_FUSION_VERSION for hit in default_hits))
        self.assertTrue(all(hit["selection_explanation"]["max_chunks_per_file"] == 1 for hit in default_hits))

    def test_unknown_strategy_is_rejected(self):
        service = _StrategyService(self.vector_candidates, self.keyword_candidates)

        with self.assertRaisesRegex(ValueError, "Unsupported retrieval strategy"):
            service.query("user-1", "query", retrieval_strategy="bm25")

    def test_explicit_experiment_dependencies_ignore_poisoned_application_env(self):
        base_dir = TEST_DATA_ROOT / f"knowledge-explicit-{uuid4()}"
        client = chromadb.EphemeralClient(
            settings=chromadb.config.Settings(anonymized_telemetry=False)
        )
        poisoned = {
            "MYAI_LLM_TEMPERATURE": "not-a-number",
            "MYAI_LLM_TIMEOUT_SECONDS": "also-not-a-number",
        }
        with patch.dict(os.environ, poisoned, clear=False):
            service = KnowledgeService(
                base_dir=str(base_dir),
                embedding_client=_ExplicitEmbedding(),
                collection_name=f"explicit_{uuid4().hex}",
                chroma_client=client,
                embedding_provider="openai_compatible",
                embedding_model_id="bge-m3:latest",
                chunk_size_chars=80,
                chunk_overlap_chars=10,
                candidate_multiplier=4,
                selection_context_budget_tokens=600,
            )
            payload = service.upload_file(
                "user",
                "explicit.txt",
                b"Explicit experiment metadata must not come from application environment defaults.",
            )

        stored = service.collection.get(include=["metadatas"])
        metadata = stored["metadatas"][0]
        self.assertEqual(metadata["embedding_provider"], "openai_compatible")
        self.assertEqual(metadata["embedding_model"], "bge-m3:latest")
        self.assertIsNone(service.settings)


if __name__ == "__main__":
    unittest.main()
