from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.core.service import AgentService
from app.knowledge.service import KnowledgeService
from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.maintenance.scheduler import MemoryMaintenanceScheduler
from app.runtime.agent_store import AgentRunStore
from app.runtime.config import RuntimeSettings
from app.runtime.container import AppRuntime
from app.runtime.error_model import AppError, ErrorCode
from app.runtime.resilience import Deadline
from app.task.runtime import TaskRunStore
from app.task.service.task_service import TaskService
from app.task.stats.record import DecisionRecord


class _CloseAwareExecutor:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self, timeout_seconds: float = 5.0) -> bool:
        self.close_calls += 1
        return True


class _Stats:
    def __init__(self) -> None:
        self.records = []

    def record(self, decision) -> None:
        self.records.append(decision)

    @staticmethod
    def compute_reward(_decision) -> float:
        return 0.0


class _SlowPlanner:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds
        self.calls = 0

    def plan(self, _content, short_context=None):
        self.calls += 1
        time.sleep(self.delay_seconds)
        return object()


class _ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _DeadlineExpiringTaskService:
    def __init__(self, clock: _ManualClock) -> None:
        self.clock = clock
        self.deadline = None

    def handle_task(self, content: str, **kwargs) -> DecisionRecord:
        self.deadline = kwargs.get("deadline")
        self.clock.advance(2.0)
        return DecisionRecord(
            task_run_id="chat-child-task",
            status="succeeded",
            user_id=kwargs.get("user_id"),
            content=content,
            plan={"need_tool": False},
            result={"success": True},
            success=True,
        )


class _UnusedService:
    def __getattr__(self, name):
        raise AssertionError(f"deadline should stop chat before calling {name}")


class _ResourceCounter:
    def __init__(self) -> None:
        self.calls = 0

    def close(self) -> None:
        self.calls += 1


class _QuiescentTaskService:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self, timeout_seconds: float = 5.0) -> bool:
        self.close_calls += 1
        return True


