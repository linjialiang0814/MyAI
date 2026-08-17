import unittest

from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.mem_service import MemoryService
from app.memory.store.in_mem_store import MemoryStore


class ManualMemoryWriteTest(unittest.TestCase):
    def test_default_extraction_still_rejects_unstructured_input(self):
        service = MemoryService(
            embedding_client=StubEmbedding(),
            memory_store=MemoryStore(),
        )

        result = service.process_user_input("u-manual-default", "project note for tomorrow")

        self.assertFalse(result["written"])
        self.assertEqual(result["reason"], "writer rejected input")

    def test_explicit_manual_write_falls_back_to_general_memory(self):
        service = MemoryService(
            embedding_client=StubEmbedding(),
            memory_store=MemoryStore(),
        )

        result = service.process_user_input(
            "u-manual-explicit",
            "project note for tomorrow",
            source="user_explicit",
            allow_unstructured_manual_write=True,
        )
        memories = service.memory_store.get_all("u-manual-explicit")

        self.assertTrue(result["written"])
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(memories[0].content, "project note for tomorrow")
        self.assertEqual(memories[0].mem_type, "general")
        self.assertEqual(memories[0].metadata["slot"], "manual_note")
        self.assertEqual(memories[0].metadata["extraction_method"], "manual")


if __name__ == "__main__":
    unittest.main()
