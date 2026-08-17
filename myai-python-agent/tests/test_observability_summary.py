import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.observability.store import ObservabilityStore, observability_store


class ObservabilitySummaryTest(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        observability_store.clear_eval_runs()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def test_eval_run_is_recorded_and_visible_in_summary(self):
        run_response = self.client.post("/eval/runs?suite=mcp")

        self.assertEqual(run_response.status_code, 200)
        run_payload = run_response.json()
        self.assertEqual(run_payload["summary"]["status"], "passed")
        self.assertEqual(run_payload["summary"]["failed_reports"], 0)
        self.assertIn("observability_record", run_payload)

        runs_response = self.client.get("/eval/runs")
        self.assertEqual(runs_response.status_code, 200)
        runs = runs_response.json()["runs"]
        self.assertTrue(runs)
        self.assertEqual(runs[0]["suite"], "mcp")
        self.assertEqual(runs[0]["status"], "passed")

        summary_response = self.client.get("/observability/summary")
        self.assertEqual(summary_response.status_code, 200)
        summary = summary_response.json()
        self.assertEqual(summary["eval"]["runs"], 1)
        self.assertEqual(summary["eval"]["latest"]["suite"], "mcp")
        self.assertGreaterEqual(summary["connectors"]["total"], 1)
        self.assertIn("task", summary)
        self.assertIn("model", summary)
        self.assertIn("chat", summary["model"]["roles"])
        self.assertIn("provider_auth_configured", summary["model"])
        self.assertNotIn("ark_api_key", summary["model"])
        self.assertNotIn("api_key_configured", summary["model"])

    def test_eval_run_history_is_persisted_and_reloaded(self):
        persist_dir = Path.cwd() / ".tmp" / f"observability-store-{uuid4().hex}"
        persist_path = persist_dir / "eval_runs.jsonl"
        try:
            store = ObservabilityStore(max_eval_runs=5, persist_path=persist_path)
            store.record_eval_run(
                {
                    "summary": {
                        "suite": "memory",
                        "status": "passed",
                        "pass_rate": 1.0,
                        "failed_reports": 0,
                        "failed": 0,
                        "total": 10,
                        "duration_ms": 100,
                    },
                    "reports": [],
                }
            )
            store.record_eval_run(
                {
                    "summary": {
                        "suite": "memory",
                        "status": "failed",
                        "pass_rate": 0.8,
                        "failed_reports": 1,
                        "failed": 2,
                        "total": 12,
                        "duration_ms": 150,
                    },
                    "reports": [],
                }
            )

            reloaded = ObservabilityStore(max_eval_runs=5, persist_path=persist_path)
            runs = reloaded.list_eval_runs(limit=5)
            summary = reloaded.eval_summary()

            self.assertEqual(len(runs), 2)
            self.assertEqual(runs[0]["status"], "failed")
            self.assertEqual(runs[1]["status"], "passed")
            self.assertEqual(summary["latest"]["status"], "failed")
            self.assertEqual(summary["previous"]["status"], "passed")
            self.assertTrue(summary["delta"]["status_changed"])
            self.assertEqual(summary["delta"]["failed_reports_delta"], 1)
            self.assertEqual(summary["delta"]["failed_cases_delta"], 2)
            self.assertEqual(summary["delta"]["total_cases_delta"], 2)
            self.assertAlmostEqual(summary["delta"]["pass_rate_delta"], -0.2)
            self.assertTrue(summary["storage"]["persisted"])
        finally:
            shutil.rmtree(persist_dir, ignore_errors=True)

    def test_task_runtime_counters_are_visible_in_summary(self):
        task_response = self.client.post("/task", json={"user_id": "u-observe", "content": "calculate 1+2"})
        self.assertEqual(task_response.status_code, 200)

        summary_response = self.client.get("/observability/summary")

        self.assertEqual(summary_response.status_code, 200)
        summary = summary_response.json()
        self.assertGreaterEqual(summary["task"]["runs"], 1)
        self.assertIn("planner", summary["task"])
        self.assertIn("tools", summary["task"])

    def test_observability_summary_redacts_sensitive_paths_by_default(self):
        self.client.post("/eval/runs?suite=mcp")

        summary_response = self.client.get("/observability/summary")
        sensitive_response = self.client.get("/observability/summary?include_sensitive=true")

        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(sensitive_response.status_code, 200)
        summary = summary_response.json()
        sensitive = sensitive_response.json()

        self.assertTrue(summary["privacy"]["redaction_applied"])
        self.assertFalse(sensitive["privacy"]["redaction_applied"])
        self.assertIn("[local-path:", summary["eval"]["storage"]["path"])
        self.assertNotIn("[local-path:", sensitive["eval"]["storage"]["path"])

        git = next(
            connector for connector in summary["connectors"]["items"]
            if connector["server_id"] == "git-readonly"
        )
        root_path = git["settings"]["repo_root"]
        self.assertIn("[local-path:", root_path)

    def test_task_tools_redacts_connector_settings_by_default(self):
        response = self.client.get("/task/tools")
        sensitive_response = self.client.get("/task/tools?include_sensitive=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sensitive_response.status_code, 200)
        payload = response.json()
        sensitive = sensitive_response.json()

        self.assertTrue(payload["privacy"]["redaction_applied"])
        self.assertFalse(sensitive["privacy"]["redaction_applied"])
        git = next(
            connector for connector in payload["connectors"]
            if connector["server_id"] == "git-readonly"
        )
        sensitive_git = next(
            connector for connector in sensitive["connectors"]
            if connector["server_id"] == "git-readonly"
        )
        self.assertIn("[local-path:", git["settings"]["repo_root"])
        self.assertNotIn("[local-path:", sensitive_git["settings"]["repo_root"])


if __name__ == "__main__":
    unittest.main()
