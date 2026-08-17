from __future__ import annotations

from dataclasses import asdict, dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Callable


BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EvalReportDefinition:
    report_id: str
    name: str
    domain: str
    description: str
    module: str
    command: str
    fixture_path: str | None = None
    strict_supported: bool = True
    formats: list[str] = field(default_factory=lambda: ["markdown", "json"])
    deterministic: bool = True
    requires_live_llm: bool = False
    coverage: list[str] = field(default_factory=list)
    last_run: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_eval_reports() -> list[dict[str, Any]]:
    return [definition.to_dict() for definition in DEFAULT_EVAL_REPORTS]


def get_eval_report(report_id: str) -> dict[str, Any] | None:
    for definition in DEFAULT_EVAL_REPORTS:
        if definition.report_id == report_id:
            return definition.to_dict()
    return None


def get_eval_report_definition(report_id: str) -> EvalReportDefinition | None:
    for definition in DEFAULT_EVAL_REPORTS:
        if definition.report_id == report_id:
            return definition
    return None


def iter_eval_report_definitions() -> list[EvalReportDefinition]:
    return list(DEFAULT_EVAL_REPORTS)


def load_report_functions(definition: EvalReportDefinition) -> tuple[Callable[..., dict[str, Any]], Callable[[dict[str, Any]], str] | None]:
    module = import_module(definition.module)
    run_fn = getattr(module, _RUN_FUNCTIONS[definition.report_id])
    render_name = _RENDER_FUNCTIONS.get(definition.report_id)
    render_fn = getattr(module, render_name) if render_name and hasattr(module, render_name) else None
    return run_fn, render_fn


def _fixture(path: str) -> str:
    return str(BASE_DIR / "tests" / "fixtures" / path)


DEFAULT_EVAL_REPORTS = [
    EvalReportDefinition(
        report_id="memory_governance",
        name="Memory Governance Report",
        domain="memory",
        description="Evaluates memory write decisions, confidence calibration, pending behavior, slots, conflicts, and governance metadata.",
        module="app.memory.evaluation.governance_report",
        command="python -m app.memory.evaluation.governance_report --format markdown --strict",
        fixture_path=_fixture("memory_governance_eval.json"),
        coverage=[
            "write_decision",
            "slot_extraction",
            "dedup_conflict",
            "pending_behavior",
            "confidence_calibration",
            "citation_metadata",
        ],
    ),
    EvalReportDefinition(
        report_id="memory_llm_calibration",
        name="Memory LLM Calibration",
        domain="memory",
        description="Runs live LLM memory extraction calibration cases when an LLM provider is configured.",
        module="app.memory.evaluation.calibrate",
        command="python -m app.memory.evaluation.calibrate --strict",
        fixture_path=_fixture("memory_llm_calibration.json"),
        formats=["json"],
        deterministic=False,
        requires_live_llm=True,
        coverage=["llm_extraction", "write_decision", "slot_quality", "confidence_bounds"],
    ),
    EvalReportDefinition(
        report_id="task_runtime",
        name="Task Runtime Report",
        domain="task",
        description="Evaluates task planning, workflow routing, tool execution, policy, retry/recovery, and memory-aware task planning.",
        module="app.task.evaluation.runtime_report",
        command="python -m app.task.evaluation.runtime_report --format markdown --strict",
        fixture_path=_fixture("task_runtime_eval.json"),
        coverage=[
            "no_tool",
            "single_tool",
            "multi_step",
            "invalid_args",
            "permission_required",
            "retry_recovery",
            "memory_aware_planning",
        ],
    ),
    EvalReportDefinition(
        report_id="knowledge_retrieval",
        name="Knowledge Retrieval And QA Report",
        domain="knowledge",
        description="Evaluates knowledge ingestion, hybrid retrieval, citation completeness, duplicate detection, and document QA behavior.",
        module="app.knowledge.evaluation.report",
        command="python -m app.knowledge.evaluation.report --format markdown --strict",
        fixture_path=_fixture("knowledge_eval.json"),
        coverage=[
            "upload_parse",
            "duplicate_detection",
            "keyword_retrieval",
            "semantic_retrieval",
            "citation_completeness",
            "document_qa",
        ],
    ),
    EvalReportDefinition(
        report_id="mcp_tool_ecosystem",
        name="MCP Tool Ecosystem Report",
        domain="mcp",
        description="Evaluates MCP descriptor conversion, policy mapping, connector health, execution trace, fail-closed behavior, and read-only connectors.",
        module="app.task.evaluation.mcp_report",
        command="python -m app.task.evaluation.mcp_report --format markdown --strict",
        fixture_path=_fixture("mcp_eval.json"),
        coverage=[
            "descriptor_conversion",
            "policy_mapping",
            "connector_health",
            "execution_trace",
            "fail_closed",
            "disabled_connector",
            "git_connector",
        ],
    ),
]


_RUN_FUNCTIONS = {
    "memory_governance": "run_governance_report",
    "memory_llm_calibration": "run_calibration",
    "task_runtime": "run_runtime_report",
    "knowledge_retrieval": "run_knowledge_report",
    "mcp_tool_ecosystem": "run_mcp_report",
}


_RENDER_FUNCTIONS = {
    "memory_governance": "render_markdown",
    "task_runtime": "render_markdown",
    "knowledge_retrieval": "render_markdown",
    "mcp_tool_ecosystem": "render_markdown",
}
