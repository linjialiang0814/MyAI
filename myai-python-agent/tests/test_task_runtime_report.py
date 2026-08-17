import unittest

from app.task.evaluation.runtime_report import render_markdown, run_runtime_report


class TaskRuntimeReportTest(unittest.TestCase):
    def test_runtime_report_passes_default_fixture(self):
        report = run_runtime_report()

        self.assertEqual(report["summary"]["failed"], 0)
        self.assertGreaterEqual(report["summary"]["total"], 7)
        by_id = {case["id"]: case for case in report["cases"]}
        self.assertEqual(by_id["single_safe_tool"]["tools"], ["calculator"])
        self.assertEqual(by_id["permission_required"]["workflow"], "memory_maintenance")
        self.assertTrue(by_id["permission_required"]["permission_required"])
        self.assertEqual(by_id["retryable_failure_recovered"]["recovery_status"], "succeeded_after_retry")
        self.assertGreaterEqual(by_id["memory_aware_planning"]["memory_selected_count"], 1)

    def test_runtime_report_markdown_contains_case_and_tool_stats(self):
        report = run_runtime_report()
        markdown = render_markdown(report)

        self.assertIn("# Task Runtime Evaluation Report", markdown)
        self.assertIn("single_safe_tool", markdown)
        self.assertIn("permission_required", markdown)
        self.assertIn("| calculator |", markdown)


if __name__ == "__main__":
    unittest.main()
