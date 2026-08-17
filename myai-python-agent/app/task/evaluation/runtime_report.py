from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.mem_service import MemoryService
from app.memory.model.mem_item import MemoryItem
from app.memory.store.in_mem_store import MemoryStore
from app.task.config.task_config import TaskConfig
from app.task.plan.executor import ToolExecutor
from app.task.plan.planner import ToolPlanner
from app.task.plan.recovery import RecoveryPlanner
from app.task.plan.validation import ToolValidation
from app.task.service.task_service import TaskService
from app.task.stats.statistics import StatsManager
from app.task.tool.tool import Tool, ToolPolicy, ToolResult
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


BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE = BASE_DIR / "tests" / "fixtures" / "task_runtime_eval.json"


class EvalFlakyRetryTool(Tool):
    name = "flaky_retry"
    description = "Eval-only tool that fails once with a transient timeout, then succeeds."
    idempotent = True
    policy = ToolPolicy(risk_level="network", timeout_seconds=1.0, retry_count=1)
    trigger_words = {"flaky retry": 2.0, "retry please": 1.2}

    def __init__(self) -> None:
        self.calls = 0

    def run(self, **kwargs) -> ToolResult:
        self.calls += 1
        if self.calls == 1:
            return ToolResult(success=False, error="temporary network timeout")
        return ToolResult(success=True, data={"calls": self.calls})


def run_runtime_report(fixture_path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    service = build_eval_task_service()
    results = [_run_case(service, case) for case in fixture.get("cases", [])]
    passed = sum(1 for result in results if result["passed"])
    failed = len(results) - passed
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(results), 4) if results else 1.0,
    }
    return {
        "summary": summary,
        "cases": results,
        "stats": service.stats.snapshot(),
    }


def build_eval_task_service() -> TaskService:
    embedding = StubEmbedding()
    memory_service = MemoryService(embedding_client=embedding, memory_store=MemoryStore())
    registry = ToolRegistry()
    registry.register_many(
        [
            SystemInfoTool(),
            CalculatorTool(),
            DateTimeTool(),
            TextStatsTool(),
            WeatherTool(),
            WebSearchTool(),
            FileSummaryTool(),
            KnowledgeAdminTool(),
            MemoryAdminTool(memory_service=memory_service),
            EvalFlakyRetryTool(),
        ]
    )
    config = TaskConfig(update_trigger_weights=False)
    stats = StatsManager(registry=registry, config=config)
    planner = ToolPlanner(
        registry=registry,
        stats=stats,
        config=config,
        workflow_registry=build_default_workflow_registry(),
    )
    return TaskService(
        rec_planner=RecoveryPlanner(planner=planner, validator=ToolValidation(registry), config=config),
        task_executor=ToolExecutor(registry),
        stats=stats,
        memory_service=memory_service,
    )


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Task Runtime Evaluation Report",
        "",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        "",
        "| Case | Passed | Status | Source | Tools | Latency ms | Notes |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for case in report["cases"]:
        tools = ", ".join(case.get("tools") or [])
        notes = "; ".join(case.get("errors") or []) or case.get("notes", "")
        lines.append(
            "| {case_id} | {passed} | {status} | {source} | {tools} | {latency} | {notes} |".format(
                case_id=case["id"],
                passed="yes" if case["passed"] else "no",
                status=case.get("status", ""),
                source=case.get("plan_source", ""),
                tools=tools,
                latency=case.get("latency_ms") or 0,
                notes=str(notes).replace("|", "\\|"),
            )
        )
    stats = report.get("stats", {})
    lines.extend(["", "## Tool Stats", "", "| Tool | Calls | Success Rate | Avg Latency ms |", "| --- | ---: | ---: | ---: |"])
    for tool_name, payload in (stats.get("tools") or {}).items():
        if int(payload.get("calls") or 0) == 0:
            continue
        lines.append(
            f"| {tool_name} | {payload['calls']} | {float(payload['success_rate']):.2%} | {payload['avg_latency_ms']} |"
        )
    return "\n".join(lines)


