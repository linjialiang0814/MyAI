from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.task.plan.planner import ToolPlan, ToolStep
from app.task.tool.tool_registry import ToolRegistry


@dataclass
class WorkflowStepTemplate:
    step_id: str
    description: str
    tool_name: str
    tool_args: dict[str, Any] = field(default_factory=dict)
    output_key: str | None = None
    extract_path: str | None = None
    use_tool_extract_args: bool = False

    def to_step(self, content: str, tool_registry: ToolRegistry) -> ToolStep:
        args = dict(self.tool_args or {})
        if self.use_tool_extract_args:
            tool = tool_registry.get_tool(self.tool_name)
            if tool is not None:
                args.update(tool.extract_args(content))
        return ToolStep(
            step_id=self.step_id,
            description=self.description,
            tool_name=self.tool_name,
            tool_args=args,
            output_key=self.output_key,
            extract_path=self.extract_path,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowDefinition:
    name: str
    description: str
    triggers: dict[str, float]
    required_tools: list[str]
    parameters: dict[str, Any]
    steps: list[WorkflowStepTemplate]
    permission_policy: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    final_response: str | None = None
    match_threshold: float = 1.0

    def match_score(self, content: str) -> tuple[float, dict[str, float]]:
        normalized = content.lower()
        matched = {
            trigger: weight
            for trigger, weight in self.triggers.items()
            if trigger.lower() in normalized
        }
        return sum(matched.values()), matched

    def can_run(self, tool_registry: ToolRegistry) -> bool:
        return all(tool_registry.has_tool(tool_name) for tool_name in self.required_tools)

    def to_plan(self, content: str, tool_registry: ToolRegistry, score: float, matched: dict[str, float]) -> ToolPlan:
        steps = [step.to_step(content, tool_registry) for step in self.steps]
        return ToolPlan(
            need_tool=True,
            tool_name=steps[0].tool_name if len(steps) == 1 else None,
            tool_args=steps[0].tool_args if len(steps) == 1 else {},
            steps=steps,
            final_response=self.final_response,
            source="workflow",
            score=score,
            matched=matched,
            rationale=f"Workflow matched: {self.name}",
            workflow={
                "name": self.name,
                "description": self.description,
                "required_tools": self.required_tools,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "triggers": self.triggers,
            "required_tools": self.required_tools,
            "parameters": self.parameters,
            "steps": [step.to_dict() for step in self.steps],
            "permission_policy": self.permission_policy,
            "output_schema": self.output_schema,
            "final_response": self.final_response,
            "match_threshold": self.match_threshold,
        }


class WorkflowRegistry:
    def __init__(self, workflows: list[WorkflowDefinition] | None = None) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}
        for workflow in workflows or []:
            self.register(workflow)

    def register(self, workflow: WorkflowDefinition) -> None:
        self._workflows[workflow.name] = workflow

    def list_workflows(self) -> list[dict[str, Any]]:
        return [workflow.to_dict() for workflow in self._workflows.values()]

    def match(self, content: str, tool_registry: ToolRegistry) -> ToolPlan | None:
        best: tuple[WorkflowDefinition, float, dict[str, float]] | None = None
        for workflow in self._workflows.values():
            if not workflow.can_run(tool_registry):
                continue
            score, matched = workflow.match_score(content)
            if score < workflow.match_threshold:
                continue
            if best is None or score > best[1]:
                best = (workflow, score, matched)
        if best is None:
            return None
        workflow, score, matched = best
        return workflow.to_plan(content, tool_registry, score, matched)


def build_default_workflow_registry() -> WorkflowRegistry:
    return WorkflowRegistry(
        [
            WorkflowDefinition(
                name="memory_policy_inspection",
                description="Inspect memory slot, governance, and calibration policies.",
                triggers={
                    "memory policy inspection": 2.0,
                    "inspect memory policy": 1.8,
                    "memory policy": 1.4,
                    "slot policy": 1.3,
                },
                required_tools=["memory_admin"],
                parameters={"operation": "policy_inspection", "mem_type": "optional", "slot": "optional"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Inspect memory governance policy",
                        tool_name="memory_admin",
                        tool_args={"operation": "policy_inspection"},
                    )
                ],
                permission_policy={"risk_level": "sensitive", "requires_confirmation": False},
                output_schema={"operation": "policy_inspection", "slot_count": "number"},
            ),
            WorkflowDefinition(
                name="memory_eval_report",
                description="Run the memory governance eval report.",
                triggers={
                    "memory eval report": 2.0,
                    "memory governance report": 1.8,
                    "calibration report": 1.4,
                    "memory report": 1.2,
                },
                required_tools=["memory_admin"],
                parameters={"operation": "eval_report", "report_format": "summary|markdown|json"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Run memory governance eval report",
                        tool_name="memory_admin",
                        tool_args={"operation": "eval_report", "report_format": "summary"},
                    )
                ],
                permission_policy={"risk_level": "sensitive", "requires_confirmation": False},
                output_schema={"operation": "eval_report", "report": "object"},
            ),
            WorkflowDefinition(
                name="memory_maintenance",
                description="Run memory maintenance for the current user.",
                triggers={
                    "memory maintenance": 2.0,
                    "maintain memory": 1.8,
                    "memory cleanup": 1.5,
                },
                required_tools=["memory_admin"],
                parameters={"operation": "maintenance", "user_id": "runtime"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Run memory maintenance",
                        tool_name="memory_admin",
                        tool_args={"operation": "maintenance"},
                    )
                ],
                permission_policy={"risk_level": "sensitive", "requires_confirmation": True},
                output_schema={"operation": "maintenance", "summary": "string"},
            ),
            WorkflowDefinition(
                name="knowledge_file_summary",
                description="Summarize a file from the user's knowledge base.",
                triggers={
                    "summarize file": 2.0,
                    "file summary": 1.6,
                    "document summary": 1.5,
                },
                required_tools=["file_summary"],
                parameters={"file_name": "optional", "file_id": "optional", "query": "content"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Summarize a knowledge-base file",
                        tool_name="file_summary",
                        use_tool_extract_args=True,
                    )
                ],
                permission_policy={"risk_level": "filesystem", "requires_confirmation": False},
                output_schema={"summary": "string", "highlights": "array", "keywords": "array"},
            ),
            WorkflowDefinition(
                name="knowledge_document_qa",
                description="Ask a focused question against a selected knowledge-base document.",
                triggers={
                    "document qa": 2.0,
                    "ask document": 1.8,
                    "ask this document": 1.8,
                    "knowledge qa": 1.5,
                    "文档问答": 2.0,
                    "问这个文档": 1.8,
                },
                required_tools=["knowledge_admin"],
                parameters={"operation": "document_qa", "file_name": "optional", "file_id": "optional", "question": "content"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Answer question using document-scoped knowledge evidence",
                        tool_name="knowledge_admin",
                        tool_args={"operation": "document_qa"},
                        use_tool_extract_args=True,
                    )
                ],
                permission_policy={"risk_level": "filesystem", "requires_confirmation": False},
                output_schema={"answer": "string", "citations": "array", "hits": "array"},
            ),
            WorkflowDefinition(
                name="knowledge_study_notes",
                description="Generate structured study notes from a knowledge-base document.",
                triggers={
                    "study notes": 2.0,
                    "make study notes": 1.8,
                    "review notes": 1.5,
                    "学习笔记": 2.0,
                    "复习笔记": 1.8,
                },
                required_tools=["knowledge_admin"],
                parameters={"operation": "study_notes", "file_name": "optional", "file_id": "optional", "query": "content"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Generate study notes with source citations",
                        tool_name="knowledge_admin",
                        tool_args={"operation": "study_notes"},
                        use_tool_extract_args=True,
                    )
                ],
                permission_policy={"risk_level": "filesystem", "requires_confirmation": False},
                output_schema={"summary": "string", "outline": "array", "key_terms": "array", "citations": "array"},
            ),
            WorkflowDefinition(
                name="knowledge_qa_cards",
                description="Generate Q&A cards from a knowledge-base document.",
                triggers={
                    "qa cards": 2.0,
                    "flashcards": 1.8,
                    "question cards": 1.5,
                    "问答卡": 2.0,
                    "题卡": 1.7,
                },
                required_tools=["knowledge_admin"],
                parameters={"operation": "qa_cards", "file_name": "optional", "file_id": "optional", "query": "content"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Generate document Q&A cards",
                        tool_name="knowledge_admin",
                        tool_args={"operation": "qa_cards"},
                        use_tool_extract_args=True,
                    )
                ],
                permission_policy={"risk_level": "filesystem", "requires_confirmation": False},
                output_schema={"cards": "array", "card_count": "number"},
            ),
            WorkflowDefinition(
                name="knowledge_document_compare",
                description="Compare two knowledge-base documents using their structured profiles.",
                triggers={
                    "compare documents": 2.0,
                    "compare files": 1.8,
                    "document comparison": 1.6,
                    "对比文档": 2.0,
                    "比较文档": 1.8,
                },
                required_tools=["knowledge_admin"],
                parameters={"operation": "compare_documents", "file_name": "required", "other_file_name": "required"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Compare two knowledge-base documents",
                        tool_name="knowledge_admin",
                        tool_args={"operation": "compare_documents"},
                        use_tool_extract_args=True,
                    )
                ],
                permission_policy={"risk_level": "filesystem", "requires_confirmation": False},
                output_schema={"files": "array", "shared_terms": "array", "first_only_terms": "array", "second_only_terms": "array"},
            ),
            WorkflowDefinition(
                name="knowledge_maintenance",
                description="Run a dry-run knowledge-base maintenance health report.",
                triggers={
                    "knowledge maintenance": 2.0,
                    "maintain knowledge": 1.8,
                    "knowledge cleanup": 1.5,
                    "knowledge health": 1.4,
                    "知识库维护": 2.0,
                    "知识库健康": 1.6,
                },
                required_tools=["knowledge_admin"],
                parameters={"operation": "maintenance", "dry_run": True, "user_id": "runtime"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Run knowledge-base maintenance health check",
                        tool_name="knowledge_admin",
                        tool_args={"operation": "maintenance", "dry_run": True},
                        use_tool_extract_args=True,
                    )
                ],
                permission_policy={"risk_level": "filesystem", "requires_confirmation": False},
                output_schema={"status": "string", "summary": "object", "actions": "array"},
            ),
            WorkflowDefinition(
                name="knowledge_eval_report",
                description="Run the knowledge retrieval and QA eval report.",
                triggers={
                    "knowledge eval report": 2.0,
                    "knowledge evaluation": 1.8,
                    "knowledge report": 1.5,
                    "rag eval": 1.4,
                    "知识库评测": 2.0,
                    "知识库报告": 1.6,
                },
                required_tools=["knowledge_admin"],
                parameters={"operation": "eval_report", "report_format": "summary|markdown|json"},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Run knowledge evaluation report",
                        tool_name="knowledge_admin",
                        tool_args={"operation": "eval_report", "report_format": "summary"},
                        use_tool_extract_args=True,
                    )
                ],
                permission_policy={"risk_level": "filesystem", "requires_confirmation": False},
                output_schema={"operation": "eval_report", "report": "object"},
            ),
            WorkflowDefinition(
                name="environment_diagnostics",
                description="Inspect local runtime environment information.",
                triggers={
                    "environment diagnostics": 2.0,
                    "system diagnostics": 1.8,
                    "project status inspection": 1.4,
                },
                required_tools=["system_info"],
                parameters={},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Collect system diagnostics",
                        tool_name="system_info",
                    )
                ],
                final_response=(
                    "Environment summary: OS={step1.data.os}, CPU cores={step1.data.cpu_count}, "
                    "memory used={step1.data.memory_used_gb}GB of {step1.data.memory_total_gb}GB."
                ),
                permission_policy={"risk_level": "safe", "requires_confirmation": False},
                output_schema={"os": "string", "cpu_count": "number", "memory_total_gb": "number"},
            ),
            WorkflowDefinition(
                name="mcp_filesystem_read_summary",
                description="Read a project file through the read-only filesystem MCP connector and return an inspectable summary.",
                triggers={
                    "read project file": 2.0,
                    "summarize project file": 2.0,
                    "read local file": 1.8,
                    "summarize local file": 1.8,
                    "mcp read file": 1.6,
                    "读取项目文件": 2.0,
                    "总结项目文件": 2.0,
                    "读取本地文件": 1.8,
                },
                required_tools=["mcp__filesystem_readonly__read_text"],
                parameters={"path": "required", "max_chars": 3000},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Read file through filesystem MCP connector",
                        tool_name="mcp__filesystem_readonly__read_text",
                        tool_args={"max_chars": 3000},
                        use_tool_extract_args=True,
                    )
                ],
                final_response=(
                    "MCP filesystem read completed for {step1.data.path}. "
                    "Content excerpt: {step1.data.content}"
                ),
                permission_policy={"risk_level": "filesystem/read", "requires_confirmation": False},
                output_schema={"path": "string", "content": "string", "truncated": "boolean"},
            ),
            WorkflowDefinition(
                name="mcp_filesystem_search_plan",
                description="Search project file names through the read-only filesystem MCP connector and return a planning-oriented match list.",
                triggers={
                    "search project files": 2.0,
                    "find project files": 1.8,
                    "search local files": 1.8,
                    "inspect project directory": 1.6,
                    "mcp search files": 1.6,
                    "搜索项目文件": 2.0,
                    "查找项目文件": 1.8,
                    "检查项目目录": 1.6,
                },
                required_tools=["mcp__filesystem_readonly__search_names"],
                parameters={"query": "required", "path": "optional", "max_results": 20},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Search file names through filesystem MCP connector",
                        tool_name="mcp__filesystem_readonly__search_names",
                        tool_args={"max_results": 20},
                        use_tool_extract_args=True,
                    )
                ],
                final_response=(
                    "MCP filesystem search completed for query '{step1.data.query}'. "
                    "Matches: {step1.data.matches}"
                ),
                permission_policy={"risk_level": "filesystem/read", "requires_confirmation": False},
                output_schema={"query": "string", "matches": "array"},
            ),
            WorkflowDefinition(
                name="mcp_git_status_review",
                description="Inspect git working tree status through the read-only git MCP connector.",
                triggers={
                    "git status": 2.0,
                    "review git status": 2.0,
                    "working tree status": 1.7,
                    "repository status": 1.6,
                    "查看git状态": 2.0,
                    "查看仓库状态": 1.8,
                },
                required_tools=["mcp__git_readonly__status"],
                parameters={},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Inspect git working tree status",
                        tool_name="mcp__git_readonly__status",
                    )
                ],
                final_response="Git status:\n{step1.data.status}",
                permission_policy={"risk_level": "filesystem/read", "requires_confirmation": False},
                output_schema={"status": "string", "repo_root": "string"},
            ),
            WorkflowDefinition(
                name="mcp_git_recent_history",
                description="Inspect recent commits through the read-only git MCP connector.",
                triggers={
                    "git log": 2.0,
                    "recent commits": 2.0,
                    "commit history": 1.8,
                    "recent git history": 1.7,
                    "查看提交历史": 2.0,
                    "最近提交": 1.8,
                },
                required_tools=["mcp__git_readonly__log"],
                parameters={"limit": 5},
                steps=[
                    WorkflowStepTemplate(
                        step_id="step1",
                        description="Inspect recent git commits",
                        tool_name="mcp__git_readonly__log",
                        tool_args={"limit": 5},
                    )
                ],
                final_response="Recent commits:\n{step1.data.log}",
                permission_policy={"risk_level": "filesystem/read", "requires_confirmation": False},
                output_schema={"log": "string", "limit": "number", "repo_root": "string"},
            ),
        ]
    )
