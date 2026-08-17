from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from app.runtime.agent_trace import AgentRun
from app.runtime.sqlite_repository import IdempotencyInProgressError

if TYPE_CHECKING:
    from app.runtime.sqlite_repository import SQLiteRuntimeRepository


class AgentRunStore:
    """Agent-run store with an in-memory default and an optional durable backend."""

    def __init__(self, repository: SQLiteRuntimeRepository | None = None) -> None:
        self._repository = repository
        self._runs: dict[str, AgentRun] = {}
        self._lock = threading.RLock()

    def create(
        self,
        user_id: str,
        conversation_id: int | None = None,
        *,
        kind: str = "chat",
        idempotency_key: str | None = None,
        request_hash: str | None = None,
    ) -> AgentRun:
        with self._lock:
            if idempotency_key is not None:
                run, _ = self.create_or_get(
                    user_id,
                    conversation_id,
                    kind=kind,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                return run
            run = AgentRun(user_id=user_id, conversation_id=conversation_id, kind=kind)
            return self.save(run)

    def create_or_get(
        self,
        user_id: str,
        conversation_id: int | None = None,
        *,
        kind: str = "chat",
        idempotency_key: str,
        request_hash: str | None,
    ) -> tuple[AgentRun, bool]:
        if self._repository is None:
            raise RuntimeError("create_or_get requires a durable runtime repository")
        if not request_hash:
            raise ValueError("request_hash is required when idempotency_key is set")
        candidate = AgentRun(
            user_id=user_id,
            conversation_id=conversation_id,
            kind=kind,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        scope = f"agent_run:{kind}"
        with self._lock:
            claim = self._repository.claim_idempotency(
                scope=scope,
                user_id=user_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_type="agent_run",
                resource_id=candidate.run_id,
                initial_resource=candidate,
            )
            if claim.claimed:
                self._runs[candidate.run_id] = candidate
                return candidate, True
            resource_id = claim.record.resource_id
            existing = self.get(resource_id) if resource_id else None
            if existing is None:
                raise IdempotencyInProgressError(
                    "An equivalent AgentRun request is claimed but not yet materialized"
                )
            return existing, False

    def save(self, run: AgentRun) -> AgentRun:
        with self._lock:
            self._runs[run.run_id] = run
            if self._repository is not None:
                self._repository.save_agent_run(run)
            return run

    def save_response(
        self,
        run: AgentRun,
        response: dict,
        *,
        status: str = "completed",
        error_code: str | None = None,
        error_message: str | None = None,
        retryable: bool | None = None,
    ) -> AgentRun:
        with self._lock:
            run.response = response
            run.error_code = error_code
            run.error_message = error_message
            run.retryable = retryable
            run.finish(status)
            self.save(run)
            if self._repository is not None and run.idempotency_key and run.request_hash:
                self._repository.complete_idempotency(
                    scope=f"agent_run:{run.kind}",
                    user_id=run.user_id,
                    idempotency_key=run.idempotency_key,
                    request_hash=run.request_hash,
                    state="completed" if status == "completed" else "failed",
                    response=response,
                    resource_type="agent_run",
                    resource_id=run.run_id,
                )
            return run

    def get(self, run_id: str) -> AgentRun | None:
        with self._lock:
            cached = self._runs.get(run_id)
            if cached is not None:
                return cached
            if self._repository is None:
                return None
            run = self._repository.get_agent_run(run_id)
            if run is not None:
                self._runs[run.run_id] = run
            return run

    def list_runs(
        self,
        *,
        user_id: str | None = None,
        conversation_id: int | None = None,
        limit: int = 20,
    ) -> list[AgentRun]:
        with self._lock:
            if self._repository is not None:
                persisted_runs = self._repository.list_agent_runs(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    limit=limit,
                )
                runs: list[AgentRun] = []
                for persisted in persisted_runs:
                    cached = self._runs.get(persisted.run_id)
                    if cached is None:
                        self._runs[persisted.run_id] = persisted
                        cached = persisted
                    runs.append(cached)
                return runs

            runs = list(self._runs.values())
            if user_id is not None:
                runs = [run for run in runs if run.user_id == user_id]
            if conversation_id is not None:
                runs = [run for run in runs if run.conversation_id == conversation_id]
            runs.sort(key=lambda run: (run.started_at, run.run_id), reverse=True)
            return runs[: max(1, int(limit))]
