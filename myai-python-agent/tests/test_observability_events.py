import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.observability.events import normalize_agent_trace, normalize_task_run


class ObservabilityEventsTest(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def test_normalize_task_run_maps_mcp_and_memory_domains(self):
        run = {
            "task_run_id": "task-1",
            "user_id": "u1",
            "status": "succeeded",
            "events": [
                {
                    "event_id": "e1",
                    "type": "task.memory_retrieval.completed",
                    "timestamp": "2026-06-29T00:00:00+00:00",
                    "status": "running",
                    "metadata": {"selected_count": 2},
                },
                {
                    "event_id": "e2",
                    "type": "task.mcp_call.completed",
                    "timestamp": "2026-06-29T00:00:01+00:00",
                    "status": "running",
                    "step_id": "step1",
                    "metadata": {
                        "server_id": "git-readonly",
                        "registry_name": "mcp__git_readonly__status",
                        "call_latency_ms": 12.5,
                    },
                },
            ],
        }

        events = normalize_task_run(run)

        self.assertEqual(events[0]["domain"], "memory")
        self.assertEqual(events[0]["evidence_count"], 2)
        self.assertEqual(events[1]["domain"], "mcp")
        self.assertEqual(events[1]["connector_id"], "git-readonly")
        self.assertEqual(events[1]["tool_name"], "mcp__git_readonly__status")
        self.assertEqual(events[1]["latency_ms"], 12.5)

    def test_normalize_agent_trace_maps_retrieval_evidence(self):
        trace = {
            "run_id": "agent-1",
            "user_id": "u1",
            "conversation_id": 7,
            "steps": [
                {
                    "name": "knowledge.retrieve",
                    "status": "completed",
                    "started_at": "2026-06-29T00:00:00+00:00",
                    "finished_at": "2026-06-29T00:00:01+00:00",
                    "latency_ms": 10.0,
                    "output_summary": "snippets=2",
                    "metadata": {"citations": [{"id": "a"}, {"id": "b"}]},
                }
            ],
        }

        events = normalize_agent_trace(trace)

        self.assertEqual(events[0]["domain"], "knowledge")
        self.assertEqual(events[0]["conversation_id"], 7)
        self.assertEqual(events[0]["evidence_count"], 2)
        self.assertEqual(events[0]["message"], "snippets=2")

    def test_observability_events_endpoint_returns_normalized_task_events(self):
        response = self.client.post("/task", json={"user_id": "u-events", "content": "calculate 2+2"})
        self.assertEqual(response.status_code, 200)

        events_response = self.client.get("/observability/events?limit=20")

        self.assertEqual(events_response.status_code, 200)
        events = events_response.json()["events"]
        self.assertTrue(events)
        self.assertTrue(all("domain" in event for event in events))
        self.assertTrue(any(event["type"] == "task.step.completed" for event in events))


if __name__ == "__main__":
    unittest.main()
