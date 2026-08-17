import threading
import time
import unittest

from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.maintenance.scheduler import MemoryMaintenanceScheduler
from app.memory.mem_service import MemoryService
from app.memory.store.in_mem_store import MemoryStore
from app.runtime.error_model import ErrorCode
from app.runtime.resilience import BackoffPolicy


class FakeClock:
    def __init__(self) -> None:
        self.value = 50.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class MemoryMaintenanceSchedulerTest(unittest.TestCase):
    def test_coalesces_repeated_user_requests(self):
        calls: list[str] = []
        scheduler = MemoryMaintenanceScheduler(
            lambda user_id: calls.append(user_id) or {"ok": True},
            debounce_seconds=0,
        )

        scheduler.schedule("u1")
        scheduler.schedule("u1")
        scheduler.schedule("u1")

        self.assertTrue(scheduler.run_due_once())
        self.assertFalse(scheduler.run_due_once())
        self.assertEqual(calls, ["u1"])
        status = scheduler.status("u1")
        self.assertEqual(status["requested_generation"], 3)
        self.assertEqual(status["completed_generation"], 3)
        self.assertFalse(status["pending"])

    def test_change_arriving_during_maintenance_schedules_follow_up(self):
        calls: list[str] = []
        scheduler = None

        def maintain(user_id: str):
            calls.append(user_id)
            if len(calls) == 1:
                scheduler.schedule(user_id)
            return {"call": len(calls)}

        scheduler = MemoryMaintenanceScheduler(maintain, debounce_seconds=0)
        scheduler.schedule("u1")

        self.assertTrue(scheduler.run_due_once())
        self.assertTrue(scheduler.status("u1")["pending"])
        self.assertTrue(scheduler.run_due_once())
        self.assertEqual(calls, ["u1", "u1"])

    def test_transient_failure_uses_bounded_backoff(self):
        clock = FakeClock()
        calls = 0

        def maintain(user_id: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("database temporarily unavailable")
            return {"ok": True}

        scheduler = MemoryMaintenanceScheduler(
            maintain,
            debounce_seconds=0,
            clock=clock,
            random_source=lambda: 1.0,
            backoff_policy=BackoffPolicy(
                max_attempts=3,
                base_delay_seconds=0.5,
                max_delay_seconds=2.0,
                jitter_ratio=0,
            ),
        )
        scheduler.schedule("u1")

        self.assertTrue(scheduler.run_due_once())
        status = scheduler.status("u1")
        self.assertTrue(status["pending"])
        self.assertEqual(status["last_error"]["code"], ErrorCode.DEPENDENCY_UNAVAILABLE.value)
        self.assertFalse(scheduler.run_due_once())
        clock.advance(0.5)
        self.assertTrue(scheduler.run_due_once())
        self.assertFalse(scheduler.status("u1")["pending"])

    def test_permanent_failure_stops_until_new_generation(self):
        calls = 0

        def maintain(user_id: str):
            nonlocal calls
            calls += 1
            raise ValueError("invalid memory state")

        scheduler = MemoryMaintenanceScheduler(maintain, debounce_seconds=0)
        scheduler.schedule("u1")

        self.assertTrue(scheduler.run_due_once())
        self.assertFalse(scheduler.status("u1")["pending"])
        self.assertEqual(scheduler.status("u1")["last_error"]["code"], ErrorCode.INVALID_ARGUMENT.value)
        scheduler.schedule("u1")
        self.assertTrue(scheduler.run_due_once())
        self.assertEqual(calls, 2)

    def test_two_workers_keep_other_users_moving_when_one_user_blocks(self):
        first_started = threading.Event()
        release_first = threading.Event()
        second_completed = threading.Event()

        def maintain(user_id: str):
            if user_id == "blocked-user":
                first_started.set()
                release_first.wait(timeout=2.0)
            else:
                second_completed.set()
            return {"user_id": user_id}

        scheduler = MemoryMaintenanceScheduler(
            maintain,
            debounce_seconds=0,
            idle_poll_seconds=0.01,
            worker_count=2,
        )
        scheduler.schedule("blocked-user")
        scheduler.start()
        try:
            self.assertTrue(first_started.wait(timeout=1.0))
            scheduler.schedule("healthy-user")
            self.assertTrue(second_completed.wait(timeout=1.0))
        finally:
            release_first.set()
            self.assertTrue(scheduler.stop(timeout_seconds=1.0))

    def test_completed_batch_past_deadline_is_recorded_as_timeout(self):
        scheduler = MemoryMaintenanceScheduler(
            lambda _user_id: time.sleep(0.02) or {"ok": True},
            debounce_seconds=0,
            maintenance_timeout_seconds=0.005,
            backoff_policy=BackoffPolicy(max_attempts=1),
        )
        scheduler.schedule("slow-user")

        self.assertTrue(scheduler.run_due_once())

        status = scheduler.status("slow-user")
        self.assertFalse(status["pending"])
        self.assertEqual(status["last_error"]["code"], ErrorCode.OPERATION_TIMEOUT.value)

    def test_foreground_memory_calls_do_not_wait_for_active_maintenance(self):
        service = MemoryService(embedding_client=StubEmbedding(), memory_store=MemoryStore())
        maintenance_started = threading.Event()
        release_maintenance = threading.Event()

        def blocking_maintenance(_user_id: str, *, deadline=None):
            maintenance_started.set()
            release_maintenance.wait(timeout=2.0)
            return {"memory_count": 0}

        service._maintenance_unlocked = blocking_maintenance
        worker = threading.Thread(target=service.try_maintenance, args=("owner",))
        worker.start()
        self.assertTrue(maintenance_started.wait(timeout=1.0))
        try:
            started_at = time.perf_counter()
            write = service.try_process_user_input("owner", "I like Python")
            selected, explanations = service.try_retrieve_for_context_with_explanation(
                "owner",
                "What do I like?",
            )
            elapsed = time.perf_counter() - started_at
            self.assertLess(elapsed, 0.1)
            self.assertTrue(write["deferred"])
            self.assertEqual(selected, [])
            self.assertTrue(explanations[0]["factors"]["deferred"])
        finally:
            release_maintenance.set()
            worker.join(timeout=1.0)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
