import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.evaluation.quality import QualityGateConfig
from app.evaluation.quality import evaluate_quality_gate
from app.evaluation.run import render_markdown, run_eval_suite


class UnifiedEvalRunnerTest(unittest.TestCase):
    def test_unified_runner_runs_all_deterministic_suites(self):
        report = run_eval_suite("all")

        self.assertEqual(report["summary"]["failed_reports"], 0)
        self.assertGreaterEqual(report["summary"]["reports"], 4)
        report_ids = {item["report_id"] for item in report["reports"]}
        self.assertIn("memory_governance", report_ids)
        self.assertIn("task_runtime", report_ids)
        self.assertIn("knowledge_retrieval", report_ids)
        self.assertIn("mcp_tool_ecosystem", report_ids)
        self.assertNotIn("memory_llm_calibration", report_ids)
        self.assertGreater(report["summary"]["total"], 0)
        self.assertEqual(report["summary"]["status"], "passed")

    def test_unified_runner_filters_by_domain(self):
        report = run_eval_suite("mcp")

        self.assertEqual(report["summary"]["failed_reports"], 0)
        self.assertEqual(report["summary"]["reports"], 1)
        self.assertEqual(report["reports"][0]["report_id"], "mcp_tool_ecosystem")
        self.assertEqual(report["reports"][0]["domain"], "mcp")

    def test_unified_runner_filters_by_report_id(self):
        report = run_eval_suite("task_runtime")

        self.assertEqual(report["summary"]["reports"], 1)
        self.assertEqual(report["reports"][0]["report_id"], "task_runtime")
        self.assertEqual(report["reports"][0]["status"], "passed")

    def test_unified_runner_markdown_renders_suite_summary(self):
        report = run_eval_suite("mcp")
        markdown = render_markdown(report)

        self.assertIn("# Unified Evaluation Report", markdown)
        self.assertIn("MCP Tool Ecosystem Report", markdown)
        self.assertIn("| Report | Domain | Status |", markdown)

    def test_quality_gate_passes_for_deterministic_mcp_suite(self):
        from app.evaluation.quality import run_quality_gate

        report = run_quality_gate("mcp", record=False)

        self.assertEqual(report["summary"]["status"], "passed")
        self.assertTrue(report["quality_gate"]["passed"])
        self.assertEqual(report["quality_gate"]["summary"]["failed_checks"], 0)

    def test_quality_gate_reports_threshold_failures(self):
        report = {
            "summary": {
                "suite": "synthetic",
                "status": "failed",
                "pass_rate": 0.75,
                "failed_reports": 1,
                "failed": 2,
            },
            "reports": [
                {
                    "report_id": "synthetic_report",
                    "name": "Synthetic Report",
                    "domain": "synthetic",
                    "summary": {"pass_rate": 0.75},
                }
            ],
        }

        gate = evaluate_quality_gate(
            report,
            config=QualityGateConfig(report_min_pass_rate={"synthetic_report": 0.9}),
            history_delta={"failed_cases_delta": 1, "pass_rate_delta": -0.1},
        )

        failed_ids = {check["id"] for check in gate["checks"] if not check["passed"]}
        self.assertFalse(gate["passed"])
        self.assertIn("suite_status", failed_ids)
        self.assertIn("suite_pass_rate", failed_ids)
        self.assertIn("failed_reports", failed_ids)
        self.assertIn("failed_cases", failed_ids)
        self.assertIn("report_pass_rate:synthetic_report", failed_ids)
        self.assertIn("failed_cases_delta", failed_ids)
        self.assertIn("pass_rate_delta", failed_ids)

    def test_maintenance_report_api_returns_recommendations(self):
        with TestClient(app) as client:
            response = client.post("/eval/maintenance-report?suite=mcp")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["status"], "passed")
        self.assertTrue(payload["quality_gate"]["passed"])
        self.assertTrue(payload["recommendations"])
        self.assertIn("history", payload)


if __name__ == "__main__":
    unittest.main()
