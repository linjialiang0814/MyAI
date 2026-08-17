import os

from app.model.base import BaseLLM
from app.memory.embedding.factory import create_embedding_client
from app.memory.mem_service import MemoryService
from app.task.mcp import GitReadOnlyMCPClient, MCPServerConfig, MCPToolRegistryLoader, ReadOnlyFilesystemMCPClient
from app.task.config.task_config import TaskConfig
from app.task.plan.executor import ToolExecutor
from app.task.plan.planner import ToolPlanner
from app.task.plan.recovery import RecoveryPlanner
from app.task.plan.validation import ToolValidation
from app.task.service.task_service import TaskService
from app.task.stats.statistics import StatsManager
from app.task.tool.tool_registry import ToolRegistry
from app.task.tools.calculator import CalculatorTool
from app.task.tools.datetime_tool import DateTimeTool
from app.task.tools.file_summary import FileSummaryTool
from app.task.tools.knowledge_admin import KnowledgeAdminTool
from app.task.tools.memory_admin import MemoryAdminTool
from app.task.tools.system_info import SystemInfoTool
from app.task.tools.text_stats import TextStatsTool
from app.task.tools.weather_tool import WeatherTool
from app.task.tools.web_search import WebSearchTool
from app.task.workflow.registry import build_default_workflow_registry
from app.runtime.resilience import BackoffPolicy, CircuitBreakerRegistry


def build_task_service(
    llm_client: BaseLLM | None = None,
    config: TaskConfig | None = None,
    *,
    memory_service: MemoryService | None = None,
    knowledge_service=None,
    run_store=None,
    agent_run_store=None,
    circuit_registry: CircuitBreakerRegistry | None = None,
    retry_backoff: BackoffPolicy | None = None,
    maintenance_scheduler=None,
    max_pending_tasks: int = 100,
    task_deadline_seconds: float = 120.0,
) -> TaskService:
    cfg = config or TaskConfig()
    if memory_service is None:
        memory_service = MemoryService(embedding_client=create_embedding_client())
    if knowledge_service is None:
        from app.knowledge.service import KnowledgeService

        knowledge_service = KnowledgeService()
    registry = ToolRegistry()
    registry.register_many(
        [
            SystemInfoTool(),
            CalculatorTool(),
            DateTimeTool(),
            TextStatsTool(),
            WeatherTool(),
            WebSearchTool(),
            FileSummaryTool(knowledge_service=knowledge_service),
            KnowledgeAdminTool(knowledge_service=knowledge_service),
            MemoryAdminTool(memory_service=memory_service),
        ]
    )
    if _filesystem_mcp_enabled():
        filesystem_client = ReadOnlyFilesystemMCPClient.from_env()
        MCPToolRegistryLoader(
            [
                MCPServerConfig(
                    server_id=filesystem_client.server_id,
                    name="Filesystem Read-Only",
                    description="Read-only MCP connector scoped to configured local roots.",
                    risk_level="filesystem/read",
                )
            ],
            filesystem_client,
        ).register_into(registry)
    if _git_mcp_enabled():
        git_client = GitReadOnlyMCPClient.from_env()
        MCPToolRegistryLoader(
            [
                MCPServerConfig(
                    server_id=git_client.server_id,
                    name="Git Read-Only",
                    description="Read-only MCP connector for local git repository inspection.",
                    risk_level="filesystem/read",
                )
            ],
            git_client,
        ).register_into(registry)

    stats = StatsManager(registry=registry, config=cfg)
    workflow_registry = build_default_workflow_registry()
    planner = ToolPlanner(
        registry=registry,
        stats=stats,
        config=cfg,
        client=llm_client,
        workflow_registry=workflow_registry,
    )
    validator = ToolValidation(registry)
    recovery = RecoveryPlanner(planner=planner, validator=validator, config=cfg)
    executor = ToolExecutor(
        registry,
        circuit_registry=circuit_registry,
        retry_backoff=retry_backoff,
    )
    return TaskService(
        rec_planner=recovery,
        task_executor=executor,
        stats=stats,
        run_store=run_store,
        agent_run_store=agent_run_store,
        memory_service=memory_service,
        maintenance_scheduler=maintenance_scheduler,
        max_pending_tasks=max_pending_tasks,
        task_deadline_seconds=task_deadline_seconds,
    )


def _filesystem_mcp_enabled() -> bool:
    return os.getenv("MYAI_MCP_FILESYSTEM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _git_mcp_enabled() -> bool:
    return os.getenv("MYAI_MCP_GIT_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
