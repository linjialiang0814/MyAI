from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from app.context.context import ConversationContext
from app.core.service import AgentService
from app.knowledge.service import KnowledgeService
from app.memory.embedding.factory import create_embedding_client
from app.memory.maintenance.scheduler import MemoryMaintenanceScheduler
from app.memory.mem_service import MemoryService
from app.memory.settings import MemorySettingsStore
from app.memory.store.chroma_store import ChromaMemoryStore
from app.memory.writer.smart_writer import build_memory_writer
from app.model.config import LLMSettings, load_llm_settings
from app.model.factory import create_llm
from app.prompt.prompt_builder import PromptBuilder
from app.runtime.agent_store import AgentRunStore
from app.runtime.chroma_client import create_chroma_client
from app.runtime.config import RuntimeSettings, load_runtime_settings
from app.runtime.resilience import (
    BackoffPolicy,
    CircuitBreakerRegistry,
    CircuitProtectedEmbeddingClient,
)
from app.runtime.sqlite_repository import SQLiteRuntimeRepository
from app.task.runtime import TaskRunStore
from app.task.service.prepare import build_task_service
from app.task.service.task_service import TaskService


@dataclass(slots=True)
class AppRuntime:
    """Process-local application services owned by one FastAPI lifespan."""

    settings: LLMSettings
    runtime_settings: RuntimeSettings
    embedding_client: Any
    chroma_client: Any
    runtime_repository: SQLiteRuntimeRepository
    agent_run_store: AgentRunStore
    task_run_store: TaskRunStore
    memory_service: MemoryService
    knowledge_service: KnowledgeService
    task_service: TaskService
    agent_service: AgentService
    chat_llm: Any
    task_llm: Any
    memory_llm: Any | None = None
    maintenance_scheduler: MemoryMaintenanceScheduler | None = None
    circuit_registry: CircuitBreakerRegistry | None = None
    recovery_report: dict[str, int] = field(default_factory=dict)
    _resources: ExitStack = field(default_factory=ExitStack, repr=False)
    _close_lock: Lock = field(default_factory=Lock, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        """Quiesce workers before releasing shared providers and stores."""

        with self._close_lock:
            if self._closed:
                return
            close_task_service = getattr(self.task_service, "close", None)
            if callable(close_task_service) and close_task_service(
                timeout_seconds=self.runtime_settings.task_shutdown_timeout_seconds
            ) is False:
                raise RuntimeError(
                    "task workers did not stop before shutdown timeout; dependencies remain open"
                )
            if self.maintenance_scheduler is not None and not self.maintenance_scheduler.stop(
                timeout_seconds=self.runtime_settings.memory_maintenance_shutdown_timeout_seconds
            ):
                raise RuntimeError(
                    "memory maintenance worker did not stop before shutdown timeout; dependencies remain open"
                )
            self._closed = True
            resources = self._resources
            self._resources = ExitStack()
        resources.close()


def build_runtime(
    settings: LLMSettings | None = None,
    *,
    runtime_settings: RuntimeSettings | None = None,
    runtime_repository: SQLiteRuntimeRepository | None = None,
    agent_run_store: AgentRunStore | None = None,
    run_store: TaskRunStore | None = None,
) -> AppRuntime:
    """Build the production composition root without hiding resource ownership."""

    resolved_settings = settings or load_llm_settings()
    resolved_runtime_settings = runtime_settings or load_runtime_settings()
    owned_ids: set[int] = set()

    with ExitStack() as resources:
        repository = runtime_repository or SQLiteRuntimeRepository(
            resolved_runtime_settings.database_path,
            busy_timeout_ms=resolved_runtime_settings.database_busy_timeout_ms,
        )
        _register_close(resources, repository, owned_ids)
        recovery_report = repository.recover_incomplete_runs()
        resolved_agent_store = agent_run_store or AgentRunStore(repository)
        resolved_task_store = run_store or TaskRunStore(repository=repository)

        circuit_registry = CircuitBreakerRegistry(
            failure_threshold=resolved_runtime_settings.circuit_failure_threshold,
            recovery_timeout_seconds=resolved_runtime_settings.circuit_recovery_seconds,
        )
        retry_backoff = BackoffPolicy(
            max_attempts=2,
            base_delay_seconds=resolved_runtime_settings.retry_base_delay_seconds,
            max_delay_seconds=resolved_runtime_settings.retry_max_delay_seconds,
            jitter_ratio=resolved_runtime_settings.retry_jitter_ratio,
        )

        chroma_client = create_chroma_client()
        _register_close(resources, chroma_client, owned_ids)

        embedding_client = create_embedding_client(resolved_settings)
        if resolved_settings.embedding_provider != "stub":
            embedding_client = CircuitProtectedEmbeddingClient(
                embedding_client,
                circuit_registry.get(
                    f"embedding:{resolved_settings.embedding_provider}:{resolved_settings.embedding_model_id}"
                ),
                dependency=resolved_settings.embedding_provider,
            )
        _register_close(resources, embedding_client, owned_ids)

        memory_llm = None
        if resolved_settings.memory_llm_extractor_enabled:
            memory_llm = create_llm(
                role="memory",
                settings=resolved_settings,
                circuit_registry=circuit_registry,
            )
            _register_close(resources, memory_llm, owned_ids)

        memory_store = ChromaMemoryStore(
            collection_name=resolved_settings.memory_collection_name,
            chroma_client=chroma_client,
        )
        memory_service = MemoryService(
            embedding_client=embedding_client,
            memory_store=memory_store,
            writer=build_memory_writer(settings=resolved_settings, llm_client=memory_llm),
            settings_store=MemorySettingsStore(),
        )
        knowledge_service = KnowledgeService(
            embedding_client=embedding_client,
            collection_name=resolved_settings.knowledge_collection_name,
            chroma_client=chroma_client,
            embedding_provider=resolved_settings.embedding_provider,
            embedding_model_id=resolved_settings.embedding_model_id,
        )

        maintenance_scheduler = None
        if resolved_runtime_settings.memory_maintenance_enabled:
            maintenance_scheduler = MemoryMaintenanceScheduler(
                memory_service,
                debounce_seconds=resolved_runtime_settings.memory_maintenance_debounce_seconds,
                idle_poll_seconds=resolved_runtime_settings.memory_maintenance_idle_poll_seconds,
                max_tracked_users=resolved_runtime_settings.memory_maintenance_max_users,
                worker_count=resolved_runtime_settings.memory_maintenance_worker_count,
                maintenance_timeout_seconds=resolved_runtime_settings.memory_maintenance_deadline_seconds,
                backoff_policy=BackoffPolicy(
                    max_attempts=3,
                    base_delay_seconds=max(1.0, resolved_runtime_settings.retry_base_delay_seconds),
                    max_delay_seconds=max(30.0, resolved_runtime_settings.retry_max_delay_seconds),
                    jitter_ratio=resolved_runtime_settings.retry_jitter_ratio,
                ),
            )

        chat_llm = create_llm(
            role="chat",
            settings=resolved_settings,
            circuit_registry=circuit_registry,
        )
        _register_close(resources, chat_llm, owned_ids)
        task_llm = create_llm(
            role="task",
            settings=resolved_settings,
            circuit_registry=circuit_registry,
        )
        _register_close(resources, task_llm, owned_ids)

        if maintenance_scheduler is not None:
            maintenance_scheduler.start()
            resources.callback(
                maintenance_scheduler.stop,
                timeout_seconds=resolved_runtime_settings.memory_maintenance_shutdown_timeout_seconds,
            )

        task_service = build_task_service(
            llm_client=task_llm,
            memory_service=memory_service,
            knowledge_service=knowledge_service,
            run_store=resolved_task_store,
            agent_run_store=resolved_agent_store,
            circuit_registry=circuit_registry,
            retry_backoff=retry_backoff,
            maintenance_scheduler=maintenance_scheduler,
            max_pending_tasks=resolved_runtime_settings.task_max_pending_runs,
            task_deadline_seconds=resolved_runtime_settings.task_deadline_seconds,
        )
        _register_close(resources, task_service, owned_ids)

        agent_service = AgentService(
            memory_service=memory_service,
            knowledge_service=knowledge_service,
            task_service=task_service,
            chat_llm=chat_llm,
            context_manager=ConversationContext(max_turns=6),
            prompt_builder=PromptBuilder(),
            run_store=resolved_agent_store,
            maintenance_scheduler=maintenance_scheduler,
            chat_deadline_seconds=resolved_runtime_settings.chat_deadline_seconds,
        )
        runtime = AppRuntime(
            settings=resolved_settings,
            runtime_settings=resolved_runtime_settings,
            embedding_client=embedding_client,
            chroma_client=chroma_client,
            runtime_repository=repository,
            agent_run_store=resolved_agent_store,
            task_run_store=resolved_task_store,
            memory_service=memory_service,
            knowledge_service=knowledge_service,
            task_service=task_service,
            agent_service=agent_service,
            chat_llm=chat_llm,
            task_llm=task_llm,
            memory_llm=memory_llm,
            maintenance_scheduler=maintenance_scheduler,
            circuit_registry=circuit_registry,
            recovery_report=recovery_report,
        )
        runtime._resources = resources.pop_all()
        return runtime


def _register_close(resources: ExitStack, resource: Any, owned_ids: set[int]) -> None:
    if resource is None or id(resource) in owned_ids:
        return
    close = getattr(resource, "close", None)
    if callable(close):
        resources.callback(close)
        owned_ids.add(id(resource))