def _run_case(service: TaskService, case: dict[str, Any]) -> dict[str, Any]:
    user_id = str(case.get("user_id") or f"eval-{case['id']}")
    _seed_memories(service, user_id, case.get("seed_memories") or [])
    decision = service.handle_task(str(case["content"]), user_id=user_id)
    plan = decision.plan or {}
    result = decision.result or {}
    steps = result.get("steps") or []
    tools = [str(step.get("tool_name")) for step in steps if step.get("tool_name")]
    if not tools and plan.get("tool_name"):
        tools = [str(plan["tool_name"])]

    actual = {
        "id": case["id"],
        "passed": True,
        "errors": [],
        "status": decision.status,
        "success": decision.success,
        "plan_source": plan.get("source"),
        "workflow": (plan.get("workflow") or {}).get("name"),
        "tools": tools,
        "step_count": len(steps or plan.get("steps") or []),
        "latency_ms": decision.latency_ms,
        "failure_reason": decision.error or _first_step_error(steps),
        "permission_required": _has_permission_required_event(decision.events or []),
        "recovery_status": _first_recovery_status(steps),
        "memory_selected_count": len((plan.get("memory_context") or {}).get("selected") or []),
    }
    errors = _check_expectations(actual, plan, case.get("expect") or {})
    actual["errors"] = errors
    actual["passed"] = not errors
    return actual


def _seed_memories(service: TaskService, user_id: str, memories: list[dict[str, Any]]) -> None:
    if not memories or not service.memory_service:
        return
    embedding = service.memory_service.embedding_client
    for memory in memories:
        service.memory_service.memory_store.add_item(
            user_id,
            MemoryItem(
                content=memory["content"],
                vector=embedding.embed(memory["content"]),
                mem_type=memory.get("mem_type", "general"),
                metadata={
                    "slot": memory.get("slot", ""),
                    "value": memory.get("value", memory["content"]),
                    "source": "task_runtime_eval_fixture",
                    "review_status": "accepted",
                    "retrieval_enabled": True,
                    "sensitivity": "normal",
                    "is_current": True,
                },
            ),
        )


def _check_expectations(actual: dict[str, Any], plan: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("success", "status", "plan_source", "workflow", "permission_required", "recovery_status"):
        if key in expect and actual.get(key) != expect[key]:
            errors.append(f"{key} expected={expect[key]!r} actual={actual.get(key)!r}")
    if "need_tool" in expect and plan.get("need_tool") != expect["need_tool"]:
        errors.append(f"need_tool expected={expect['need_tool']!r} actual={plan.get('need_tool')!r}")
    if "tool" in expect and expect["tool"] not in actual.get("tools", []):
        errors.append(f"tool expected={expect['tool']!r} actual={actual.get('tools')!r}")
    if "tools" in expect and actual.get("tools") != expect["tools"]:
        errors.append(f"tools expected={expect['tools']!r} actual={actual.get('tools')!r}")
    if "step_count" in expect and actual.get("step_count") != expect["step_count"]:
        errors.append(f"step_count expected={expect['step_count']!r} actual={actual.get('step_count')!r}")
    if "failure_contains" in expect and expect["failure_contains"] not in str(actual.get("failure_reason") or ""):
        errors.append(f"failure_contains expected token={expect['failure_contains']!r} actual={actual.get('failure_reason')!r}")
    if "memory_selected_min" in expect and actual.get("memory_selected_count", 0) < int(expect["memory_selected_min"]):
        errors.append(
            f"memory_selected_min expected>={expect['memory_selected_min']} actual={actual.get('memory_selected_count')}"
        )
    return errors


def _first_step_error(steps: list[dict[str, Any]]) -> str:
    for step in steps:
        error = (step.get("result") or {}).get("error")
        if error:
            return str(error)
    return ""


def _first_recovery_status(steps: list[dict[str, Any]]) -> str | None:
    for step in steps:
        status = ((step.get("result") or {}).get("metadata") or {}).get("recovery_status")
        if status and status != "not_needed":
            return str(status)
    return None


def _has_permission_required_event(events: list[dict[str, Any]]) -> bool:
    return any(event.get("type") == "task.tool_policy.permission_required" for event in events)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run task runtime evaluation fixture and render a report.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = run_runtime_report(args.fixture)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    if args.strict and report["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
