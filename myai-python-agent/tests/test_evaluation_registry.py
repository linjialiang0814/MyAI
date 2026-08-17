import unittest

from fastapi.testclient import TestClient

from app.evaluation.registry import get_eval_report, list_eval_reports
from app.main import app


class EvaluationRegistryTest(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def test_registry_lists_existing_reports(self):
        reports = list_eval_reports()
        by_id = {report["report_id"]: report for report in reports}

        self.assertIn("memory_governance", by_id)
        self.assertIn("memory_llm_calibration", by_id)
        self.assertIn("task_runtime", by_id)
        self.assertIn("knowledge_retrieval", by_id)
        self.assertIn("mcp_tool_ecosystem", by_id)
        self.assertEqual(by_id["mcp_tool_ecosystem"]["domain"], "mcp")
        self.assertTrue(by_id["task_runtime"]["strict_supported"])
        self.assertTrue(by_id["memory_llm_calibration"]["requires_live_llm"])
        self.assertFalse(by_id["memory_llm_calibration"]["deterministic"])

    def test_registry_get_report_by_id(self):
        report = get_eval_report("knowledge_retrieval")

        self.assertIsNotNone(report)
        self.assertEqual(report["module"], "app.knowledge.evaluation.report")
        self.assertIn("knowledge_eval.json", report["fixture_path"])

    def test_eval_reports_api_lists_registry(self):
        response = self.client.get("/eval/reports")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["summary"]["total"], 5)
        self.assertIn("memory", payload["summary"]["domains"])
        self.assertIn("mcp", payload["summary"]["domains"])
        ids = {report["report_id"] for report in payload["reports"]}
        self.assertIn("task_runtime", ids)
        self.assertIn("mcp_tool_ecosystem", ids)

    def test_eval_report_api_gets_single_report(self):
        response = self.client.get("/eval/reports/memory_governance")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["report_id"], "memory_governance")
        self.assertEqual(payload["domain"], "memory")

    def test_eval_report_api_returns_404_for_unknown_report(self):
        response = self.client.get("/eval/reports/not_found")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
