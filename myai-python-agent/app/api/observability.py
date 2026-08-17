from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime, get_task_service
from app.observability.events import normalize_task_run
from app.observability.store import observability_store
from app.privacy.redaction import privacy_metadata
from app.privacy.redaction import sanitize_for_api
from app.model.health import model_status_with_probe, probe_model_health
from app.task.service.task_service import TaskService
from app.runtime.container import AppRuntime


router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/summary")
def get_observability_summary(
    include_sensitive: bool = False,
    task_service: TaskService = Depends(get_task_service),
    runtime: AppRuntime = Depends(get_runtime),
):
    task_stats = task_service.stats.snapshot()
    runs = task_service.list_runs(limit=50)
    recent_events = []
    for run in runs[:5]:
        recent_events.extend(normalize_task_run(run))
    connectors = task_service.list_connectors()
    task_status_counts: dict[str, int] = {}
    for run in runs:
        status = str(run.get("status") or "unknown")
        task_status_counts[status] = task_status_counts.get(status, 0) + 1
    tool_failures = [
        {
            "tool_name": name,
            "calls": payload.get("calls", 0),
            "success_rate": payload.get("success_rate", 1.0),
            "avg_latency_ms": payload.get("avg_latency_ms", 0),
        }
        for name, payload in (task_stats.get("tools") or {}).items()
        if int(payload.get("calls") or 0) > 0 and float(payload.get("success_rate") or 0) < 1.0
    ]
    payload = {
        "task": {
            "runs": len(runs),
            "status_counts": task_status_counts,
            "planner": task_stats.get("planner", {}),
            "tools": task_stats.get("tools", {}),
            "tool_failures": tool_failures,
        },
        "connectors": {
            "total": len(connectors),
            "healthy": len([connector for connector in connectors if (connector.get("health") or {}).get("ok")]),
            "items": connectors,
        },
        "eval": observability_store.eval_summary(),
        "model": model_status_with_probe(),
        "events": {
            "recent": recent_events[-50:],
            "count": len(recent_events),
        },
        "runtime": {
            "database": runtime.runtime_repository.pragma_settings(),
            "recovery": runtime.recovery_report,
            "maintenance": {
                "enabled": runtime.maintenance_scheduler is not None,
                "users": runtime.maintenance_scheduler.snapshot()
                if runtime.maintenance_scheduler is not None
                else [],
            },
            "circuits": runtime.circuit_registry.snapshot()
            if runtime.circuit_registry is not None
            else {},
        },
        "privacy": privacy_metadata(include_sensitive),
    }
    return sanitize_for_api(payload, include_sensitive=include_sensitive)


@router.post("/model/probe")
def probe_model_runtime(include_sensitive: bool = False):
    payload = {
        "model_probe": probe_model_health(),
        "privacy": privacy_metadata(include_sensitive),
    }
    return sanitize_for_api(payload, include_sensitive=include_sensitive)


@router.get("/events")
def list_observability_events(
    limit: int = 50,
    include_sensitive: bool = False,
    task_service: TaskService = Depends(get_task_service),
):
    events = []
    for run in task_service.list_runs(limit=20):
        events.extend(normalize_task_run(run))
    events.sort(key=lambda event: str(event.get("started_at") or ""), reverse=True)
    payload = {"events": events[: max(1, limit)], "privacy": privacy_metadata(include_sensitive)}
    return sanitize_for_api(payload, include_sensitive=include_sensitive)