class RuntimeConcurrencyAcceptanceTest(unittest.TestCase):
    def test_concurrent_knowledge_uploads_keep_both_index_entries(self):
        root = Path.cwd() / ".tmp" / f"knowledge-concurrency-{uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, root, True)
        with patch.dict(os.environ, {"MYAI_CHROMA_MODE": "ephemeral"}, clear=False):
            service = KnowledgeService(
                base_dir=str(root),
                embedding_client=StubEmbedding(),
                collection_name=f"knowledge_concurrency_{uuid4().hex}",
                embedding_provider="stub",
                embedding_model_id="stub",
            )

        start = threading.Barrier(2)
        documents = [
            ("alpha.txt", b"alpha concurrent document with enough distinct readable content"),
            ("beta.txt", b"beta concurrent document with another distinct readable payload"),
        ]

        def upload(item):
            start.wait(timeout=2.0)
            return service.upload_file("concurrent-owner", item[0], item[1])

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(upload, documents))

        index_path = root / "concurrent-owner" / "index.json"
        persisted = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(len(results), 2)
        self.assertEqual({item["file_name"] for item in persisted}, {"alpha.txt", "beta.txt"})
        self.assertEqual(
            {item["file_name"] for item in service.list_files("concurrent-owner")},
            {"alpha.txt", "beta.txt"},
        )

    def test_task_backpressure_rejects_without_creating_an_extra_run(self):
        started = threading.Event()
        release = threading.Event()
        task_executor = _CloseAwareExecutor()
        store = TaskRunStore()
        service = TaskService(
            rec_planner=None,
            task_executor=task_executor,
            stats=None,
            run_store=store,
            max_pending_tasks=1,
        )

        def blocking_execute(_run):
            started.set()
            release.wait(timeout=2.0)

        service._execute_run = blocking_execute
        try:
            service.start_background_task("first", user_id="owner")
            self.assertTrue(started.wait(timeout=1.0))
            with self.assertRaises(AppError) as raised:
                service.start_background_task("second", user_id="owner")
            self.assertEqual(raised.exception.info.code, ErrorCode.RATE_LIMITED)
            self.assertTrue(raised.exception.info.retryable)
            self.assertEqual(len(store.list_runs(user_id="owner")), 1)
        finally:
            release.set()
            self.assertTrue(service.close(timeout_seconds=1.0))

    def test_task_backpressure_still_replays_existing_idempotent_run(self):
        started = threading.Event()
        release = threading.Event()
        store = TaskRunStore()
        service = TaskService(
            rec_planner=None,
            task_executor=_CloseAwareExecutor(),
            stats=None,
            run_store=store,
            max_pending_tasks=1,
        )

        def blocking_execute(_run):
            started.set()
            release.wait(timeout=2.0)

        service._execute_run = blocking_execute
        try:
            first = service.start_background_task(
                "first",
                user_id="owner",
                idempotency_key="same-logical-task",
            )
            self.assertTrue(started.wait(timeout=1.0))
            replay = service.start_background_task(
                "first",
                user_id="owner",
                idempotency_key="same-logical-task",
            )
            self.assertEqual(replay["task_run_id"], first["task_run_id"])
            self.assertEqual(len(store.list_runs(user_id="owner")), 1)
        finally:
            release.set()
            self.assertTrue(service.close(timeout_seconds=1.0))

    def test_task_close_keeps_executor_open_until_blocking_worker_finishes(self):
        started = threading.Event()
        release = threading.Event()
        task_executor = _CloseAwareExecutor()
        service = TaskService(
            rec_planner=None,
            task_executor=task_executor,
            stats=None,
            max_pending_tasks=1,
        )

        def blocking_execute(_run):
            started.set()
            release.wait(timeout=2.0)

        service._execute_run = blocking_execute
        service.start_background_task("blocking", user_id="owner")
        self.assertTrue(started.wait(timeout=1.0))
        self.assertFalse(service.close(timeout_seconds=0.01))
        self.assertEqual(task_executor.close_calls, 0)

        release.set()
        self.assertTrue(service.close(timeout_seconds=1.0))
        self.assertEqual(task_executor.close_calls, 1)

    def test_task_deadline_marks_slow_planning_as_timeout(self):
        planner = _SlowPlanner(delay_seconds=0.2)
        service = TaskService(
            rec_planner=planner,
            task_executor=_CloseAwareExecutor(),
            stats=_Stats(),
            task_deadline_seconds=0.1,
        )
        self.addCleanup(service.close)

        decision = service.handle_task("slow planning", user_id="owner")

        self.assertEqual(planner.calls, 1)
        self.assertFalse(decision.success)
        self.assertEqual(decision.status, "failed")
        self.assertEqual(
            decision.result["error_info"]["code"],
            ErrorCode.OPERATION_TIMEOUT.value,
        )
        self.assertEqual(decision.result["error_info"]["operation"], "task.plan")

    def test_chat_deadline_is_propagated_to_child_task_and_enforced(self):
        clock = _ManualClock()
        deadline = Deadline.after(1.0, clock=clock)
        task_service = _DeadlineExpiringTaskService(clock)
        agent_service = AgentService(
            memory_service=_UnusedService(),
            knowledge_service=_UnusedService(),
            task_service=task_service,
            chat_llm=_UnusedService(),
            run_store=AgentRunStore(),
            chat_deadline_seconds=1.0,
        )

        with patch.object(Deadline, "after", return_value=deadline):
            with self.assertRaises(AppError) as raised:
                agent_service.generate_reply("owner", "slow child", conversation_id=7)

        self.assertIs(task_service.deadline, deadline)
        self.assertEqual(raised.exception.info.code, ErrorCode.OPERATION_TIMEOUT)
        self.assertEqual(raised.exception.info.operation, "task.handle")

    def test_chat_deadline_includes_waiting_for_conversation_lock(self):
        agent_service = AgentService(
            memory_service=_UnusedService(),
            knowledge_service=_UnusedService(),
            task_service=_UnusedService(),
            chat_llm=_UnusedService(),
            run_store=AgentRunStore(),
            chat_deadline_seconds=0.02,
        )
        conversation_lock = agent_service._conversation_lock("owner", 7)
        locked = threading.Event()
        release = threading.Event()

        def hold_conversation_lock():
            with conversation_lock:
                locked.set()
                release.wait(timeout=2.0)

        holder = threading.Thread(target=hold_conversation_lock)
        holder.start()
        self.assertTrue(locked.wait(timeout=1.0))
        try:
            with self.assertRaises(AppError) as raised:
                agent_service.generate_reply("owner", "blocked chat", conversation_id=7)
            self.assertEqual(raised.exception.info.code, ErrorCode.OPERATION_TIMEOUT)
            self.assertEqual(raised.exception.info.operation, "chat.conversation_lock")
        finally:
            release.set()
            holder.join(timeout=1.0)
        self.assertFalse(holder.is_alive())

    def test_runtime_does_not_release_resources_while_scheduler_is_blocked(self):
        started = threading.Event()
        release = threading.Event()

        def blocking_maintenance(_user_id):
            started.set()
            release.wait(timeout=2.0)
            return {}

        scheduler = MemoryMaintenanceScheduler(
            blocking_maintenance,
            debounce_seconds=0.0,
            idle_poll_seconds=0.01,
        )
        scheduler.start()
        scheduler.schedule("owner")
        self.assertTrue(started.wait(timeout=1.0))
        self.addCleanup(release.set)
        self.addCleanup(scheduler.stop, timeout_seconds=1.0)

        resource = _ResourceCounter()
        resources = ExitStack()
        resources.callback(resource.close)
        placeholder = object()
        task_service = _QuiescentTaskService()
        runtime = AppRuntime(
            settings=placeholder,
            runtime_settings=RuntimeSettings(
                database_path=Path("runtime-concurrency-test.db"),
                task_shutdown_timeout_seconds=0.01,
                memory_maintenance_shutdown_timeout_seconds=0.01,
            ),
            embedding_client=placeholder,
            chroma_client=placeholder,
            runtime_repository=placeholder,
            agent_run_store=placeholder,
            task_run_store=placeholder,
            memory_service=placeholder,
            knowledge_service=placeholder,
            task_service=task_service,
            agent_service=placeholder,
            chat_llm=placeholder,
            task_llm=placeholder,
            maintenance_scheduler=scheduler,
            _resources=resources,
        )

        with self.assertRaisesRegex(RuntimeError, "memory maintenance worker did not stop"):
            runtime.close()
        self.assertFalse(runtime.closed)
        self.assertEqual(resource.calls, 0)

        release.set()
        runtime.close()
        self.assertTrue(runtime.closed)
        self.assertEqual(resource.calls, 1)


if __name__ == "__main__":
    unittest.main()
