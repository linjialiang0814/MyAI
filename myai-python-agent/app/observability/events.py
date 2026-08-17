from __future__ import annotations

from typing import Any


def normalize_task_run(run: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    for index, event in enumerate(run.get("events") or []):
        metadata = event.get("metadata") or {}
        event_type = str(event.get("type") or "task.event")
        events.append(
            {
                "event_id": event.get("event_id") or f"{run.get('task_run_id', 'task')}-{index}",
                "source": "python-agent",
                "domain": _task_domain(event_type),
                "type": event_type,
                "status": event.get("status") or run.get("status") or "unknown",
                "started_at": metadata.get("call_started_at") or event.get("timestamp"),
                "finished_at": metadata.get("call_finished_at") or event.get("timestamp"),
                "latency_ms": metadata.get("latency_ms") or metadata.get("call_latency_ms"),
                "user_id": run.get("user_id"),
                "conversation_id": None,
                "run_id": run.get("task_run_id"),
                "task_run_id": run.get("task_run_id"),
                "step_id": event.get("step_id"),
                "tool_name": metadata.get("tool_name") or metadata.get("registry_name"),
                "connector_id": metadata.get("server_id"),
                "error_category": metadata.get("error_category"),
                "error": metadata.get("error") or run.get("error"),
                "evidence_count": _evidence_count(metadata),
                "message": event.get("message"),
                "metadata": metadata,
            }
        )
    return events


def normalize_agent_trace(trace: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    for index, step in enumerate(trace.get("steps") or []):
        metadata = step.get("metadata") or {}
        step_name = str(step.get("name") or "agent.step")
        events.append(
            {
                "event_id": f"{trace.get('run_id', 'agent')}-{index}",
                "source": "python-agent",
                "domain": _agent_domain(step_name),
                "type": step_name,
                "status": step.get("status") or "unknown",
                "started_at": step.get("started_at"),
                "finished_at": step.get("finished_at"),
                "latency_ms": step.get("latency_ms"),
                "user_id": trace.get("user_id"),
                "conversation_id": trace.get("conversation_id"),
                "run_id": trace.get("run_id"),
                "task_run_id": _nested_task_run_id(metadata),
                "step_id": None,
                "tool_name": None,
                "connector_id": None,
                "error_category": None,
                "error": metadata.get("error"),
                "evidence_count": _evidence_count(metadata),
                "message": step.get("output_summary") or step.get("input_summary"),
                "metadata": metadata,
            }
        )
    return events


def _task_domain(event_type: str) -> str:
    if event_type.startswith("task.mcp_call"):
        return "mcp"
    if "memory" in event_type:
        return "memory"
    if "tool_policy" in event_type or "step" in event_type:
        return "tool"
    return "task"


def _agent_domain(step_name: str) -> str:
    if step_name.startswith("memory."):
        return "memory"
    if step_name.startswith("knowledge."):
        return "knowledge"
    if step_name.startswith("task."):
        return "task"
    if step_name.startswith("llm."):
        return "llm"
    if step_name.startswith("context."):
        return "context"
    return "agent"


def _evidence_count(metadata: dict[str, Any]) -> int:
    for key in ("citations", "selected", "hits", "snippets", "memories"):
        value = metadata.get(key)
        if isinstance(value, list):
            return len(value)
    selected_count = metadata.get("selected_count")
    if isinstance(selected_count, int):
        return selected_count
    return 0


def _nested_task_run_id(metadata: dict[str, Any]) -> str | None:
    result = metadata.get("result")
    if isinstance(result, dict):
        value = result.get("task_run_id")
        if value:
            return str(value)
    plan = metadata.get("plan")
    if isinstance(plan, dict):
        value = plan.get("task_run_id")
        if value:
            return str(value)
    return None
