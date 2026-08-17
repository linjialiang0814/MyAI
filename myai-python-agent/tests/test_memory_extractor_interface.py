import unittest

from app.memory.writer.extractor import MemoryToWrite
from app.memory.writer.smart_writer import SmartMemoryWriter


class FakeExtractor:
    def extract(self, user_input: str):
        if user_input == "structured extractor input":
            return MemoryToWrite(
                content=user_input,
                mem_type="fact",
                importance=5,
                confidence=0.99,
                canonical_key="custom",
                canonical_value="value",
                metadata={"slot": "custom", "value": "value"},
            )
        return None


class MemoryExtractorInterfaceTest(unittest.TestCase):
    def test_writer_accepts_structured_extractor(self):
        writer = SmartMemoryWriter(extractors=[FakeExtractor()])

        candidate = writer.should_write("structured extractor input")

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.mem_type, "fact")
        self.assertEqual(candidate.metadata["slot"], "custom")

    def test_negative_command_short_circuits_extractors(self):
        writer = SmartMemoryWriter(extractors=[FakeExtractor()])

        candidate = writer.should_write("forget this: structured extractor input")

        self.assertIsNone(candidate)

    def test_correction_prefix_marks_update_intent(self):
        writer = SmartMemoryWriter()

        candidate = writer.should_write("Actually, my major is AI")

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.mem_type, "fact")
        self.assertEqual(candidate.metadata["slot"], "major")
        self.assertEqual(candidate.metadata["value"], "ai")
        self.assertEqual(candidate.metadata["update_intent"], "correction")
        self.assertEqual(candidate.content, "Actually, my major is AI")

    def test_move_expression_marks_location_correction(self):
        writer = SmartMemoryWriter()

        candidate = writer.should_write("I moved to Shanghai")

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.mem_type, "fact")
        self.assertEqual(candidate.metadata["slot"], "location")
        self.assertEqual(candidate.metadata["value"], "shanghai")
        self.assertEqual(candidate.metadata["update_intent"], "correction")

    def test_preference_negation_marks_update_intent(self):
        writer = SmartMemoryWriter()

        candidate = writer.should_write("I no longer like Python")

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.mem_type, "preference")
        self.assertEqual(candidate.metadata["slot"], "preference")
        self.assertEqual(candidate.metadata["value"], "python")
        self.assertEqual(candidate.metadata["update_intent"], "negation")
        self.assertEqual(candidate.metadata["negation_signal"], "explicit")

    def test_rule_writer_extracts_multiple_candidates(self):
        writer = SmartMemoryWriter()

        candidates = writer.extract_candidates("my major is CS and I like Python")

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].metadata["slot"], "major")
        self.assertEqual(candidates[0].metadata["value"], "cs")
        self.assertEqual(candidates[1].mem_type, "preference")
        self.assertEqual(candidates[1].metadata["value"], "python")


if __name__ == "__main__":
    unittest.main()
