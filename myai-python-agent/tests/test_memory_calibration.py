import unittest

from app.memory.evaluation.calibrate import evaluate_case
from app.memory.writer.extractor import MemoryToWrite


class FakeExtractor:
    def extract(self, user_input: str):
        if user_input == "write":
            return MemoryToWrite(
                content="write",
                mem_type="preference",
                confidence=0.8,
                importance=4,
                metadata={
                    "slot": "preference",
                    "value": "write",
                    "sensitivity": "personal",
                    "scope": "global",
                },
            )
        return None


class MemoryCalibrationTest(unittest.TestCase):
    def test_evaluate_case_reports_matching_candidate(self):
        result = evaluate_case(
            FakeExtractor(),
            {
                "id": "write-case",
                "input": "write",
                "expect_write": True,
                "expect_mem_type": "preference",
                "expect_slot": "preference",
                "expect_confidence_min": 0.7,
                "expect_confidence_max": 0.9,
            },
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["actual"]["mem_type"], "preference")

    def test_evaluate_case_reports_false_positive(self):
        result = evaluate_case(
            FakeExtractor(),
            {
                "id": "no-write-case",
                "input": "write",
                "expect_write": False,
            },
        )

        self.assertFalse(result["passed"])
        self.assertIn("write expected=False actual=True", result["mismatches"])


if __name__ == "__main__":
    unittest.main()
