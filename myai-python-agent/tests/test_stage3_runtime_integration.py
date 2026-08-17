from __future__ import annotations

import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.model.config import LLMSettings
from app.runtime.config import RuntimeSettings
from app.runtime.container import build_runtime
from app.runtime.sqlite_repository import IdempotencyConflictError, SQLiteRuntimeRepository


def _stub_model_settings(suffix: str) -> LLMSettings:
    return LLMSettings(
        default_provider="stub",
        chat_provider="stub",
        task_provider="stub",
        memory_provider="stub",
        embedding_provider="stub",
        memory_llm_extractor_enabled=False,
        fallback_to_stub=False,
        temperature=0.0,
        ark_api_key="",
        ark_base_url="",
        default_model_id="",
        chat_model_id="",
        task_model_id="",
        memory_model_id="",
        embedding_model_id="",
        memory_collection_name=f"stage3_memory_{suffix}",
        knowledge_collection_name=f"stage3_knowledge_{suffix}",
    )


class Stage3RuntimeIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / ".tmp" / f"stage3-{uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        self.database_path = self.root / "runtime" / "runtime.db"
        self.environment = {
            "MYAI_CHROMA_MODE": "ephemeral",
            "MYAI_KNOWLEDGE_DATA_DIR": str(self.root / "knowledge"),
            "MYAI_MEMORY_SETTINGS_DIR": str(self.root / "memory-settings"),
            "MYAI_MCP_GIT_ENABLED": "false",
            "MYAI_MCP_FILESYSTEM_ENABLED": "false",
        }

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _build_runtime(self):
        suffix = uuid4().hex
        runtime_settings = RuntimeSettings(
            database_path=self.database_path,
            memory_maintenance_debounce_seconds=3_600,
        )
        return build_runtime(
            settings=_stub_model_settings(suffix),
            runtime_settings=runtime_settings,
        )

    def test_chat_persists_complete_run_chain_and_replays_idempotently(self):
        with patch.dict(os.environ, self.environment, clear=False):
            runtime = self._build_runtime()
            try:
                def forbidden_hot_path(_user_id):
                    raise AssertionError("maintenance must not run in the chat request path")

                runtime.memory_service.maintenance = forbidden_hot_path
                first = runtime.agent_service.generate_reply(
                    "owner-stage3",
                    "hello runtime",
                    conversation_id=71,
                    history=[{"role": "user", "content": "prior context"}],
                    idempotency_key="chat-request-71",
                )
                replay = runtime.agent_service.generate_reply(
                    "owner-stage3",
                    "hello runtime",
                    conversation_id=71,
                    history=[{"role": "user", "content": "prior context"}],
                    idempotency_key="chat-request-71",
                )

                self.assertEqual(replay.trace.run_id, first.trace.run_id)
                self.assertEqual(replay.reply, first.reply)
                self.assertIn(
                    "memory.maintenance.schedule",
                    [step.name for step in first.trace.steps],
                )
                task_runs = runtime.task_run_store.list_runs(user_id="owner-stage3")
                self.assertEqual(len(task_runs), 1)
                self.assertEqual(task_runs[0].agent_run_id, first.trace.run_id)
                self.assertEqual(task_runs[0].conversation_id, 71)

                with self.assertRaises(IdempotencyConflictError):
                    runtime.agent_service.generate_reply(
                        "owner-stage3",
                        "different body",
                        conversation_id=71,
                        idempotency_key="chat-request-71",
                    )
                with self.assertRaises(IdempotencyConflictError):
                    runtime.agent_service.generate_reply(
                        "owner-stage3",
                        "hello runtime",
                        conversation_id=71,
                        history=[{"role": "user", "content": "changed context"}],
                        idempotency_key="chat-request-71",
                    )
            finally:
                runtime.close()

        repository = SQLiteRuntimeRepository(self.database_path)
        try:
            restored_agent = repository.get_agent_run(first.trace.run_id)
            restored_tasks = repository.list_task_runs(user_id="owner-stage3", limit=10)
            self.assertEqual(restored_agent.status, "completed")
            self.assertEqual(restored_agent.conversation_id, 71)
            self.assertEqual(restored_tasks[0].agent_run_id, restored_agent.run_id)
        finally:
            repository.close()

    def test_standalone_task_creates_parent_agent_run(self):
        with patch.dict(os.environ, self.environment, clear=False):
            runtime = self._build_runtime()
            try:
                decision = runtime.task_service.handle_task(
                    "hello standalone task",
                    user_id="owner-task",
                    conversation_id=81,
                    idempotency_key="standalone-request-81",
                )
                replay = runtime.task_service.handle_task(
                    "hello standalone task",
                    user_id="owner-task",
                    conversation_id=81,
                    idempotency_key="standalone-request-81",
                )
                task_run = runtime.task_run_store.get(decision.task_run_id)
                parent = runtime.agent_run_store.get(task_run.agent_run_id)

                self.assertEqual(replay.task_run_id, decision.task_run_id)
                self.assertEqual(parent.kind, "standalone_task")
                self.assertEqual(parent.user_id, task_run.user_id)
                self.assertEqual(parent.conversation_id, task_run.conversation_id)
                self.assertEqual(parent.status, "completed")
            finally:
                runtime.close()

    def test_agent_run_api_exposes_owner_filtered_relationship(self):
        with patch.dict(os.environ, self.environment, clear=False):
            runtime = self._build_runtime()
            application = create_app(runtime_factory=lambda: runtime)
            with TestClient(application) as client:
                chat = client.post(
                    "/chat",
                    headers={"Idempotency-Key": "api-chat-91"},
                    json={
                        "user_id": "owner-api",
                        "message": "hello api runtime",
                        "conversation_id": 91,
                    },
                )
                self.assertEqual(chat.status_code, 200)
                run_id = chat.json()["run_id"]

                detail = client.get(f"/agent/runs/{run_id}?user_id=owner-api")
                hidden = client.get(f"/agent/runs/{run_id}?user_id=other-owner")

                self.assertEqual(detail.status_code, 200)
                self.assertEqual(detail.json()["conversation_id"], 91)
                self.assertEqual(detail.json()["task_runs"][0]["agent_run_id"], run_id)
                self.assertEqual(hidden.status_code, 404)
                self.assertEqual(hidden.json()["error"]["code"], "not_found")

    def test_global_error_model_maps_idempotency_conflict_and_request_id(self):
        class ErrorAgentService:
            def generate_reply(self, *args, **kwargs):
                raise IdempotencyConflictError("private database detail")

        class FakeRuntime(SimpleNamespace):
            def close(self):
                return None

        application = create_app(
            runtime_factory=lambda: FakeRuntime(agent_service=ErrorAgentService())
        )
        with TestClient(application, raise_server_exceptions=False) as client:
            response = client.post(
                "/chat",
                headers={"X-Request-ID": "stage3-request-id"},
                json={"user_id": "owner", "message": "hello"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.headers["X-Request-ID"], "stage3-request-id")
        self.assertEqual(response.json()["error"]["code"], "idempotency_conflict")
        self.assertNotIn("private database detail", response.text)


if __name__ == "__main__":
    unittest.main()
