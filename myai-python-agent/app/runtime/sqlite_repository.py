from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.runtime.agent_trace import AgentRun, AgentStep, utc_now_iso
from app.runtime.storage_redaction import (
    sanitize_agent_metadata,
    sanitize_structured_for_storage,
    sanitize_text_for_storage,
)
from app.task.runtime import TaskEvent, TaskRun, TaskStepRun


_MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""
_MIGRATION_GLOB = "[0-9][0-9][0-9][0-9]_*.sql"


class MigrationChecksumError(RuntimeError):
    pass


class IdempotencyConflictError(RuntimeError):
    pass


class IdempotencyInProgressError(RuntimeError):
    pass


class RunLinkMismatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class IdempotencyRecord:
    scope: str
    user_id: str
    idempotency_key: str
    request_hash: str
    resource_type: str | None
    resource_id: str | None
    state: str
    response: Any
    created_at: str
    updated_at: str
    expires_at: str | None


class _StoredIdempotencyDigest(str):
    """Marker for a digest loaded from SQLite, never API-provided text."""


@dataclass(frozen=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    claimed: bool


class SQLiteRuntimeRepository:
    """Durable, privacy-bounded storage for agent and task run snapshots.

    Connections are intentionally short lived so synchronous FastAPI workers and the
    task background executor never share a sqlite3 connection across threads.
    """

    def __init__(self, database_path: str | Path, *, busy_timeout_ms: int = 5_000) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.busy_timeout_ms = max(1, int(busy_timeout_ms))
        self._write_lock = threading.RLock()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._write_lock, closing(self._connect()) as connection:
            connection.execute(_MIGRATION_TABLE_SQL)
            connection.commit()

        migration_paths = self._migration_paths()
        if not migration_paths:
            raise FileNotFoundError("No runtime database migrations were found")
        for migration_path in migration_paths:
            self._apply_migration(migration_path)

    def save_agent_run(self, run: AgentRun) -> None:
        now = utc_now_iso()
        with self._write_lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_agent_identity(connection, run)
            connection.execute(
                """
                INSERT INTO agent_runs (
                    run_id, kind, user_id, conversation_id, idempotency_key,
                    request_hash, status, response_json, error_code, error_message,
                    retryable, started_at, finished_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    response_json = excluded.response_json,
                    error_code = excluded.error_code,
                    error_message = excluded.error_message,
                    retryable = excluded.retryable,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    updated_at = excluded.updated_at
                """,
                (
                    run.run_id,
                    run.kind,
                    run.user_id,
                    run.conversation_id,
                    _idempotency_key_digest(run.idempotency_key),
                    run.request_hash,
                    run.status,
                    _json_dump(sanitize_structured_for_storage(run.response)) if run.response is not None else None,
                    sanitize_text_for_storage(run.error_code, max_chars=128),
                    sanitize_text_for_storage(run.error_message, max_chars=4_096),
                    _bool_to_db(run.retryable),
                    run.started_at,
                    run.finished_at,
                    run.started_at,
                    now,
                ),
            )
            connection.execute("DELETE FROM agent_steps WHERE agent_run_id = ?", (run.run_id,))
            for ordinal, step in enumerate(run.steps):
                connection.execute(
                    """
                    INSERT INTO agent_steps (
                        agent_run_id, ordinal, name, status, started_at, finished_at,
                        latency_ms, input_summary, output_summary, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.run_id,
                        ordinal,
                        step.name,
                        step.status,
                        step.started_at,
                        step.finished_at,
                        step.latency_ms,
                        sanitize_text_for_storage(step.input_summary, max_chars=2_048),
                        sanitize_text_for_storage(step.output_summary, max_chars=2_048),
                        _json_dump(sanitize_agent_metadata(step.metadata)),
                    ),
                )
            self._sync_terminal_idempotency(
                connection,
                scope=f"agent_run:{run.kind}",
                user_id=run.user_id,
                idempotency_key=run.idempotency_key,
                request_hash=run.request_hash,
                resource_type="agent_run",
                resource_id=run.run_id,
                status=run.status,
                response=run.response,
            )
            connection.commit()

    def get_agent_run(self, run_id: str) -> AgentRun | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            return self._load_agent_run(connection, row) if row else None

    def list_agent_runs(
        self,
        *,
        user_id: str | None = None,
        conversation_id: int | None = None,
        limit: int = 20,
    ) -> list[AgentRun]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if user_id is not None:
            clauses.append("user_id = ?")
            parameters.append(user_id)
        if conversation_id is not None:
            clauses.append("conversation_id = ?")
            parameters.append(conversation_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(max(1, int(limit)))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM agent_runs{where} ORDER BY created_at DESC, run_id DESC LIMIT ?",
                parameters,
            ).fetchall()
            return [self._load_agent_run(connection, row) for row in rows]

    def save_task_run(self, run: TaskRun) -> None:
        now = utc_now_iso()
        plan = sanitize_structured_for_storage(run.plan)
        result = sanitize_structured_for_storage(run.result)
        with self._write_lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_task_parent(connection, run)
            connection.execute(
                """
                INSERT INTO task_runs (
                    task_run_id, agent_run_id, user_id, conversation_id, idempotency_key,
                    request_hash, idempotency_scope, content, status, current_step_id, plan_json, result_json, error,
                    error_code, retryable,
                    latency_ms, success, created_at, started_at, finished_at,
                    cancel_requested, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_run_id) DO UPDATE SET
                    status = excluded.status,
                    current_step_id = excluded.current_step_id,
                    plan_json = excluded.plan_json,
                    result_json = excluded.result_json,
                    error = excluded.error,
                    error_code = excluded.error_code,
                    retryable = excluded.retryable,
                    latency_ms = excluded.latency_ms,
                    success = excluded.success,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    cancel_requested = excluded.cancel_requested,
                    updated_at = excluded.updated_at
                """,
                (
                    run.task_run_id,
                    run.agent_run_id,
                    run.user_id,
                    run.conversation_id,
                    _idempotency_key_digest(run.idempotency_key),
                    run.request_hash,
                    run.idempotency_scope,
                    sanitize_text_for_storage(run.content),
                    run.status,
                    run.current_step_id,
                    _json_dump(plan) if plan is not None else None,
                    _json_dump(result) if result is not None else None,
                    sanitize_text_for_storage(run.error, max_chars=4_096),
                    run.error_code,
                    _bool_to_db(run.retryable),
                    run.latency_ms,
                    _bool_to_db(run.success),
                    run.created_at,
                    run.started_at,
                    run.finished_at,
                    int(bool(run.cancel_requested)),
                    now,
                ),
            )
            connection.execute("DELETE FROM task_events WHERE task_run_id = ?", (run.task_run_id,))
            connection.execute("DELETE FROM task_steps WHERE task_run_id = ?", (run.task_run_id,))
            for ordinal, step in enumerate(run.steps):
                connection.execute(
                    """
                    INSERT INTO task_steps (
                        task_run_id, step_id, ordinal, description, tool_name, status,
                        tool_args_json, result_json, error, latency_ms, started_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.task_run_id,
                        step.step_id,
                        ordinal,
                        sanitize_text_for_storage(step.description, max_chars=2_048),
                        step.tool_name,
                        step.status,
                        _json_dump(sanitize_structured_for_storage(step.tool_args)),
                        _json_dump(sanitize_structured_for_storage(step.result)) if step.result is not None else None,
                        sanitize_text_for_storage(step.error, max_chars=4_096),
                        step.latency_ms,
                        step.started_at,
                        step.finished_at,
                    ),
                )
            for sequence_no, event in enumerate(run.events):
                connection.execute(
                    """
                    INSERT INTO task_events (
                        event_id, task_run_id, sequence_no, type, timestamp, status,
                        step_id, message, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        run.task_run_id,
                        sequence_no,
                        event.type,
                        event.timestamp,
                        event.status,
                        event.step_id,
                        sanitize_text_for_storage(event.message, max_chars=2_048),
                        _json_dump(sanitize_structured_for_storage(event.metadata)),
                    ),
                )
            self._sync_terminal_idempotency(
                connection,
                scope=f"task_run:{run.idempotency_scope}",
                user_id=run.user_id,
                idempotency_key=run.idempotency_key,
                request_hash=run.request_hash,
                resource_type="task_run",
                resource_id=run.task_run_id,
                status=run.status,
                response=run.to_dict(),
            )
            connection.commit()

    def get_task_run(self, task_run_id: str) -> TaskRun | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM task_runs WHERE task_run_id = ?",
                (task_run_id,),
            ).fetchone()
            return self._load_task_run(connection, row) if row else None

    def list_task_runs(
        self,
        *,
        user_id: str | None = None,
        agent_run_id: str | None = None,
        limit: int = 20,
    ) -> list[TaskRun]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if user_id is not None:
            clauses.append("user_id = ?")
            parameters.append(user_id)
        if agent_run_id is not None:
            clauses.append("agent_run_id = ?")
            parameters.append(agent_run_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(max(1, int(limit)))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM task_runs{where} ORDER BY created_at DESC, task_run_id DESC LIMIT ?",
                parameters,
            ).fetchall()
            return [self._load_task_run(connection, row) for row in rows]

    def claim_idempotency(
        self,
        *,
        scope: str,
        user_id: str,
        idempotency_key: str,
        request_hash: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        expires_at: str | None = None,
        initial_resource: AgentRun | TaskRun | None = None,
    ) -> IdempotencyClaim:
        _validate_idempotency_identity(scope, user_id, idempotency_key, request_hash)
        if initial_resource is not None:
            expected_type, expected_id = _resource_identity(initial_resource)
            if resource_type not in {None, expected_type} or resource_id not in {None, expected_id}:
                raise ValueError("initial_resource identity does not match the claim")
            resource_type, resource_id = expected_type, expected_id
        stored_key = _idempotency_key_digest(idempotency_key)
        now = utc_now_iso()
        with self._write_lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM idempotency_records
                WHERE scope = ? AND user_id = ? AND idempotency_key = ?
                """,
                (scope, user_id, stored_key),
            ).fetchone()
            if row is not None:
                record = _idempotency_from_row(row)
                if record.request_hash != request_hash:
                    connection.rollback()
                    raise IdempotencyConflictError(
                        "The idempotency key is already bound to a different request"
                    )
                if initial_resource is not None and record.state in {"in_progress", "failed"}:
                    resource_exists = self._resource_exists(
                        connection,
                        record.resource_type,
                        record.resource_id,
                    )
                    if not resource_exists:
                        resource_type, resource_id = _resource_identity(initial_resource)
                        connection.execute(
                            """
                            UPDATE idempotency_records
                            SET state = 'in_progress', response_json = NULL,
                                resource_type = ?, resource_id = ?, updated_at = ?
                            WHERE scope = ? AND user_id = ? AND idempotency_key = ?
                            """,
                            (resource_type, resource_id, now, scope, user_id, stored_key),
                        )
                        self._insert_initial_resource(connection, initial_resource)
                        connection.commit()
                        claimed_row = connection.execute(
                            """
                            SELECT * FROM idempotency_records
                            WHERE scope = ? AND user_id = ? AND idempotency_key = ?
                            """,
                            (scope, user_id, stored_key),
                        ).fetchone()
                        return IdempotencyClaim(
                            record=_idempotency_from_row(claimed_row),
                            claimed=True,
                        )
                connection.commit()
                return IdempotencyClaim(record=record, claimed=False)

            connection.execute(
                """
                INSERT INTO idempotency_records (
                    scope, user_id, idempotency_key, request_hash, resource_type,
                    resource_id, state, response_json, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'in_progress', NULL, ?, ?, ?)
                """,
                (
                    scope,
                    user_id,
                    stored_key,
                    request_hash,
                    resource_type,
                    resource_id,
                    now,
                    now,
                    expires_at,
                ),
            )
            if initial_resource is not None:
                self._insert_initial_resource(connection, initial_resource)
            connection.commit()
            row = connection.execute(
                """
                SELECT * FROM idempotency_records
                WHERE scope = ? AND user_id = ? AND idempotency_key = ?
                """,
                (scope, user_id, stored_key),
            ).fetchone()
            record = _idempotency_from_row(row) if row is not None else None
            if record is None:  # pragma: no cover - defensive database invariant
                raise RuntimeError("Idempotency claim disappeared after commit")
            return IdempotencyClaim(record=record, claimed=True)

    def complete_idempotency(
        self,
        *,
        scope: str,
        user_id: str,
        idempotency_key: str,
        request_hash: str,
        state: str = "completed",
        response: Any = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> IdempotencyRecord:
        _validate_idempotency_identity(scope, user_id, idempotency_key, request_hash)
        stored_key = _idempotency_key_digest(idempotency_key)
        if state not in {"completed", "failed"}:
            raise ValueError("Completed idempotency state must be completed or failed")
        response_json = (
            _json_dump(sanitize_structured_for_storage(response))
            if response is not None
            else None
        )
        with self._write_lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM idempotency_records
                WHERE scope = ? AND user_id = ? AND idempotency_key = ?
                """,
                (scope, user_id, stored_key),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise KeyError("Idempotency claim not found")
            existing = _idempotency_from_row(row)
            if existing.request_hash != request_hash:
                connection.rollback()
                raise IdempotencyConflictError(
                    "The idempotency key is already bound to a different request"
                )
            if (
                existing.resource_type is not None
                and resource_type is not None
                and existing.resource_type != resource_type
            ) or (
                existing.resource_id is not None
                and resource_id is not None
                and existing.resource_id != resource_id
            ):
                connection.rollback()
                raise IdempotencyConflictError(
                    "The idempotency key is already bound to a different resource"
                )
            if existing.state in {"completed", "failed"}:
                connection.commit()
                return existing
            connection.execute(
                """
                UPDATE idempotency_records
                SET state = ?, response_json = ?,
                    resource_type = COALESCE(?, resource_type),
                    resource_id = COALESCE(?, resource_id),
                    updated_at = ?
                WHERE scope = ? AND user_id = ? AND idempotency_key = ?
                """,
                (
                    state,
                    response_json,
                    resource_type,
                    resource_id,
                    utc_now_iso(),
                    scope,
                    user_id,
                    stored_key,
                ),
            )
            connection.commit()
        completed = self.get_idempotency(
            scope=scope,
            user_id=user_id,
            idempotency_key=idempotency_key,
        )
        if completed is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("Idempotency record disappeared after completion")
        return completed

    def get_idempotency(
        self,
        *,
        scope: str,
        user_id: str,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        stored_key = _idempotency_key_digest(idempotency_key)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM idempotency_records
                WHERE scope = ? AND user_id = ? AND idempotency_key = ?
                """,
                (scope, user_id, stored_key),
            ).fetchone()
            return _idempotency_from_row(row) if row is not None else None

    def recover_incomplete_runs(self) -> dict[str, int]:
        """Fail stale non-terminal runs without replaying side-effecting work."""
        now = utc_now_iso()
        task_error = "RUNTIME_RESTART: task interrupted by process restart"
        with self._write_lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            # A standalone task can commit its child run immediately before the
            # process dies while finalizing the synthetic parent AgentRun. Reconcile
            # that narrow window from the durable child instead of misreporting a
            # successfully completed task as an interrupted agent run.
            connection.execute(
                """
                UPDATE agent_runs
                SET status = CASE child.status
                        WHEN 'succeeded' THEN 'completed'
                        ELSE child.status
                    END,
                    response_json = json_object(
                        'task_run_id', child.task_run_id,
                        'status', child.status,
                        'success', json(CASE WHEN child.success = 1 THEN 'true' ELSE 'false' END)
                    ),
                    error_code = CASE
                        WHEN child.status = 'failed' THEN 'task_failed'
                        WHEN child.status = 'cancelled' THEN 'cancelled'
                        ELSE NULL
                    END,
                    error_message = child.error,
                    retryable = CASE WHEN child.status IN ('failed', 'cancelled') THEN 0 ELSE NULL END,
                    finished_at = COALESCE(child.finished_at, ?),
                    updated_at = ?
                FROM task_runs AS child
                WHERE agent_runs.kind = 'standalone_task'
                  AND agent_runs.status IN ('queued', 'planning', 'running')
                  AND child.agent_run_id = agent_runs.run_id
                  AND child.status IN ('succeeded', 'failed', 'cancelled')
                  AND 1 = (
                      SELECT COUNT(*) FROM task_runs AS siblings
                      WHERE siblings.agent_run_id = agent_runs.run_id
                  )
                """,
                (now, now),
            )
            agent_rows = connection.execute(
                """
                SELECT run_id FROM agent_runs
                WHERE status IN ('queued', 'planning', 'running')
                """
            ).fetchall()
            task_rows = connection.execute(
                """
                SELECT task_run_id FROM task_runs
                WHERE status IN ('queued', 'planning', 'running')
                """
            ).fetchall()
            connection.execute(
                """
                UPDATE agent_runs
                SET status = 'failed', finished_at = ?, updated_at = ?,
                    error_code = 'RUNTIME_RESTART',
                    error_message = 'Agent run interrupted by process restart',
                    retryable = 1
                WHERE status IN ('queued', 'planning', 'running')
                """,
                (now, now),
            )
            for row in task_rows:
                task_run_id = row["task_run_id"]
                next_sequence = connection.execute(
                    """
                    SELECT COALESCE(MAX(sequence_no), -1) + 1
                    FROM task_events WHERE task_run_id = ?
                    """,
                    (task_run_id,),
                ).fetchone()[0]
                connection.execute(
                    """
                    UPDATE task_runs
                    SET status = 'failed', success = 0, error = ?,
                        error_code = 'RUNTIME_RESTART', retryable = 1,
                        current_step_id = NULL, finished_at = ?, updated_at = ?
                    WHERE task_run_id = ?
                    """,
                    (task_error, now, now, task_run_id),
                )
                connection.execute(
                    """
                    UPDATE task_steps
                    SET status = 'failed',
                        error = COALESCE(error, ?),
                        finished_at = COALESCE(finished_at, ?)
                    WHERE task_run_id = ? AND status = 'running'
                    """,
                    (task_error, now, task_run_id),
                )
                connection.execute(
                    """
                    INSERT INTO task_events (
                        event_id, task_run_id, sequence_no, type, timestamp,
                        status, step_id, message, metadata_json
                    ) VALUES (?, ?, ?, 'task.recovered_after_restart', ?,
                              'failed', NULL, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        task_run_id,
                        next_sequence,
                        now,
                        "Task marked failed after process restart; execution was not replayed.",
                        _json_dump({"error_code": "RUNTIME_RESTART", "retryable": True}),
                    ),
                )
            connection.execute(
                """
                UPDATE idempotency_records
                SET state = 'failed', updated_at = ?
                WHERE state = 'in_progress'
                  AND (
                    (resource_type = 'agent_run' AND resource_id IN (
                        SELECT run_id FROM agent_runs WHERE error_code = 'RUNTIME_RESTART'
                    ))
                    OR
                    (resource_type = 'task_run' AND resource_id IN (
                        SELECT task_run_id FROM task_runs WHERE error LIKE 'RUNTIME_RESTART:%'
                    ))
                  )
                """,
                (now,),
            )
            connection.execute(
                """
                UPDATE idempotency_records
                SET state = 'completed', updated_at = ?
                WHERE state = 'in_progress'
                  AND (
                    (resource_type = 'agent_run' AND resource_id IN (
                        SELECT run_id FROM agent_runs WHERE status IN ('completed', 'succeeded')
                    ))
                    OR
                    (resource_type = 'task_run' AND resource_id IN (
                        SELECT task_run_id FROM task_runs WHERE status = 'succeeded'
                    ))
                  )
                """,
                (now,),
            )
            connection.execute(
                """
                UPDATE idempotency_records
                SET state = 'failed', updated_at = ?
                WHERE state = 'in_progress'
                """,
                (now,),
            )
            connection.commit()
        return {"agent_runs": len(agent_rows), "task_runs": len(task_rows)}

    def pragma_settings(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            return {
                "journal_mode": str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
                "foreign_keys": int(connection.execute("PRAGMA foreign_keys").fetchone()[0]),
                "busy_timeout": int(connection.execute("PRAGMA busy_timeout").fetchone()[0]),
            }

    def applied_migrations(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
            ).fetchall()
            return [dict(row) for row in rows]

    def close(self) -> None:
        # Connections are scoped to individual operations, so there is no pool to close.
        return None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=self.busy_timeout_ms / 1_000,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def _migration_paths(self) -> list[Path]:
        migration_root = Path(__file__).resolve().parent / "sql"
        return sorted(migration_root.glob(_MIGRATION_GLOB))

    def _apply_migration(self, migration_path: Path) -> None:
        version_text, _, name = migration_path.stem.partition("_")
        version = int(version_text)
        sql = migration_path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        with self._write_lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT checksum FROM schema_migrations WHERE version = ?",
                (version,),
            ).fetchone()
            if row:
                if row["checksum"] != checksum:
                    raise MigrationChecksumError(
                        f"Migration {version:04d} checksum differs from the applied schema"
                    )
                return

            escaped_name = name.replace("'", "''")
            escaped_checksum = checksum.replace("'", "''")
            escaped_applied_at = utc_now_iso().replace("'", "''")
            script = (
                "BEGIN IMMEDIATE;\n"
                f"{sql}\n"
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
                f"VALUES ({version}, '{escaped_name}', '{escaped_checksum}', '{escaped_applied_at}');\n"
                f"PRAGMA user_version = {version};\n"
                "COMMIT;"
            )
            try:
                connection.executescript(script)
            except sqlite3.IntegrityError:
                connection.rollback()
                applied = connection.execute(
                    "SELECT checksum FROM schema_migrations WHERE version = ?",
                    (version,),
                ).fetchone()
                if not applied or applied["checksum"] != checksum:
                    raise

    def _validate_task_parent(self, connection: sqlite3.Connection, run: TaskRun) -> None:
        existing = connection.execute(
            """
            SELECT agent_run_id, user_id, conversation_id, idempotency_scope,
                   idempotency_key, request_hash, content
            FROM task_runs WHERE task_run_id = ?
            """,
            (run.task_run_id,),
        ).fetchone()
        if existing is not None and (
            existing["agent_run_id"] != run.agent_run_id
            or existing["user_id"] != run.user_id
            or existing["conversation_id"] != run.conversation_id
            or existing["idempotency_scope"] != run.idempotency_scope
            or existing["idempotency_key"] != _idempotency_key_digest(run.idempotency_key)
            or existing["request_hash"] != run.request_hash
            or existing["content"] != sanitize_text_for_storage(run.content)
        ):
            raise RunLinkMismatchError("TaskRun identity and parent link are immutable")
        if run.agent_run_id is None:
            return
        parent = connection.execute(
            "SELECT user_id, conversation_id FROM agent_runs WHERE run_id = ?",
            (run.agent_run_id,),
        ).fetchone()
        if parent is None:
            return  # The SQLite foreign key reports the missing parent on INSERT.
        if parent["user_id"] != run.user_id or parent["conversation_id"] != run.conversation_id:
            raise RunLinkMismatchError(
                "TaskRun owner/conversation must match its parent AgentRun"
            )

    def _insert_initial_resource(
        self,
        connection: sqlite3.Connection,
        resource: AgentRun | TaskRun,
    ) -> None:
        now = utc_now_iso()
        if isinstance(resource, AgentRun):
            self._validate_agent_identity(connection, resource)
            connection.execute(
                """
                INSERT INTO agent_runs (
                    run_id, kind, user_id, conversation_id, idempotency_key,
                    request_hash, status, response_json, error_code, error_message,
                    retryable, started_at, finished_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, NULL, ?, ?)
                """,
                (
                    resource.run_id,
                    resource.kind,
                    resource.user_id,
                    resource.conversation_id,
                    _idempotency_key_digest(resource.idempotency_key),
                    resource.request_hash,
                    resource.status,
                    resource.started_at,
                    resource.started_at,
                    now,
                ),
            )
            return

        if isinstance(resource, TaskRun):
            self._validate_task_parent(connection, resource)
            connection.execute(
                """
                INSERT INTO task_runs (
                    task_run_id, agent_run_id, user_id, conversation_id,
                    idempotency_key, request_hash, idempotency_scope, content,
                    status, current_step_id, plan_json, result_json, error,
                    error_code, retryable,
                    latency_ms, success, created_at, started_at, finished_at,
                    cancel_requested, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL,
                          NULL, NULL, NULL, NULL, ?, NULL, NULL, 0, ?)
                """,
                (
                    resource.task_run_id,
                    resource.agent_run_id,
                    resource.user_id,
                    resource.conversation_id,
                    _idempotency_key_digest(resource.idempotency_key),
                    resource.request_hash,
                    resource.idempotency_scope,
                    sanitize_text_for_storage(resource.content),
                    resource.status,
                    resource.created_at,
                    now,
                ),
            )
            for sequence_no, event in enumerate(resource.events):
                connection.execute(
                    """
                    INSERT INTO task_events (
                        event_id, task_run_id, sequence_no, type, timestamp,
                        status, step_id, message, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        resource.task_run_id,
                        sequence_no,
                        event.type,
                        event.timestamp,
                        event.status,
                        event.step_id,
                        sanitize_text_for_storage(event.message, max_chars=2_048),
                        _json_dump(sanitize_structured_for_storage(event.metadata)),
                    ),
                )
            return
        raise TypeError("Unsupported initial idempotency resource")

    @staticmethod
    def _resource_exists(
        connection: sqlite3.Connection,
        resource_type: str | None,
        resource_id: str | None,
    ) -> bool:
        if not resource_type or not resource_id:
            return False
        if resource_type == "agent_run":
            table, key = "agent_runs", "run_id"
        elif resource_type == "task_run":
            table, key = "task_runs", "task_run_id"
        else:
            return False
        return connection.execute(
            f"SELECT 1 FROM {table} WHERE {key} = ?",
            (resource_id,),
        ).fetchone() is not None

    def _validate_agent_identity(self, connection: sqlite3.Connection, run: AgentRun) -> None:
        existing = connection.execute(
            """
            SELECT kind, user_id, conversation_id, idempotency_key, request_hash
            FROM agent_runs WHERE run_id = ?
            """,
            (run.run_id,),
        ).fetchone()
        if existing is None:
            return
        if (
            existing["kind"] != run.kind
            or existing["user_id"] != run.user_id
            or existing["conversation_id"] != run.conversation_id
            or existing["idempotency_key"] != _idempotency_key_digest(run.idempotency_key)
            or existing["request_hash"] != run.request_hash
        ):
            raise RunLinkMismatchError("AgentRun identity and conversation link are immutable")

    def _sync_terminal_idempotency(
        self,
        connection: sqlite3.Connection,
        *,
        scope: str,
        user_id: str | None,
        idempotency_key: str | None,
        request_hash: str | None,
        resource_type: str,
        resource_id: str,
        status: str,
        response: Any,
    ) -> None:
        state = _terminal_idempotency_state(status)
        if state is None or user_id is None or not idempotency_key or not request_hash:
            return
        row = connection.execute(
            """
            SELECT * FROM idempotency_records
            WHERE scope = ? AND user_id = ? AND idempotency_key = ?
            """,
            (scope, user_id, _idempotency_key_digest(idempotency_key)),
        ).fetchone()
        if row is None:
            return
        existing = _idempotency_from_row(row)
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different request"
            )
        if (
            existing.resource_type not in {None, resource_type}
            or existing.resource_id not in {None, resource_id}
        ):
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different resource"
            )
        if existing.state in {"completed", "failed"}:
            return
        response_json = (
            _json_dump(sanitize_structured_for_storage(response))
            if response is not None
            else None
        )
        connection.execute(
            """
            UPDATE idempotency_records
            SET state = ?, response_json = ?, resource_type = ?, resource_id = ?,
                updated_at = ?
            WHERE scope = ? AND user_id = ? AND idempotency_key = ?
            """,
            (
                state,
                response_json,
                resource_type,
                resource_id,
                utc_now_iso(),
                scope,
                user_id,
                _idempotency_key_digest(idempotency_key),
            ),
        )

    def _load_agent_run(self, connection: sqlite3.Connection, row: sqlite3.Row) -> AgentRun:
        step_rows = connection.execute(
            "SELECT * FROM agent_steps WHERE agent_run_id = ? ORDER BY ordinal",
            (row["run_id"],),
        ).fetchall()
        return AgentRun(
            user_id=row["user_id"],
            conversation_id=row["conversation_id"],
            kind=row["kind"],
            idempotency_key=_stored_idempotency_digest(row["idempotency_key"]),
            request_hash=row["request_hash"],
            response=_json_load(row["response_json"], None),
            error_code=row["error_code"],
            error_message=row["error_message"],
            retryable=_db_to_bool(row["retryable"]),
            run_id=row["run_id"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            steps=[
                AgentStep(
                    name=step["name"],
                    status=step["status"],
                    started_at=step["started_at"],
                    finished_at=step["finished_at"],
                    latency_ms=float(step["latency_ms"]),
                    input_summary=step["input_summary"],
                    output_summary=step["output_summary"],
                    metadata=_json_load(step["metadata_json"], {}),
                )
                for step in step_rows
            ],
        )

    def _load_task_run(self, connection: sqlite3.Connection, row: sqlite3.Row) -> TaskRun:
        step_rows = connection.execute(
            "SELECT * FROM task_steps WHERE task_run_id = ? ORDER BY ordinal",
            (row["task_run_id"],),
        ).fetchall()
        event_rows = connection.execute(
            "SELECT * FROM task_events WHERE task_run_id = ? ORDER BY sequence_no",
            (row["task_run_id"],),
        ).fetchall()
        events = [
            TaskEvent(
                event_id=event["event_id"],
                type=event["type"],
                timestamp=event["timestamp"],
                status=event["status"],
                step_id=event["step_id"],
                message=event["message"],
                metadata=_json_load(event["metadata_json"], {}),
            )
            for event in event_rows
        ]
        steps = []
        for step in step_rows:
            step_events = [event for event in events if event.step_id == step["step_id"]]
            steps.append(
                TaskStepRun(
                    step_id=step["step_id"],
                    description=step["description"],
                    tool_name=step["tool_name"],
                    status=step["status"],
                    tool_args=_json_load(step["tool_args_json"], {}),
                    result=_json_load(step["result_json"], None),
                    error=step["error"],
                    latency_ms=step["latency_ms"],
                    started_at=step["started_at"],
                    finished_at=step["finished_at"],
                    events=step_events,
                )
            )
        return TaskRun(
            task_run_id=row["task_run_id"],
            user_id=row["user_id"],
            content=row["content"],
            agent_run_id=row["agent_run_id"],
            conversation_id=row["conversation_id"],
            idempotency_key=_stored_idempotency_digest(row["idempotency_key"]),
            request_hash=row["request_hash"],
            idempotency_scope=row["idempotency_scope"],
            status=row["status"],
            current_step_id=row["current_step_id"],
            plan=_json_load(row["plan_json"], None),
            result=_json_load(row["result_json"], None),
            error=row["error"],
            error_code=row["error_code"],
            retryable=_db_to_bool(row["retryable"]),
            latency_ms=row["latency_ms"],
            success=_db_to_bool(row["success"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            cancel_requested=bool(row["cancel_requested"]),
            steps=steps,
            events=events,
        )


def _json_dump(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_load(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Corrupt JSON payload in runtime database") from exc


def _bool_to_db(value: bool | None) -> int | None:
    return None if value is None else int(bool(value))


def _db_to_bool(value: int | None) -> bool | None:
    return None if value is None else bool(value)


def _terminal_idempotency_state(status: str) -> str | None:
    if status in {"completed", "succeeded"}:
        return "completed"
    if status in {"failed", "cancelled"}:
        return "failed"
    return None


def hash_request_payload(value: Any) -> str:
    """Return a deterministic digest without persisting the raw request payload."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: f"[unsupported:{type(item).__name__}]",
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_idempotency_identity(
    scope: str,
    user_id: str,
    idempotency_key: str,
    request_hash: str,
) -> None:
    if not scope.strip() or not user_id.strip() or not idempotency_key.strip() or not request_hash.strip():
        raise ValueError("scope, user_id, idempotency_key, and request_hash are required")
    if len(idempotency_key) > 256:
        raise ValueError("idempotency_key must not exceed 256 characters")


def _idempotency_key_digest(idempotency_key: str | None) -> str | None:
    if idempotency_key is None:
        return None
    if isinstance(idempotency_key, _StoredIdempotencyDigest):
        return str(idempotency_key)
    value = str(idempotency_key)
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stored_idempotency_digest(value: str | None) -> _StoredIdempotencyDigest | None:
    return None if value is None else _StoredIdempotencyDigest(value)


def _resource_identity(resource: AgentRun | TaskRun) -> tuple[str, str]:
    if isinstance(resource, AgentRun):
        return "agent_run", resource.run_id
    if isinstance(resource, TaskRun):
        return "task_run", resource.task_run_id
    raise TypeError("Unsupported idempotency resource")


def _idempotency_from_row(row: sqlite3.Row) -> IdempotencyRecord:
    return IdempotencyRecord(
        scope=row["scope"],
        user_id=row["user_id"],
        idempotency_key=row["idempotency_key"],
        request_hash=row["request_hash"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        state=row["state"],
        response=_json_load(row["response_json"], None),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        expires_at=row["expires_at"],
    )
