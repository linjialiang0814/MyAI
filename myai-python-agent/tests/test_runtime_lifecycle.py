from contextlib import ExitStack
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.model.config import LLMSettings
from app.runtime.container import AppRuntime, build_runtime
from app.runtime.config import RuntimeSettings


def _stub_settings() -> LLMSettings:
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
        memory_collection_name="runtime_lifecycle_memory",
        knowledge_collection_name="runtime_lifecycle_knowledge",
    )


class _CloseCounter:
    def __init__(self) -> None:
        self.calls = 0

    def close(self) -> None:
        self.calls += 1


class _SchedulerCounter:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self, *, timeout_seconds: float = 5.0) -> bool:
        self.stop_calls += 1
        return True


class RuntimeLifecycleTest(unittest.TestCase):
    def test_app_factory_defers_runtime_creation_to_lifespan(self):
        runtime = _CloseCounter()
        calls = []

        def runtime_factory():
            calls.append("build")
            return runtime

        application = create_app(runtime_factory=runtime_factory)
        self.assertEqual(calls, [])

        with TestClient(application):
            self.assertEqual(calls, ["build"])
            self.assertIs(application.state.runtime, runtime)

        self.assertEqual(runtime.calls, 1)
        self.assertIsNone(application.state.runtime)

    def test_runtime_close_is_idempotent(self):
        close_counter = _CloseCounter()
        resources = ExitStack()
        resources.callback(close_counter.close)
        placeholder = object()
        runtime = AppRuntime(
            settings=_stub_settings(),
            runtime_settings=RuntimeSettings(database_path=Path("runtime-test.db")),
            embedding_client=placeholder,
            chroma_client=placeholder,
            runtime_repository=placeholder,
            agent_run_store=placeholder,
            task_run_store=placeholder,
            memory_service=placeholder,
            knowledge_service=placeholder,
            task_service=placeholder,
            agent_service=placeholder,
            chat_llm=placeholder,
            task_llm=placeholder,
            _resources=resources,
        )

        runtime.close()
        runtime.close()

        self.assertTrue(runtime.closed)
        self.assertEqual(close_counter.calls, 1)

    def test_build_runtime_shares_services_across_agent_task_and_tools(self):
        temp_dir = Path.cwd() / ".tmp" / f"runtime-lifecycle-{uuid4().hex}"
        try:
            environment = {
                "MYAI_CHROMA_MODE": "ephemeral",
                "MYAI_KNOWLEDGE_DATA_DIR": str(temp_dir / "knowledge"),
                "MYAI_MEMORY_SETTINGS_DIR": str(temp_dir / "memory-settings"),
                "MYAI_RUNTIME_DB_PATH": str(temp_dir / "runtime" / "runtime.db"),
                "MYAI_MCP_GIT_ENABLED": "false",
                "MYAI_MCP_FILESYSTEM_ENABLED": "false",
            }
            with patch.dict(os.environ, environment, clear=False):
                runtime = build_runtime(settings=_stub_settings())
                try:
                    registry = runtime.task_service.task_executor.registry
                    self.assertIs(runtime.agent_service.memory_service, runtime.memory_service)
                    self.assertIs(runtime.agent_service.knowledge_service, runtime.knowledge_service)
                    self.assertIs(runtime.agent_service.task_service, runtime.task_service)
                    self.assertIs(runtime.task_service.memory_service, runtime.memory_service)
                    self.assertIs(
                        runtime.memory_service.memory_store.client,
                        runtime.chroma_client,
                    )
                    self.assertIs(runtime.knowledge_service.client, runtime.chroma_client)
                    self.assertIs(
                        registry.get_tool("file_summary").knowledge_service,
                        runtime.knowledge_service,
                    )
                    self.assertIs(
                        registry.get_tool("knowledge_admin").knowledge_service,
                        runtime.knowledge_service,
                    )
                    self.assertIs(
                        registry.get_tool("memory_admin").memory_service,
                        runtime.memory_service,
                    )
                finally:
                    runtime.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_build_runtime_closes_partial_resources_when_startup_fails(self):
        chroma_client = _CloseCounter()
        with (
            patch("app.runtime.container.create_chroma_client", return_value=chroma_client),
            patch("app.runtime.container.create_embedding_client", side_effect=RuntimeError("boom")),
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                build_runtime(settings=_stub_settings())

        self.assertEqual(chroma_client.calls, 1)

    def test_build_runtime_stops_scheduler_when_late_startup_step_fails(self):
        temp_dir = Path.cwd() / ".tmp" / f"runtime-startup-cleanup-{uuid4().hex}"
        scheduler = _SchedulerCounter()
        environment = {
            "MYAI_CHROMA_MODE": "ephemeral",
            "MYAI_KNOWLEDGE_DATA_DIR": str(temp_dir / "knowledge"),
            "MYAI_MEMORY_SETTINGS_DIR": str(temp_dir / "memory-settings"),
            "MYAI_MCP_GIT_ENABLED": "false",
            "MYAI_MCP_FILESYSTEM_ENABLED": "false",
        }
        try:
            with (
                patch.dict(os.environ, environment, clear=False),
                patch(
                    "app.runtime.container.MemoryMaintenanceScheduler",
                    return_value=scheduler,
                ),
                patch(
                    "app.runtime.container.build_task_service",
                    side_effect=RuntimeError("late startup failure"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "late startup failure"):
                    build_runtime(
                        settings=_stub_settings(),
                        runtime_settings=RuntimeSettings(
                            database_path=temp_dir / "runtime" / "runtime.db",
                        ),
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(scheduler.start_calls, 1)
        self.assertEqual(scheduler.stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
