import unittest
from pathlib import Path
import shutil
from unittest.mock import patch
from uuid import uuid4

from app.task.evaluation.mcp_report import render_markdown, run_mcp_report


class MCPEvalReportTest(unittest.TestCase):
    def test_mcp_report_passes_default_fixture(self):
        report = run_mcp_report()

        self.assertEqual(report["summary"]["failed"], 0)
        self.assertGreaterEqual(report["summary"]["total"], 9)
        coverage = report["summary"]["coverage"]
        self.assertGreaterEqual(coverage["descriptor"], 1)
        self.assertGreaterEqual(coverage["policy"], 2)
        self.assertGreaterEqual(coverage["connector_health"], 1)
        self.assertGreaterEqual(coverage["execution_trace"], 1)
        by_id = {case["id"]: case for case in report["cases"]}
        self.assertEqual(by_id["filesystem_read_execution_trace"]["actual"]["event_type"], "task.mcp_call.completed")
        self.assertTrue(by_id["filesystem_read_execution_trace"]["actual"]["has_step_event"])
        self.assertEqual(by_id["filesystem_path_escape_fails_closed"]["actual"]["event_type"], "task.mcp_call.failed")
        self.assertEqual(
            by_id["filesystem_path_escape_fails_closed"]["actual"]["error_category"],
            "path_outside_allowed_roots",
        )
        self.assertEqual(by_id["git_connector_health"]["actual"]["risk_level"], "filesystem/read")
        self.assertEqual(by_id["git_status_execution_trace"]["actual"]["event_type"], "task.mcp_call.completed")
        self.assertEqual(by_id["git_status_execution_trace"]["actual"]["connector"], "git_readonly")

    def test_mcp_report_markdown_contains_coverage_and_cases(self):
        report = run_mcp_report()
        markdown = render_markdown(report)

        self.assertIn("# MCP Evaluation Report", markdown)
        self.assertIn("descriptor_schema_conversion", markdown)
        self.assertIn("filesystem_connector_health", markdown)
        self.assertIn("filesystem_read_execution_trace", markdown)
        self.assertIn("git_status_execution_trace", markdown)
        self.assertIn("Coverage:", markdown)

    def test_git_cases_are_explicitly_skipped_outside_a_source_checkout(self):
        directory = Path.cwd() / ".tmp" / f"mcp-no-git-{uuid4().hex}"
        directory.mkdir(parents=True, exist_ok=False)
        try:
            with patch("app.task.evaluation.mcp_report.BASE_DIR", directory / "python"):
                report = run_mcp_report()
        finally:
            shutil.rmtree(directory, ignore_errors=True)

        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["summary"]["skipped"], 2)
        self.assertEqual(report["summary"]["pass_rate"], 1.0)
        git_cases = [case for case in report["cases"] if case["type"].startswith("git_")]
        self.assertEqual(len(git_cases), 2)
        self.assertTrue(all(case["skipped"] for case in git_cases))


if __name__ == "__main__":
    unittest.main()
