from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from app.task.config.task_config import TaskConfig
from app.task.mcp import GitReadOnlyMCPClient, MCPServerConfig, MCPToolDescriptor, MCPToolRegistryLoader, MockMCPClient, ReadOnlyFilesystemMCPClient
from app.task.mcp.policy import map_mcp_tool_policy
from app.task.plan.executor import ToolExecutor
from app.task.plan.planner import ToolPlan, ToolStep
from app.task.service.task_service import TaskService
from app.task.stats.statistics import StatsManager
from app.task.tool.tool_registry import ToolRegistry


BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE = BASE_DIR / "tests" / "fixtures" / "mcp_eval.json"
EVAL_ROOT = Path(
    os.getenv("MYAI_EVAL_WORK_DIR", str(BASE_DIR / ".tmp"))
) / "mcp_eval"


class FixedMCPPlanner:
    def __init__(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        self.tool_name = tool_name
        self.tool_args = tool_args

    def plan(self, content: str, short_context: list[str] | None = None) -> ToolPlan:
        return ToolPlan(
            need_tool=True,
            source="mcp_eval",
            steps=[
                ToolStep(
                    step_id="step1",
                    description="Run MCP eval tool.",
                    tool_name=self.tool_name,
                    tool_args=self.tool_args,
                )
            ],
        )


def run_mcp_report(fixture_path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    _prepare_eval_root()
    try:
        results = [_run_case(case) for case in fixture.get("cases", [])]
    finally:
        shutil.rmtree(EVAL_ROOT, ignore_errors=True)
    skipped = sum(1 for result in results if result.get("skipped"))
    executed = len(results) - skipped
    passed = sum(1 for result in results if result["passed"] and not result.get("skipped"))
    failed = executed - passed
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": round(passed / executed, 4) if executed else 1.0,
        "coverage": _coverage(results),
    }
    return {"summary": summary, "cases": results}


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    coverage = summary.get("coverage") or {}
    lines = [
        "# MCP Evaluation Report",
        "",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Skipped: {summary.get('skipped', 0)}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        f"- Coverage: {', '.join(f'{key}={value}' for key, value in coverage.items())}",
        "",
        "| Case | Type | Passed | Key Result | Errors |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        lines.append(
            "| {case_id} | {case_type} | {passed} | {result} | {errors} |".format(
                case_id=case["id"],
                case_type=case.get("type", ""),
                passed="skipped" if case.get("skipped") else ("yes" if case["passed"] else "no"),
                result=str(case.get("key_result", "")).replace("|", "\\|"),
                errors="; ".join(case.get("errors") or []).replace("|", "\\|"),
            )
        )
    return "\n".join(lines)


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    case_type = str(case.get("type") or "")
    if case_type in {"git_connector_health", "git_execution_trace"}:
        skip_reason = _git_eval_skip_reason()
        if skip_reason:
            return {
                "id": case["id"],
                "type": case_type,
                "passed": False,
                "skipped": True,
                "skip_reason": skip_reason,
                "errors": [],
                "actual": {"skip_reason": skip_reason},
                "key_result": f"skipped: {skip_reason}",
            }
    if case_type == "descriptor":
        actual = _case_descriptor(case)
    elif case_type == "policy":
        actual = _case_policy(case)
    elif case_type == "connector_health":
        actual = _case_connector_health(case)
    elif case_type in {"execution_trace", "path_escape"}:
        actual = _case_execution_trace(case)
    elif case_type == "git_connector_health":
        actual = _case_git_connector_health(case)
    elif case_type == "git_execution_trace":
        actual = _case_git_execution_trace(case)
    elif case_type == "disabled_connector":
        actual = _case_disabled_connector(case)
    else:
        actual = {"error": f"Unknown case type: {case_type}"}
    errors = _check_expectations(actual, case.get("expect") or {})
    return {
        "id": case["id"],
        "type": case_type,
        "passed": not errors,
        "skipped": False,
        "errors": errors,
        "actual": actual,
        "key_result": _key_result(actual),
    }


def _git_eval_skip_reason() -> str | None:
    if not (BASE_DIR.parent / ".git").exists():
        return "Git connector cases require a source checkout with .git metadata."
    if shutil.which("git") is None:
        return "Git connector cases require the git executable."
    return None


def _case_descriptor(case: dict[str, Any]) -> dict[str, Any]:
    descriptor = MCPToolDescriptor(
        server_id="mock-server",
        name="echo_text",
        description="Echo input text.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )
    client = MockMCPClient([descriptor])
    registry = ToolRegistry()
    tools = MCPToolRegistryLoader([MCPServerConfig(server_id="mock-server", name="Mock")], client).register_into(registry)
    tool = tools[0]
    return {
        "registry_name": tool.name,
        "required": tool.schema["function"]["parameters"].get("required", []),
        "risk_level": tool.policy.risk_level,
        "tool_count": len(tools),
    }


def _case_policy(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("descriptor") or {}
    descriptor = MCPToolDescriptor(
        server_id=str(payload.get("server_id") or "mock-server"),
        name=str(payload.get("name") or "tool"),
        description=str(payload.get("description") or ""),
        risk_level=str(payload.get("risk_level") or "safe"),
        retry_count=int(payload.get("retry_count") or 0),
        annotations=dict(payload.get("annotations") or {}),
    )
    return map_mcp_tool_policy(descriptor)


def _case_connector_health(case: dict[str, Any]) -> dict[str, Any]:
    client = ReadOnlyFilesystemMCPClient({"workspace": EVAL_ROOT})
    registry = ToolRegistry()
    MCPToolRegistryLoader(
        [MCPServerConfig(server_id=client.server_id, name="Filesystem Read-Only", risk_level="filesystem/read")],
        client,
    ).register_into(registry)
    service = _service(registry)
    connector = service.list_connectors()[0]
    return {
        "enabled": connector["enabled"],
        "health_ok": connector["health"]["ok"],
        "tool_count": connector["tool_count"],
        "risk_level": connector["risk_summary"]["risk_level"],
        "roots": connector["settings"].get("roots", []),
    }


def _case_execution_trace(case: dict[str, Any]) -> dict[str, Any]:
    client = ReadOnlyFilesystemMCPClient({"workspace": EVAL_ROOT})
    registry = ToolRegistry()
    MCPToolRegistryLoader(
        [MCPServerConfig(server_id=client.server_id, name="Filesystem Read-Only", risk_level="filesystem/read")],
        client,
    ).register_into(registry)
    service = _service(registry, planner=FixedMCPPlanner(str(case["tool_name"]), dict(case.get("tool_args") or {})))
    decision = service.handle_task("run mcp eval", user_id="mcp-eval")
    run = service.get_run(decision.task_run_id) or {}
    events = run.get("events") or []
    mcp_event = next((event for event in events if str(event.get("type", "")).startswith("task.mcp_call.")), {})
    step = (run.get("steps") or [{}])[0]
    result = step.get("result") or {}
    metadata = result.get("metadata") or {}
    return {
        "success": decision.success,
        "event_type": mcp_event.get("type"),
        "connector": metadata.get("connector"),
        "error_category": metadata.get("error_category"),
        "mcp_call_status": metadata.get("mcp_call_status"),
        "has_step_event": any(event.get("type") == mcp_event.get("type") for event in step.get("events") or []),
    }


def _case_disabled_connector(case: dict[str, Any]) -> dict[str, Any]:
    client = ReadOnlyFilesystemMCPClient({"workspace": EVAL_ROOT})
    registry = ToolRegistry()
    tools = MCPToolRegistryLoader(
        [MCPServerConfig(server_id=client.server_id, name="Disabled Filesystem", enabled=False)],
        client,
    ).register_into(registry)
    return {"registered_tools": len(tools)}


def _case_git_connector_health(case: dict[str, Any]) -> dict[str, Any]:
    client = GitReadOnlyMCPClient(BASE_DIR.parent)
    registry = ToolRegistry()
    MCPToolRegistryLoader(
        [MCPServerConfig(server_id=client.server_id, name="Git Read-Only", risk_level="filesystem/read")],
        client,
    ).register_into(registry)
    service = _service(registry)
    connector = service.list_connectors()[0]
    return {
        "enabled": connector["enabled"],
        "health_ok": connector["health"]["ok"],
        "tool_count": connector["tool_count"],
        "risk_level": connector["risk_summary"]["risk_level"],
    }


def _case_git_execution_trace(case: dict[str, Any]) -> dict[str, Any]:
    client = GitReadOnlyMCPClient(BASE_DIR.parent)
    registry = ToolRegistry()
    MCPToolRegistryLoader(
        [MCPServerConfig(server_id=client.server_id, name="Git Read-Only", risk_level="filesystem/read")],
        client,
    ).register_into(registry)
    service = _service(registry, planner=FixedMCPPlanner(str(case["tool_name"]), dict(case.get("tool_args") or {})))
    decision = service.handle_task("run git mcp eval", user_id="mcp-eval")
    run = service.get_run(decision.task_run_id) or {}
    events = run.get("events") or []
    mcp_event = next((event for event in events if str(event.get("type", "")).startswith("task.mcp_call.")), {})
    step = (run.get("steps") or [{}])[0]
    result = step.get("result") or {}
    metadata = result.get("metadata") or {}
    return {
        "success": decision.success,
        "event_type": mcp_event.get("type"),
        "connector": metadata.get("connector"),
        "error_category": metadata.get("error_category"),
        "mcp_call_status": metadata.get("mcp_call_status"),
        "has_step_event": any(event.get("type") == mcp_event.get("type") for event in step.get("events") or []),
    }


def _service(registry: ToolRegistry, planner: Any | None = None) -> TaskService:
    stats = StatsManager(registry=registry, config=TaskConfig(update_trigger_weights=False))
    return TaskService(
        rec_planner=planner or object(),
        task_executor=ToolExecutor(registry),
        stats=stats,
    )


def _check_expectations(actual: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, expected in expect.items():
        if actual.get(key) != expected:
            errors.append(f"{key} expected={expected!r} actual={actual.get(key)!r}")
    return errors


def _key_result(actual: dict[str, Any]) -> str:
    for key in ("event_type", "risk_level", "health_ok", "registry_name", "registered_tools"):
        if key in actual:
            return f"{key}={actual[key]}"
    if "error" in actual:
        return str(actual["error"])
    return "ok"


def _coverage(results: list[dict[str, Any]]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for result in results:
        case_type = str(result.get("type") or "unknown")
        coverage[case_type] = coverage.get(case_type, 0) + 1
    return coverage


def _prepare_eval_root() -> None:
    shutil.rmtree(EVAL_ROOT, ignore_errors=True)
    (EVAL_ROOT / "notes").mkdir(parents=True, exist_ok=True)
    (EVAL_ROOT / "notes" / "mcp_eval.txt").write_text("MCP eval fixture document.", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MCP evaluation fixture and render a report.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = run_mcp_report(args.fixture)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    if args.strict and report["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
