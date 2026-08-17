import unittest

from app.knowledge.evaluation.report import render_markdown, run_knowledge_report


class KnowledgeEvalReportTest(unittest.TestCase):
    def test_knowledge_report_passes_default_fixture(self):
        report = run_knowledge_report()

        self.assertEqual(report["summary"]["failed"], 0)
        self.assertGreaterEqual(report["summary"]["total"], 8)
        self.assertEqual(report["summary"]["hit_at_k"], 1.0)
        self.assertEqual(report["summary"]["expected_file_found"], 1.0)
        self.assertEqual(report["summary"]["citation_completeness"], 1.0)
        self.assertEqual(report["summary"]["coverage_by_type"]["query"], 5)

        by_id = {case["id"]: case for case in report["cases"]}
        self.assertEqual(by_id["semantic_retrieval"]["top_retrieval_mode"], "vector")
        self.assertTrue(by_id["file_filtered_retrieval"]["hit_at_k"])
        self.assertEqual(by_id["no_answer_insufficient_evidence"]["answer_status"], "not_enough_evidence")

    def test_knowledge_report_markdown_renders_metrics(self):
        report = run_knowledge_report()
        markdown = render_markdown(report)

        self.assertIn("# Knowledge Evaluation Report", markdown)
        self.assertIn("Hit@k", markdown)
        self.assertIn("Citation completeness", markdown)
        self.assertIn("semantic_retrieval", markdown)
        self.assertIn("| Case | Type | Pass | Hit@k | Expected File | Citation | Latency ms | Notes |", markdown)


if __name__ == "__main__":
    unittest.main()
