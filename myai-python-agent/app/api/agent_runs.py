from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_runtime
from app.privacy.redaction import sanitize_for_api
from app.runtime.container import AppRuntime


router = APIRouter(prefix="/agent/runs", tags=["agent-runs"])


@router.get("")
def list_agent_runs(
    user_id: str,
    conversation_id: int | None = None,
    limit: int = 20,
    include_sensitive: bool = False,
    runtime: AppRuntime = Depends(get_runtime),
):
    runs = runtime.agent_run_store.list_runs(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=min(max(1, limit), 200),
    )
    return sanitize_for_api(
        {"runs": [_agent_run_payload(run) for run in runs]},
        include_sensitive=include_sensitive,
    )


@router.get("/{run_id}")
def get_agent_run(
    run_id: str,
    user_id: str,
    include_sensitive: bool = False,
    runtime: AppRuntime = Depends(get_runtime),
):
    run = runtime.agent_run_store.get(run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="Agent run not found")
    payload = _agent_run_payload(run)
    payload["task_runs"] = _tasks_for_agent(runtime, user_id, run_id)
    return sanitize_for_api(payload, include_sensitive=include_sensitive)


@router.get("/{run_id}/tasks")
def list_agent_tasks(
    run_id: str,
    user_id: str,
    include_sensitive: bool = False,
    runtime: AppRuntime = Depends(get_runtime),
):
    run = runtime.agent_run_store.get(run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return sanitize_for_api(
        {"agent_run_id": run_id, "task_runs": _tasks_for_agent(runtime, user_id, run_id)},
        include_sensitive=include_sensitive,
    )


def _tasks_for_agent(runtime: AppRuntime, user_id: str, run_id: str) -> list[dict]:
    return runtime.task_service.list_runs(
        user_id=user_id,
        agent_run_id=run_id,
        limit=1_000,
    )


def _agent_run_payload(run) -> dict:
    return {
        "run_id": run.run_id,
        "kind": run.kind,
        "user_id": run.user_id,
        "conversation_id": run.conversation_id,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "retryable": run.retryable,
        "steps": [step.__dict__ for step in run.steps],
    }
