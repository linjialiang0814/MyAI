import unittest

import numpy as np

from app.memory.mem_service import MemoryService
from app.memory.store.in_mem_store import MemoryStore
from app.memory.writer.llm_extractor import LLMMemoryExtractor
from app.memory.writer.smart_writer import RuleBasedMemoryExtractor, SmartMemoryWriter


class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class FailingLLM:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("model unavailable")


class TinyEmbedding:
    def embed(self, text: str):
        return np.array([1.0, 0.0, 0.0], dtype=np.float32)


class MemoryLLMExtractorTest(unittest.TestCase):
    def test_llm_extractor_parses_structured_memory(self):
        extractor = LLMMemoryExtractor(
            FakeLLM(
                """
                {
                  "should_write": true,
                  "content": "I use dark mode for coding",
                  "mem_type": "preference",
                  "slot": "preference",
                  "value": "dark mode for coding",
                  "confidence": 0.76,
                  "importance": 4,
                  "reason": "user stated a durable UI preference"
                }
                """
            )
        )

        candidate = extractor.extract("Dark mode is easier on my eyes when coding.")

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.mem_type, "preference")
        self.assertEqual(candidate.metadata["slot"], "preference")
        self.assertEqual(candidate.metadata["value"], "dark mode for coding")
        self.assertEqual(candidate.metadata["extraction_method"], "llm")
        self.assertEqual(candidate.metadata["sensitivity"], "personal")
        self.assertEqual(candidate.metadata["scope"], "global")

    def test_llm_extractor_rejects_invalid_or_low_confidence_payloads(self):
        self.assertIsNone(LLMMemoryExtractor(FakeLLM("not json")).extract("anything"))
        self.assertIsNone(
            LLMMemoryExtractor(
                FakeLLM(
                    '{"should_write": true, "content": "x", "mem_type": "fact", '
                    '"slot": "major", "value": "x", "confidence": 0.2, "importance": 3}'
                )
            ).extract("anything")
        )

    def test_llm_extractor_parses_multiple_candidates(self):
        extractor = LLMMemoryExtractor(
            FakeLLM(
                """
                {
                  "should_write": true,
                  "memories": [
                    {
                      "should_write": true,
                      "content": "my major is computer science",
                      "mem_type": "fact",
                      "slot": "major",
                      "value": "computer science",
                      "confidence": 0.9,
                      "importance": 5,
                      "reason": "user stated major"
                    },
                    {
                      "should_write": true,
                      "content": "I like Python",
                      "mem_type": "preference",
                      "slot": "preference",
                      "value": "python",
                      "confidence": 0.88,
                      "importance": 4,
                      "reason": "user stated preference"
                    }
                  ]
                }
                """
            )
        )

        candidates = extractor.extract_many("my major is computer science and I like Python")

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].metadata["slot"], "major")
        self.assertEqual(candidates[1].metadata["slot"], "preference")

    def test_llm_extractor_fails_closed_when_model_is_unavailable(self):
        self.assertIsNone(LLMMemoryExtractor(FailingLLM()).extract("anything"))

    def test_memory_service_uses_llm_fallback_after_rules(self):
        writer = SmartMemoryWriter(
            extractors=[
                RuleBasedMemoryExtractor(),
                LLMMemoryExtractor(
                    FakeLLM(
                        """
                        {
                          "should_write": true,
                          "content": "I usually code late at night",
                          "mem_type": "preference",
                          "slot": "preference",
                          "value": "code late at night",
                          "confidence": 0.62,
                          "importance": 4,
                          "reason": "user described a durable work habit"
                        }
                        """
                    )
                ),
            ]
        )
        service = MemoryService(
            embedding_client=TinyEmbedding(),
            memory_store=MemoryStore(),
            writer=writer,
        )

        result = service.process_user_input("u-llm-memory", "Late-night coding is when I focus best.")
        memory = service.memory_store.get_by_id("u-llm-memory", result["memory_id"])

        self.assertTrue(result["written"])
        self.assertEqual(memory.mem_type, "preference")
        self.assertEqual(memory.metadata["extraction_method"], "llm")
        self.assertEqual(memory.metadata["review_status"], "pending")
        self.assertIn("confidence", memory.metadata["review_reason"])

    def test_multi_candidate_low_confidence_goes_pending_with_batch_metadata(self):
        writer = SmartMemoryWriter(
            extractors=[
                LLMMemoryExtractor(
                    FakeLLM(
                        """
                        {
                          "should_write": true,
                          "memories": [
                            {
                              "should_write": true,
                              "content": "my major is computer science",
                              "mem_type": "fact",
                              "slot": "major",
                              "value": "computer science",
                              "confidence": 0.92,
                              "importance": 5,
                              "reason": "user stated major"
                            },
                            {
                              "should_write": true,
                              "content": "I prefer concise answers",
                              "mem_type": "preference",
                              "slot": "preference",
                              "value": "concise answers",
                              "confidence": 0.78,
                              "importance": 4,
                              "reason": "user implied response style preference"
                            }
                          ]
                        }
                        """
                    )
                )
            ]
        )
        service = MemoryService(
            embedding_client=TinyEmbedding(),
            memory_store=MemoryStore(),
            writer=writer,
        )

        result = service.process_user_input(
            "u-llm-memory-multi",
            "my major is computer science and I prefer concise answers",
        )
        memories = service.memory_store.get_all("u-llm-memory-multi")
        by_value = {memory.metadata["canonical_value"]: memory for memory in memories}

        self.assertTrue(result["written"])
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["written_count"], 2)
        self.assertEqual(by_value["computer science"].metadata["review_status"], "accepted")
        low_confidence = by_value["concise answers"]
        self.assertEqual(low_confidence.metadata["review_status"], "pending")
        self.assertIn("multi-candidate confidence", low_confidence.metadata["review_reason"])
        self.assertEqual(low_confidence.metadata["raw_confidence"], 0.78)
        self.assertLess(low_confidence.metadata["calibrated_confidence"], 0.78)
        self.assertIn("method:llm", low_confidence.metadata["confidence_calibration_factors"])
        self.assertEqual(low_confidence.metadata["candidate_count"], 2)
        self.assertEqual(low_confidence.metadata["candidate_index"], 2)
        self.assertTrue(low_confidence.metadata["multi_candidate"])
        self.assertEqual(
            by_value["computer science"].metadata["extraction_batch_id"],
            low_confidence.metadata["extraction_batch_id"],
        )


if __name__ == "__main__":
    unittest.main()
