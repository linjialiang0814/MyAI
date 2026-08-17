from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from app.runtime.error_model import ErrorCode, error_info_from_message

if TYPE_CHECKING:
    from app.runtime.sqlite_repository import SQLiteRuntimeRepository


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _synchronized(method):
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return locked


@dataclass
class TaskEvent:
    event_id: str
    type: str
    timestamp: str
    status: str
    step_id: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskStepRun:
    step_id: str
    description: str | None
    tool_name: str
    status: str = "queued"
    tool_args: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float | None = None
    started_at: str | None = None
    finished_at: str | None = None
    events: list[TaskEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["events"] = [event.to_dict() for event in self.events]
        return data


@dataclass
class TaskRun:
    task_run_id: str
    user_id: str | None
    content: str
    agent_run_id: str | None = None
    conversation_id: int | None = None
    idempotency_key: str | None = None
    request_hash: str | None = None
    idempotency_scope: str = "standalone"
    status: str = "queued"
    current_step_id: str | None = None
    plan: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
    retryable: bool | None = None
    latency_ms: float | None = None
    success: bool | None = None
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    cancel_requested: bool = False
    steps: list[TaskStepRun] = field(default_factory=list)
    events: list[TaskEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("idempotency_key", None)
        data["idempotency_key_present"] = self.idempotency_key is not None
        data["steps"] = [step.to_dict() for step in self.steps]
        data["events"] = [event.to_dict() for event in self.events]
        return data


class TaskRunStore:
    def __init__(self, repository: SQLiteRuntimeRepository | None = None) -> None:
        self._repository = repository
        self._runs: dict[str, TaskRun] = {}
        self._idempotency: dict[tuple[str, str | None, str], tuple[str, str]] = {}
        self._lock = threading.RLock()

    @_synchronized
    def create(
        self,
        user_id: str | None,
        content: str,
        *,
        agent_run_id: str | None = None,
        conversation_id: int | None = None,
        idempotency_key: str | None = None,
        request_hash: str | None = None,
        idempotency_scope: str = "standalone",
    ) -> TaskRun:
        if idempotency_key is not None:
            run, _ = self.create_or_get(
                user_id,
                content,
                agent_run_id=agent_run_id,
                conversation_id=conversation_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                idempotency_scope=idempotency_scope,
            )
            return run
        run = TaskRun(
            task_run_id=str(uuid4()),
            user_id=user_id,
            content=content,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            idempotency_scope=idempotency_scope,
        )
        self._runs[run.task_run_id] = run
        self._append_event(run, "task.created", "Task run created.")
        self._persist(run)
        return run

    @_synchronized
    def create_or_get(
        self,
        user_id: str | None,
        content: str,
        *,
        agent_run_id: str | None = None,
        conversation_id: int | None = None,
        idempotency_key: str,
        request_hash: str | None = None,
        idempotency_scope: str = "standalone",
    ) -> tuple[TaskRun, bool]:
        from app.runtime.sqlite_repository import (
            IdempotencyConflictError,
            IdempotencyInProgressError,
        )

        effective_hash = request_hash or _hash_task_request(
            user_id=user_id,
            content=content,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
        )
        candidate = TaskRun(
            task_run_id=str(uuid4()),
            user_id=user_id,
            content=content,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
            request_hash=effective_hash,
            idempotency_scope=idempotency_scope,
        )
        self._append_event(candidate, "task.created", "Task run created.")
        if self._repository is None:
            cache_key = (idempotency_scope, user_id, idempotency_key)
            existing = self._idempotency.get(cache_key)
            if existing is not None:
                existing_hash, existing_run_id = existing
                if existing_hash != effective_hash:
                    raise IdempotencyConflictError(
                        "The idempotency key is already bound to a different request"
                    )
                return self._runs[existing_run_id], False
            self._idempotency[cache_key] = (effective_hash, candidate.task_run_id)
            self._runs[candidate.task_run_id] = candidate
            return candidate, True

        if user_id is None:
            raise ValueError("user_id is required for durable idempotency")
        claim = self._repository.claim_idempotency(
            scope=f"task_run:{idempotency_scope}",
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_hash=effective_hash,
            resource_type="task_run",
            resource_id=candidate.task_run_id,
            initial_resource=candidate,
        )
        if claim.claimed:
            self._runs[candidate.task_run_id] = candidate
            return candidate, True
        resource_id = claim.record.resource_id
        existing = self.get(resource_id) if resource_id else None
        if existing is None:
            raise IdempotencyInProgressError(
                "An equivalent TaskRun request is claimed but not yet materialized"
            )
        if existing.request_hash != effective_hash:
            raise IdempotencyConflictError(
                "The persisted TaskRun request hash differs from its idempotency claim"
            )
        return existing, False

    @_synchronized
    def replay_if_exists(
        self,
        user_id: str | None,
        content: str,
        *,
        agent_run_id: str | None = None,
        conversation_id: int | None = None,
        idempotency_key: str,
        idempotency_scope: str = "standalone",
    ) -> TaskRun | None:
        """Return an existing idempotent run without claiming queue capacity."""

        from app.runtime.sqlite_repository import (
            IdempotencyConflictError,
            IdempotencyInProgressError,
        )

        if self._repository is None:
            cached = self._idempotency.get((idempotency_scope, user_id, idempotency_key))
            if cached is None:
                return None
            stored_hash, run_id = cached
            existing = self._runs.get(run_id)
        else:
            if user_id is None:
                raise ValueError("user_id is required for durable idempotency")
            record = self._repository.get_idempotency(
                scope=f"task_run:{idempotency_scope}",
                user_id=user_id,
                idempotency_key=idempotency_key,
            )
            if record is None:
                return None
            stored_hash = record.request_hash
            existing = self.get(record.resource_id) if record.resource_id else None

        if existing is None:
            raise IdempotencyInProgressError(
                "An equivalent TaskRun request is claimed but not yet materialized"
            )
        expected_hash = _hash_task_request(
            user_id=user_id,
            content=content,
            agent_run_id=agent_run_id or existing.agent_run_id,
            conversation_id=conversation_id,
        )
        if stored_hash != expected_hash:
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different request"
            )
        return existing

    @_synchronized
    def get(self, task_run_id: str) -> TaskRun | None:
        cached = self._runs.get(task_run_id)
        if cached is not None:
            return cached
        if self._repository is None:
            return None
        run = self._repository.get_task_run(task_run_id)
        if run is not None:
            self._runs[run.task_run_id] = run
        return run

    @_synchronized
    def list_runs(
        self,
        user_id: str | None = None,
        limit: int = 20,
        *,
        agent_run_id: str | None = None,
    ) -> list[TaskRun]:
        if self._repository is not None:
            persisted_runs = self._repository.list_task_runs(
                user_id=user_id,
                agent_run_id=agent_run_id,
                limit=limit,
            )
            runs: list[TaskRun] = []
            for persisted in persisted_runs:
                # Keep one canonical in-process object. Replacing an active object
                # with a database snapshot can lose a concurrent cancellation and
                # leave get() reporting a stale state after the worker finishes.
                cached = self._runs.get(persisted.task_run_id)
                if cached is None:
                    self._runs[persisted.task_run_id] = persisted
                    cached = persisted
                runs.append(cached)
            return runs
        runs = list(self._runs.values())
        if user_id is not None:
            runs = [run for run in runs if run.user_id == user_id]
        if agent_run_id is not None:
            runs = [run for run in runs if run.agent_run_id == agent_run_id]
        runs.sort(key=lambda run: run.created_at, reverse=True)
        return runs[: max(1, limit)]

    @_synchronized
    def save(self, run: TaskRun) -> TaskRun:
        self._runs[run.task_run_id] = run
        self._persist(run)
        return run

    @_synchronized
    def mark_queued(self, run: TaskRun, *, background: bool = False) -> None:
        run.status = "queued"
        self._append_event(
            run,
            "task.queued",
            "Task queued.",
            metadata={"background": background},
        )
        self._persist(run)

    @_synchronized
    def request_cancel(self, run: TaskRun) -> bool:
        if run.status in {"succeeded", "failed", "cancelled"}:
            return False
        run.cancel_requested = True
        self._append_event(run, "task.cancel_requested", "Task cancellation requested.")
        self._persist(run)
        return True

    @_synchronized
    def mark_planning(self, run: TaskRun) -> None:
        run.status = "planning"
        run.started_at = run.started_at or utc_now()
        self._append_event(run, "task.planning.started", "Planning started.")
        self._persist(run)

    @_synchronized
    def record_memory_retrieval_started(self, run: TaskRun) -> None:
        self._append_event(run, "task.memory_retrieval.started", "Memory context retrieval started.")
        self._persist(run)

    @_synchronized
    def record_memory_retrieval_completed(self, run: TaskRun, memory_context: dict[str, Any]) -> None:
        selected = memory_context.get("selected", []) if isinstance(memory_context, dict) else []
        self._append_event(
            run,
            "task.memory_retrieval.completed",
            "Memory context retrieval completed.",
            metadata={
                "selected_count": len(selected),
                "selected": selected,
                "explanations": memory_context.get("explanations", []) if isinstance(memory_context, dict) else [],
            },
        )
        self._persist(run)

    @_synchronized
    def set_plan(self, run: TaskRun, plan: dict[str, Any], steps: list[Any]) -> None:
        run.plan = plan
        run.steps = [
            TaskStepRun(
                step_id=step.step_id,
                description=step.description,
                tool_name=step.tool_name,
                tool_args=dict(step.tool_args or {}),
            )
            for step in steps
        ]
        self._append_event(
            run,
            "task.planning.completed",
            "Planning completed.",
            metadata={
                "source": plan.get("source"),
                "need_tool": plan.get("need_tool"),
                "step_count": len(steps),
            },
        )
        self._persist(run)

    @_synchronized
    def mark_running(self, run: TaskRun) -> None:
        run.status = "running"
        run.started_at = run.started_at or utc_now()
        self._append_event(run, "task.running", "Task execution started.")
        self._persist(run)

    @_synchronized
    def start_step(self, run: TaskRun, step_id: str, tool_args: dict[str, Any]) -> None:
        run.current_step_id = step_id
        step = self._find_step(run, step_id)
        if step is None:
            return
        step.status = "running"
        step.tool_args = dict(tool_args or {})
        step.started_at = step.started_at or utc_now()
        event = self._append_event(
            run,
            "task.step.started",
            f"Step {step_id} started.",
            step_id=step_id,
            metadata={"tool_name": step.tool_name, "tool_args": step.tool_args},
        )
        step.events.append(event)
        self._persist(run)

    @_synchronized
    def complete_step(self, run: TaskRun, step_id: str, result: dict[str, Any], latency_ms: float) -> None:
        step = self._find_step(run, step_id)
        if step is None:
            return
        step.status = "succeeded"
        step.result = result
        step.latency_ms = round(latency_ms, 3)
        step.finished_at = utc_now()
        event = self._append_event(
            run,
            "task.step.completed",
            f"Step {step_id} completed.",
            step_id=step_id,
            metadata={"tool_name": step.tool_name, "latency_ms": step.latency_ms},
        )
        step.events.append(event)
        self._persist(run)

    @_synchronized
    def fail_step(self, run: TaskRun, step_id: str, result: dict[str, Any], latency_ms: float, error: str | None) -> None:
        step = self._find_step(run, step_id)
        if step is None:
            return
        step.status = "failed"
        step.result = result
        step.error = error
        step.latency_ms = round(latency_ms, 3)
        step.finished_at = utc_now()
        event = self._append_event(
            run,
            "task.step.failed",
            f"Step {step_id} failed.",
            step_id=step_id,
            metadata={"tool_name": step.tool_name, "latency_ms": step.latency_ms, "error": error},
        )
        step.events.append(event)
        self._persist(run)

    @_synchronized
    def record_tool_policy(self, run: TaskRun, step_id: str, policy_metadata: dict[str, Any] | None) -> None:
        if not policy_metadata:
            return
        decision = str(policy_metadata.get("policy_decision") or "unknown")
        event_type = f"task.tool_policy.{decision}"
        event = self._append_event(
            run,
            event_type,
            f"Tool policy decision: {decision}.",
            step_id=step_id,
            metadata=policy_metadata,
        )
        step = self._find_step(run, step_id)
        if step is not None:
            step.events.append(event)
        self._persist(run)

    @_synchronized
    def record_recovery(self, run: TaskRun, step_id: str, result_metadata: dict[str, Any] | None) -> None:
        if not result_metadata:
            return
        recovery_status = result_metadata.get("recovery_status")
        if not recovery_status or recovery_status == "not_needed":
            return
        event = self._append_event(
            run,
            "task.step.recovery",
            f"Recovery status: {recovery_status}.",
            step_id=step_id,
            metadata={
                "attempt": result_metadata.get("attempt"),
                "max_attempts": result_metadata.get("max_attempts"),
                "retryable": result_metadata.get("retryable"),
                "recovery_status": recovery_status,
                "recovery_recommendation": result_metadata.get("recovery_recommendation"),
                "errors": result_metadata.get("errors", []),
            },
        )
        step = self._find_step(run, step_id)
        if step is not None:
            step.events.append(event)
        self._persist(run)

    @_synchronized
    def record_mcp_call(self, run: TaskRun, step_id: str, result_metadata: dict[str, Any] | None, *, success: bool, error: str | None = None) -> None:
        if not result_metadata or result_metadata.get("tool_source") != "mcp":
            return
        status = "completed" if success else "failed"
        event_type = f"task.mcp_call.{status}"
        metadata = {
            "server_id": result_metadata.get("mcp_server_id"),
            "tool_name": result_metadata.get("mcp_tool_name"),
            "registry_name": result_metadata.get("mcp_registry_name"),
            "call_status": result_metadata.get("mcp_call_status") or status,
            "call_started_at": result_metadata.get("mcp_call_started_at"),
            "call_finished_at": result_metadata.get("mcp_call_finished_at"),
            "call_latency_ms": result_metadata.get("mcp_call_latency_ms"),
            "attempt": result_metadata.get("attempt"),
            "max_attempts": result_metadata.get("max_attempts"),
            "retryable": result_metadata.get("retryable"),
            "error": error,
        }
        event = self._append_event(
            run,
            event_type,
            f"MCP tool call {status}.",
            step_id=step_id,
            metadata={key: value for key, value in metadata.items() if value is not None},
        )
        step = self._find_step(run, step_id)
        if step is not None:
            step.events.append(event)
        self._persist(run)

    @_synchronized
    def record_outcome_memory_started(self, run: TaskRun) -> None:
        self._append_event(run, "task.outcome_memory.started", "Task outcome memory evaluation started.")
        self._persist(run)

    @_synchronized
    def record_outcome_memory_completed(self, run: TaskRun, outcome_result: dict[str, Any]) -> None:
        self._append_event(
            run,
            "task.outcome_memory.completed",
            "Task outcome memory evaluation completed.",
            metadata=outcome_result,
        )
        self._persist(run)

    @_synchronized
    def succeed(self, run: TaskRun, result: dict[str, Any] | None, latency_ms: float | None = None) -> None:
        run.status = "succeeded"
        run.result = result
        run.success = True
        run.error = None
        run.error_code = None
        run.retryable = None
        run.latency_ms = latency_ms
        run.current_step_id = None
        run.finished_at = utc_now()
        self._append_event(run, "task.completed", "Task completed.", metadata={"latency_ms": latency_ms})
        self._persist(run)
        self._complete_idempotency(run, state="completed")

    @_synchronized
    def cancel(self, run: TaskRun, result: dict[str, Any] | None = None, latency_ms: float | None = None) -> None:
        run.status = "cancelled"
        run.result = result or {"success": False, "cancelled": True}
        run.success = False
        run.error = "Task cancelled"
        run.error_code = ErrorCode.CANCELLED.value
        run.retryable = False
        run.latency_ms = latency_ms
        run.current_step_id = None
        run.finished_at = utc_now()
        self._append_event(run, "task.cancelled", "Task cancelled.", metadata={"latency_ms": latency_ms})
        self._persist(run)
        self._complete_idempotency(run, state="failed")

    @_synchronized
    def fail(
        self,
        run: TaskRun,
        error: str,
        result: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        error_info: dict[str, Any] | None = None,
    ) -> None:
        run.status = "failed"
        run.result = result
        run.success = False
        run.error = error
        if isinstance(error_info, dict) and error_info.get("code"):
            run.error_code = str(error_info["code"])
            run.retryable = bool(error_info.get("retryable"))
        else:
            classified = error_info_from_message(error)
            run.error_code = classified.code.value
            run.retryable = classified.retryable
        run.latency_ms = latency_ms
        run.current_step_id = None
        run.finished_at = utc_now()
        self._append_event(
            run,
            "task.failed",
            "Task failed.",
            metadata={"latency_ms": latency_ms, "error": error},
        )
        self._persist(run)
        self._complete_idempotency(run, state="failed")

    def _find_step(self, run: TaskRun, step_id: str) -> TaskStepRun | None:
        return next((step for step in run.steps if step.step_id == step_id), None)

    def _append_event(
        self,
        run: TaskRun,
        event_type: str,
        message: str | None = None,
        step_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskEvent:
        event = TaskEvent(
            event_id=str(uuid4()),
            type=event_type,
            timestamp=utc_now(),
            status=run.status,
            step_id=step_id,
            message=message,
            metadata=dict(metadata or {}),
        )
        run.events.append(event)
        return event

    def _persist(self, run: TaskRun) -> None:
        self._runs[run.task_run_id] = run
        if self._repository is not None:
            self._repository.save_task_run(run)

    def _complete_idempotency(self, run: TaskRun, *, state: str) -> None:
        if (
            self._repository is None
            or run.user_id is None
            or not run.idempotency_key
            or not run.request_hash
        ):
            return
        self._repository.complete_idempotency(
            scope=f"task_run:{run.idempotency_scope}",
            user_id=run.user_id,
            idempotency_key=run.idempotency_key,
            request_hash=run.request_hash,
            state=state,
            response=run.to_dict(),
            resource_type="task_run",
            resource_id=run.task_run_id,
        )


def _hash_task_request(
    *,
    user_id: str | None,
    content: str,
    agent_run_id: str | None,
    conversation_id: int | None,
) -> str:
    payload = json.dumps(
        {
            "agent_run_id": agent_run_id,
            "content": content,
            "conversation_id": conversation_id,
            "user_id": user_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
