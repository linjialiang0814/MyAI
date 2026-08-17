import hashlib
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.runtime.agent_store import AgentRunStore
from app.runtime.agent_trace import AgentStep
from app.runtime.sqlite_repository import (
    IdempotencyConflictError,
    RunLinkMismatchError,
    SQLiteRuntimeRepository,
)
from app.task.runtime import TaskRunStore


class SQLiteRuntimeRepositoryTest(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp" / "runtime-repository-tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.database_path = temp_root / f"runtime-{uuid4()}.db"
        self.repository = SQLiteRuntimeRepository(self.database_path)

    def tearDown(self):
        self.repository.close()
        for path in self.database_path.parent.glob(f"{self.database_path.name}*"):
            path.unlink(missing_ok=True)

    def test_migration_and_connection_safety_settings_are_idempotent(self):
        settings = self.repository.pragma_settings()

        self.assertEqual(settings["journal_mode"], "wal")
        self.assertEqual(settings["foreign_keys"], 1)
        self.assertEqual(settings["busy_timeout"], 5_000)
        self.assertEqual([item["version"] for item in self.repository.applied_migrations()], [1])

        reopened = SQLiteRuntimeRepository(self.database_path)
        self.assertEqual([item["version"] for item in reopened.applied_migrations()], [1])
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_agent_run_round_trip_uses_metadata_allowlist_and_redaction(self):
        store = AgentRunStore(self.repository)
        run = store.create("owner-1", conversation_id=41)
        run.steps.append(
            AgentStep(
                name="memory.retrieve",
                status="completed",
                started_at="2026-08-11T01:00:00+00:00",
                finished_at="2026-08-11T01:00:01+00:00",
                latency_ms=10.5,
                input_summary="password=hunter2",
                output_summary="memories=1",
                metadata={
                    "selected_count": 1,
                    "token": "agent-secret-value",
                    "memories": [
                        {
                            "memory_id": "mem-1",
                            "mem_type": "fact",
                            "content": "raw private biography sentence",
                            "source": "chat_extraction",
                        }
                    ],
                    "unapproved_raw_payload": "must not be stored",
                },
            )
        )
        run.finish()
        store.save(run)

        restarted_store = AgentRunStore(SQLiteRuntimeRepository(self.database_path))
        restored = restarted_store.get(run.run_id)

        self.assertIsNotNone(restored)
        self.assertEqual(restored.user_id, "owner-1")
        self.assertEqual(restored.conversation_id, 41)
        self.assertEqual(restored.status, "completed")
        self.assertEqual(restored.steps[0].input_summary, "password=[redacted-secret]")
        self.assertEqual(restored.steps[0].metadata["selected_count"], 1)
        self.assertEqual(restored.steps[0].metadata["memories_count"], 1)
        self.assertEqual(restored.steps[0].metadata["memories"][0]["memory_id"], "mem-1")
        self.assertNotIn("content", restored.steps[0].metadata["memories"][0])
        self.assertNotIn("token", restored.steps[0].metadata)
        self.assertNotIn("unapproved_raw_payload", restored.steps[0].metadata)
        self._assert_database_omits(
            "hunter2",
            "agent-secret-value",
            "raw private biography sentence",
            "must not be stored",
        )

    def test_task_run_round_trip_preserves_links_steps_events_and_safe_payload(self):
        agent_store = AgentRunStore(self.repository)
        agent_run = agent_store.create("owner-2", conversation_id=77)
        task_store = TaskRunStore(repository=self.repository)
        task_run = task_store.create(
            "owner-2",
            "calculate 1 + 2",
            agent_run_id=agent_run.run_id,
            conversation_id=77,
            idempotency_key="request-77-1",
        )
        task_store.mark_planning(task_run)
        plan = {
            "source": "rule",
            "need_tool": True,
            "steps": [{"step_id": "step1", "tool_name": "calculator"}],
        }
        steps = [
            SimpleNamespace(
                step_id="step1",
                description="Calculate the expression",
                tool_name="calculator",
                tool_args={"expression": "1 + 2"},
            )
        ]
        task_store.set_plan(task_run, plan, steps)
        task_store.mark_running(task_run)
        task_store.start_step(
            task_run,
            "step1",
            {"expression": "1 + 2", "api_key": "task-secret-value"},
        )
        task_store.complete_step(
            task_run,
            "step1",
            {
                "success": True,
                "data": {
                    "value": 3,
                    "content": "raw tool document body",
                },
            },
            4.25,
        )
        task_store.succeed(task_run, {"success": True, "summary": "Result is 3"}, latency_ms=4.25)

        restarted_store = TaskRunStore(repository=SQLiteRuntimeRepository(self.database_path))
        restored = restarted_store.get(task_run.task_run_id)

        self.assertIsNotNone(restored)
        self.assertEqual(restored.agent_run_id, agent_run.run_id)
        self.assertEqual(restored.conversation_id, 77)
        self.assertTrue(restored.idempotency_key.startswith("sha256:"))
        self.assertNotIn("request-77-1", restored.idempotency_key)
        self.assertEqual(restored.content, "calculate 1 + 2")
        self.assertEqual(restored.status, "succeeded")
        self.assertTrue(restored.success)
        self.assertEqual(restored.steps[0].status, "succeeded")
        self.assertEqual(restored.steps[0].tool_args["expression"], "1 + 2")
        self.assertEqual(restored.steps[0].tool_args["api_key"], "[redacted-secret]")
        self.assertIn("[redacted-body", restored.steps[0].result["data"]["content"])
        self.assertTrue(restored.steps[0].events)
        self.assertEqual(restored.events[-1].type, "task.completed")
        self.assertEqual(
            [run.task_run_id for run in restarted_store.list_runs(user_id="owner-2")],
            [task_run.task_run_id],
        )
        self._assert_database_omits("task-secret-value", "raw tool document body")

    def test_agent_foreign_key_is_enforced_for_linked_task(self):
        store = TaskRunStore(repository=self.repository)

        with self.assertRaises(sqlite3.IntegrityError):
            store.create(
                "owner",
                "linked task",
                agent_run_id="missing-agent-run",
                conversation_id=1,
            )

    def test_linked_task_must_match_agent_owner_and_conversation(self):
        agent = AgentRunStore(self.repository).create("owner", conversation_id=9)
        store = TaskRunStore(repository=self.repository)

        with self.assertRaises(RunLinkMismatchError):
            store.create(
                "different-owner",
                "linked task",
                agent_run_id=agent.run_id,
                conversation_id=9,
            )
        with self.assertRaises(RunLinkMismatchError):
            store.create(
                "owner",
                "linked task",
                agent_run_id=agent.run_id,
                conversation_id=10,
            )

    def test_idempotency_claim_is_atomic_replayable_and_conflict_safe(self):
        other_repository = SQLiteRuntimeRepository(self.database_path)

        def claim(repository):
            return repository.claim_idempotency(
                scope="chat",
                user_id="owner",
                idempotency_key="request-1",
                request_hash="hash-a",
                resource_type="agent_run",
                resource_id="run-1",
                expires_at="2026-08-12T00:00:00+00:00",
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            claims = list(executor.map(claim, [self.repository, other_repository]))

        self.assertEqual(sorted(item.claimed for item in claims), [False, True])
        self.assertTrue(all(item.record.resource_id == "run-1" for item in claims))
        completed = self.repository.complete_idempotency(
            scope="chat",
            user_id="owner",
            idempotency_key="request-1",
            request_hash="hash-a",
            response={"success": True, "token": "response-secret", "content": "private response body"},
            resource_type="agent_run",
            resource_id="run-1",
        )
        replay = other_repository.get_idempotency(
            scope="chat",
            user_id="owner",
            idempotency_key="request-1",
        )
        repeated = other_repository.complete_idempotency(
            scope="chat",
            user_id="owner",
            idempotency_key="request-1",
            request_hash="hash-a",
            response={"success": False, "replacement": "must not overwrite"},
            resource_type="agent_run",
            resource_id="run-1",
        )

        self.assertEqual(completed.state, "completed")
        self.assertEqual(replay.response["token"], "[redacted-secret]")
        self.assertIn("[redacted-body", replay.response["content"])
        self.assertEqual(repeated.response, replay.response)
        with self.assertRaises(IdempotencyConflictError):
            self.repository.claim_idempotency(
                scope="chat",
                user_id="owner",
                idempotency_key="request-1",
                request_hash="hash-b",
            )
        self._assert_database_omits("response-secret", "private response body")

    def test_agent_store_create_or_get_and_response_survive_restart(self):
        first_store = AgentRunStore(self.repository)
        first, created = first_store.create_or_get(
            "owner-agent",
            22,
            kind="chat",
            idempotency_key="agent-request-1",
            request_hash="agent-hash-1",
        )
        first_store.save_response(first, {"reply": "password is response-hunter"})

        restarted = AgentRunStore(SQLiteRuntimeRepository(self.database_path))
        replay, replay_created = restarted.create_or_get(
            "owner-agent",
            22,
            kind="chat",
            idempotency_key="agent-request-1",
            request_hash="agent-hash-1",
        )

        self.assertTrue(created)
        self.assertFalse(replay_created)
        self.assertEqual(replay.run_id, first.run_id)
        self.assertEqual(replay.response, {"reply": "password=[redacted-secret]"})
        self.assertEqual(replay.status, "completed")
        record = self.repository.get_idempotency(
            scope="agent_run:chat",
            user_id="owner-agent",
            idempotency_key="agent-request-1",
        )
        self.assertEqual(record.state, "completed")
        self._assert_database_omits("response-hunter")

    def test_task_store_create_or_get_reuses_same_request_and_rejects_conflict(self):
        store = TaskRunStore(repository=self.repository)
        first, created = store.create_or_get(
            "owner-task",
            "calculate 2 + 2",
            idempotency_key="task-request-1",
        )
        store.succeed(first, {"success": True, "summary": "Result is 4"}, latency_ms=1.0)

        restarted = TaskRunStore(repository=SQLiteRuntimeRepository(self.database_path))
        replay, replay_created = restarted.create_or_get(
            "owner-task",
            "calculate 2 + 2",
            idempotency_key="task-request-1",
        )

        self.assertTrue(created)
        self.assertFalse(replay_created)
        self.assertEqual(replay.task_run_id, first.task_run_id)
        self.assertEqual(replay.status, "succeeded")
        record = self.repository.get_idempotency(
            scope="task_run:standalone",
            user_id="owner-task",
            idempotency_key="task-request-1",
        )
        self.assertEqual(record.state, "completed")
        with self.assertRaises(IdempotencyConflictError):
            restarted.create_or_get(
                "owner-task",
                "different task body",
                idempotency_key="task-request-1",
            )

    def test_secret_like_idempotency_keys_are_hashed_without_colliding(self):
        store = AgentRunStore(self.repository)
        first, first_created = store.create_or_get(
            "owner-secret-key",
            kind="chat",
            idempotency_key="token=alpha",
            request_hash="hash-alpha",
        )
        second, second_created = store.create_or_get(
            "owner-secret-key",
            kind="chat",
            idempotency_key="token=beta",
            request_hash="hash-beta",
        )

        self.assertTrue(first_created)
        self.assertTrue(second_created)
        self.assertNotEqual(first.run_id, second.run_id)
        with closing(sqlite3.connect(self.database_path)) as connection:
            stored = [row[0] for row in connection.execute(
                "SELECT idempotency_key FROM agent_runs ORDER BY run_id"
            )]
        self.assertTrue(all(value.startswith("sha256:") for value in stored))
        self._assert_database_omits("token=alpha", "token=beta")

    def test_digest_shaped_external_key_does_not_alias_an_existing_raw_key(self):
        store = AgentRunStore(self.repository)
        raw_key = "plain-key"
        digest_shaped_key = "sha256:" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        first, first_created = store.create_or_get(
            "owner-digest-shape",
            kind="chat",
            idempotency_key=raw_key,
            request_hash="hash-plain",
        )
        second, second_created = store.create_or_get(
            "owner-digest-shape",
            kind="chat",
            idempotency_key=digest_shaped_key,
            request_hash="hash-literal-digest",
        )

        self.assertTrue(first_created)
        self.assertTrue(second_created)
        self.assertNotEqual(first.run_id, second.run_id)
        with closing(sqlite3.connect(self.database_path)) as connection:
            stored = [row[0] for row in connection.execute(
                "SELECT idempotency_key FROM agent_runs WHERE user_id = ? ORDER BY run_id",
                ("owner-digest-shape",),
            )]
        self.assertEqual(len(stored), 2)
        self.assertEqual(len(set(stored)), 2)
        self._assert_database_omits(raw_key)

    def test_resource_materialization_failure_rolls_back_idempotency_claim(self):
        store = TaskRunStore(repository=self.repository)

        with self.assertRaises(sqlite3.IntegrityError):
            store.create_or_get(
                "owner-atomic",
                "bad parent",
                agent_run_id="missing-parent",
                idempotency_key="atomic-request",
            )

        self.assertIsNone(
            self.repository.get_idempotency(
                scope="task_run:standalone",
                user_id="owner-atomic",
                idempotency_key="atomic-request",
            )
        )

    def test_task_idempotency_namespaces_do_not_collide(self):
        store = TaskRunStore(repository=self.repository)
        standalone, _ = store.create_or_get(
            "owner-scopes",
            "standalone",
            idempotency_key="same-key",
            idempotency_scope="standalone",
        )
        child, _ = store.create_or_get(
            "owner-scopes",
            "chat child",
            idempotency_key="same-key",
            idempotency_scope="chat_child",
        )

        self.assertNotEqual(standalone.task_run_id, child.task_run_id)

    def test_agent_identity_cannot_change_after_linked_task_exists(self):
        agent_store = AgentRunStore(self.repository)
        agent = agent_store.create("owner-original", conversation_id=11)
        TaskRunStore(self.repository).create(
            "owner-original",
            "linked",
            agent_run_id=agent.run_id,
            conversation_id=11,
        )
        agent.user_id = "owner-other"
        agent.conversation_id = 12

        with self.assertRaises(RunLinkMismatchError):
            agent_store.save(agent)

    def test_task_identity_and_parent_link_cannot_change_after_creation(self):
        agent = AgentRunStore(self.repository).create("owner-task-identity", conversation_id=31)
        task = TaskRunStore(self.repository).create(
            "owner-task-identity",
            "linked task",
            agent_run_id=agent.run_id,
            conversation_id=31,
            idempotency_scope="standalone",
        )
        task.user_id = "different-owner"

        with self.assertRaises(RunLinkMismatchError):
            self.repository.save_task_run(task)

    def test_task_query_filters_by_agent_before_applying_limit(self):
        agent_store = AgentRunStore(self.repository)
        task_store = TaskRunStore(self.repository)
        target_parent = agent_store.create("owner-agent-filter", conversation_id=41)
        target = task_store.create(
            "owner-agent-filter",
            "target child",
            agent_run_id=target_parent.run_id,
            conversation_id=41,
        )
        other_parent = agent_store.create("owner-agent-filter", conversation_id=42)
        task_store.create(
            "owner-agent-filter",
            "newer unrelated child",
            agent_run_id=other_parent.run_id,
            conversation_id=42,
        )

        selected = self.repository.list_task_runs(
            user_id="owner-agent-filter",
            agent_run_id=target_parent.run_id,
            limit=1,
        )

        self.assertEqual([run.task_run_id for run in selected], [target.task_run_id])

    def test_recovery_fails_nonterminal_runs_once_without_replay(self):
        agent_store = AgentRunStore(self.repository)
        agent, _ = agent_store.create_or_get(
            "owner-recovery",
            55,
            idempotency_key="agent-recovery-request",
            request_hash="agent-recovery-hash",
        )
        task_store = TaskRunStore(repository=self.repository)
        task, _ = task_store.create_or_get(
            "owner-recovery",
            "long running task",
            agent_run_id=agent.run_id,
            conversation_id=55,
            idempotency_key="task-recovery-request",
        )
        task_store.mark_running(task)

        recovered = self.repository.recover_incomplete_runs()
        recovered_again = self.repository.recover_incomplete_runs()
        restarted_agent = AgentRunStore(SQLiteRuntimeRepository(self.database_path)).get(agent.run_id)
        restarted_task = TaskRunStore(repository=SQLiteRuntimeRepository(self.database_path)).get(task.task_run_id)

        self.assertEqual(recovered, {"agent_runs": 1, "task_runs": 1})
        self.assertEqual(recovered_again, {"agent_runs": 0, "task_runs": 0})
        self.assertEqual(restarted_agent.status, "failed")
        self.assertEqual(restarted_agent.error_code, "RUNTIME_RESTART")
        self.assertTrue(restarted_agent.retryable)
        self.assertEqual(restarted_task.status, "failed")
        self.assertFalse(restarted_task.success)
        self.assertTrue(restarted_task.error.startswith("RUNTIME_RESTART:"))
        self.assertEqual(restarted_task.events[-1].type, "task.recovered_after_restart")
        self.assertEqual(
            self.repository.get_idempotency(
                scope="agent_run:chat",
                user_id="owner-recovery",
                idempotency_key="agent-recovery-request",
            ).state,
            "failed",
        )
        self.assertEqual(
            self.repository.get_idempotency(
                scope="task_run:standalone",
                user_id="owner-recovery",
                idempotency_key="task-recovery-request",
            ).state,
            "failed",
        )

    def test_list_does_not_replace_active_task_object_or_lose_cancellation(self):
        store = TaskRunStore(repository=self.repository)
        run = store.create("owner-cache", "active task")
        store.mark_running(run)

        listed = store.list_runs(user_id="owner-cache")
        self.assertIs(listed[0], run)
        store.request_cancel(listed[0])

        self.assertTrue(run.cancel_requested)
        self.assertIs(store.get(run.task_run_id), run)

    def test_recovery_finishes_running_step_with_parent_task(self):
        agent = AgentRunStore(self.repository).create("owner-step", conversation_id=61)
        store = TaskRunStore(repository=self.repository)
        run = store.create(
            "owner-step",
            "run a long tool",
            agent_run_id=agent.run_id,
            conversation_id=61,
        )
        store.set_plan(
            run,
            {"source": "test", "need_tool": True},
            [SimpleNamespace(step_id="s1", description="slow", tool_name="slow", tool_args={})],
        )
        store.mark_running(run)
        store.start_step(run, "s1", {})

        self.repository.recover_incomplete_runs()
        restored = TaskRunStore(SQLiteRuntimeRepository(self.database_path)).get(run.task_run_id)

        self.assertEqual(restored.status, "failed")
        self.assertEqual(restored.steps[0].status, "failed")
        self.assertIsNotNone(restored.steps[0].finished_at)
        self.assertTrue(restored.steps[0].error.startswith("RUNTIME_RESTART:"))

    def test_recovery_reconciles_terminal_standalone_child_before_failing_parent(self):
        agent_store = AgentRunStore(self.repository)
        parent = agent_store.create("owner-standalone", kind="standalone_task")
        task_store = TaskRunStore(repository=self.repository)
        child = task_store.create(
            "owner-standalone",
            "already completed",
            agent_run_id=parent.run_id,
        )
        task_store.succeed(child, {"success": True}, latency_ms=1.0)

        recovered = self.repository.recover_incomplete_runs()
        restored = AgentRunStore(SQLiteRuntimeRepository(self.database_path)).get(parent.run_id)

        self.assertEqual(recovered["agent_runs"], 0)
        self.assertEqual(restored.status, "completed")
        self.assertEqual(restored.response["task_run_id"], child.task_run_id)
        self.assertTrue(restored.response["success"])

    def test_no_argument_task_store_remains_in_memory_compatible(self):
        store = TaskRunStore()
        run = store.create("owner", "private task")

        self.assertIs(store.get(run.task_run_id), run)
        self.assertIsNone(run.agent_run_id)
        self.assertIsNone(run.conversation_id)
        self.assertIsNone(run.idempotency_key)
        self.assertEqual(run.events[0].type, "task.created")

    def _assert_database_omits(self, *values: str) -> None:
        database_bytes = b""
        for path in self.database_path.parent.glob(f"{self.database_path.name}*"):
            database_bytes += path.read_bytes()
        for value in values:
            self.assertNotIn(value.encode("utf-8"), database_bytes)


if __name__ == "__main__":
    unittest.main()
