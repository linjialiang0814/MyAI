from fastapi import Depends, Request

from app.core.service import AgentService
from app.knowledge.service import KnowledgeService
from app.memory.mem_service import MemoryService
from app.runtime.container import AppRuntime
from app.memory.maintenance.scheduler import MemoryMaintenanceScheduler
from app.task.service.task_service import TaskService


def get_runtime(request: Request) -> AppRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise RuntimeError("Application runtime is unavailable outside the FastAPI lifespan")
    return runtime


def get_agent_service(runtime: AppRuntime = Depends(get_runtime)) -> AgentService:
    return runtime.agent_service


def get_memory_service(runtime: AppRuntime = Depends(get_runtime)) -> MemoryService:
    return runtime.memory_service


def get_knowledge_service(runtime: AppRuntime = Depends(get_runtime)) -> KnowledgeService:
    return runtime.knowledge_service


def get_task_service(runtime: AppRuntime = Depends(get_runtime)) -> TaskService:
    return runtime.task_service


def get_memory_maintenance_scheduler(
    runtime: AppRuntime = Depends(get_runtime),
) -> MemoryMaintenanceScheduler | None:
    return runtime.maintenance_scheduler
