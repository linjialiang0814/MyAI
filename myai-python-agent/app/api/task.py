from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.dependencies import get_task_service
from app.schemas.task_request import TaskRequest
from app.schemas.task_run_access_request import TaskRunAccessRequest
from app.schemas.task_response import TaskResponse
from app.privacy.redaction import privacy_metadata
from app.privacy.redaction import sanitize_for_api
from app.task.service.task_service import TaskService

router = APIRouter()

@router.post("/task")
def get_task(
    request: TaskRequest,
    include_sensitive: bool = False,
    task_service: TaskService = Depends(get_task_service),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    decision = task_service.handle_task(
        request.content,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        agent_run_id=request.agent_run_id,
        idempotency_key=_resolve_idempotency_key(request.idempotency_key, idempotency_header),
    )
    response = TaskResponse(
        task_run_id=decision.task_run_id,
        agent_run_id=decision.agent_run_id,
        conversation_id=decision.conversation_id,
        status=decision.status,
        content=decision.content,
        plan=decision.plan,
        result=decision.result,
        reward=decision.reward,
        success=decision.success,
        error=decision.error,
        error_code=decision.error_code,
        retryable=decision.retryable,
        latency_ms=decision.latency_ms,
        events=decision.events,
    )
    return sanitize_for_api(response.model_dump(), include_sensitive=include_sensitive)


@router.get("/task/runs/{task_run_id}")
def get_task_run(
    task_run_id: str,
    user_id: str,
    include_sensitive: bool = False,
    task_service: TaskService = Depends(get_task_service),
):
    run = task_service.get_run(task_run_id, user_id=user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Task run not found")
    return sanitize_for_api(run, include_sensitive=include_sensitive)


@router.get("/task/runs")
def list_task_runs(
    user_id: str,
    limit: int = 20,
    include_sensitive: bool = False,
    task_service: TaskService = Depends(get_task_service),
):
    payload = {"runs": task_service.list_runs(user_id=user_id, limit=limit)}
    return sanitize_for_api(payload, include_sensitive=include_sensitive)


@router.get("/task/workflows")
def list_task_workflows(task_service: TaskService = Depends(get_task_service)):
    return {"workflows": task_service.list_workflows()}


@router.get("/task/tools")
def list_task_tools(
    include_sensitive: bool = False,
    task_service: TaskService = Depends(get_task_service),
):
    tools = task_service.list_tools()
    connectors = task_service.list_connectors()
    summary = {
        "total": len(tools),
        "local": len([tool for tool in tools if tool.get("source") == "local"]),
        "mcp": len([tool for tool in tools if tool.get("source") == "mcp"]),
        "permission_required": len([tool for tool in tools if (tool.get("policy") or {}).get("requires_confirmation")]),
        "connectors": len(connectors),
        "healthy_connectors": len([connector for connector in connectors if (connector.get("health") or {}).get("ok")]),
    }
    payload = {"summary": summary, "tools": tools, "connectors": connectors, "privacy": privacy_metadata(include_sensitive)}
    return sanitize_for_api(payload, include_sensitive=include_sensitive)


@router.post("/task/runs")
def start_task_run(
    request: TaskRequest,
    include_sensitive: bool = False,
    task_service: TaskService = Depends(get_task_service),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    run = task_service.start_background_task(
        request.content,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        agent_run_id=request.agent_run_id,
        idempotency_key=_resolve_idempotency_key(request.idempotency_key, idempotency_header),
    )
    return sanitize_for_api(run, include_sensitive=include_sensitive)


@router.post("/task/runs/{task_run_id}/cancel")
def cancel_task_run(
    task_run_id: str,
    request: TaskRunAccessRequest,
    include_sensitive: bool = False,
    task_service: TaskService = Depends(get_task_service),
):
    run = task_service.request_cancel(task_run_id, user_id=request.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Task run not found")
    return sanitize_for_api(run, include_sensitive=include_sensitive)


def _resolve_idempotency_key(body_key: str | None, header_key: str | None) -> str | None:
    normalized_body = (body_key or "").strip()
    normalized_header = (header_key or "").strip()
    if normalized_body and normalized_header and normalized_body != normalized_header:
        raise HTTPException(status_code=400, detail="Idempotency key header and body value differ")
    return normalized_header or normalized_body or None
