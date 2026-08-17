from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.model.base import BaseLLM
from app.runtime.error_model import classify_exception
from app.task.config.task_config import TaskConfig
from app.task.stats.statistics import StatsManager
from app.task.tool.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ToolStep:
    step_id: str
    description: str
    tool_name: str
    tool_args: Dict[str, Any] = field(default_factory=dict)
    output_key: Optional[str] = None
    extract_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolPlan:
    need_tool: bool
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    steps: List[ToolStep] = field(default_factory=list)
    final_response: Optional[str] = None
    source: str = "none"
    score: Optional[float] = None
    matched: Dict[str, float] = field(default_factory=dict)
    rationale: Optional[str] = None
    memory_context: Dict[str, Any] = field(default_factory=dict)
    workflow: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "need_tool": self.need_tool,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "steps": [step.to_dict() for step in self.steps],
            "final_response": self.final_response,
            "source": self.source,
            "score": self.score,
            "matched": self.matched,
            "rationale": self.rationale,
            "memory_context": self.memory_context,
            "workflow": self.workflow,
        }

    def normalized_steps(self) -> List[ToolStep]:
        if self.steps:
            return self.steps
        if self.need_tool and self.tool_name:
            return [
                ToolStep(
                    step_id="step1",
                    description=f"Execute {self.tool_name}",
                    tool_name=self.tool_name,
                    tool_args=self.tool_args,
                )
            ]
        return []


class ToolPlanner:
    def __init__(
        self,
        registry: ToolRegistry,
        stats: StatsManager,
        config: TaskConfig,
        client: BaseLLM | None = None,
        workflow_registry: Any | None = None,
    ) -> None:
        self.registry = registry
        self.stats = stats
        self.config = config
        self.client = client
        self.workflow_registry = workflow_registry

    def plan(self, content: str, short_context: List[str] | None = None) -> ToolPlan:
        short_context = short_context or []
        content = content.strip()

        if self.workflow_registry:
            workflow_plan = self.workflow_registry.match(content, self.registry)
            if workflow_plan:
                return workflow_plan

        multi_step_plan = self.multi_step_rule_plan(content)
        if multi_step_plan:
            return multi_step_plan

        rule_plan = self.rule_based_plan(content)
        if rule_plan:
            return rule_plan

        if self.config.allow_llm_fallback and self.client:
            llm_plan = self.llm_based_plan(content, short_context)
            if llm_plan:
                return llm_plan

        return ToolPlan(need_tool=False, source="none", rationale="No tool needed.")

    def list_workflows(self) -> list[dict[str, Any]]:
        if not self.workflow_registry:
            return []
        return self.workflow_registry.list_workflows()

    def rule_based_plan(self, content: str) -> Optional[ToolPlan]:
        match = self.match_by_trigger(content)
        if not match:
            return None

        tool = match["tool"]
        score = match["score"]
        matched = match["matched"]

        success_rate = self.stats.success_rate(tool.name)
        if success_rate < self.config.min_success_rate:
            logger.info(
                "Tool %s success rate %.2f%% is below threshold %.2f%%, skip rule plan.",
                tool.name,
                success_rate * 100,
                self.config.min_success_rate * 100,
            )
            return None

        extracted_args = tool.extract_args(content)

        return ToolPlan(
            need_tool=True,
            tool_name=tool.name,
            tool_args=extracted_args,
            source="rule",
            score=score,
            matched=matched,
            rationale=f"Trigger word matched: {matched}",
        )

    def multi_step_rule_plan(self, content: str) -> Optional[ToolPlan]:
        normalized = content.lower()

        has_time_intent = any(
            token in normalized or token in content
            for token in ["time", "now", "几点", "时间", "当前时间"]
        )
        has_math_intent = any(
            token in normalized or token in content
            for token in ["calculate", "compute", "剩", "还有多久", "difference", "距离"]
        )
        mentions_eight = any(
            token in normalized or token in content
            for token in ["8 pm", "8pm", "20:00", "8点", "晚上8点", "晚8点"]
        )

        if has_time_intent and has_math_intent and mentions_eight:
            timezone_args = self._datetime_args_from_content(content)
            return ToolPlan(
                need_tool=True,
                steps=[
                    ToolStep(
                        step_id="step1",
                        description="Get the current local time",
                        tool_name="datetime_info",
                        tool_args=timezone_args,
                        output_key="current_hour",
                        extract_path="data.local_hour",
                    ),
                    ToolStep(
                        step_id="step2",
                        description="Calculate remaining hours until 20:00",
                        tool_name="calculator",
                        tool_args={"expression": "20 - {current_hour}"},
                        output_key="remaining_hours",
                        extract_path="data.value",
                    ),
                ],
                final_response="The current local hour is {current_hour}. There are about {remaining_hours} hours remaining until 20:00.",
                source="rule",
                score=2.0,
                matched={"datetime_info": 1.0, "calculator": 1.0},
                rationale="Detected a chained request: get time first, then calculate the remaining hours.",
            )

        has_text_stats = any(
            token in normalized or token in content
            for token in ["统计", "word count", "字数", "字符数", "text", "text stats"]
        )
        has_reading_time = any(
            token in normalized or token in content
            for token in ["阅读时间", "reading time", "read time", "需要多久读完"]
        )
        if has_text_stats and has_reading_time:
            text_content = self._extract_text_payload(content)
            if text_content:
                return ToolPlan(
                    need_tool=True,
                    steps=[
                        ToolStep(
                            step_id="step1",
                            description="Calculate text statistics",
                            tool_name="text_stats",
                            tool_args={"text": text_content},
                            output_key="word_count",
                            extract_path="data.word_count",
                        ),
                        ToolStep(
                            step_id="step2",
                            description="Estimate reading time in minutes at 200 words per minute",
                            tool_name="calculator",
                            tool_args={"expression": "{word_count} / 200"},
                            output_key="reading_minutes",
                            extract_path="data.value",
                        ),
                    ],
                    final_response="The text contains about {word_count} words, and the estimated reading time is {reading_minutes} minutes.",
                    source="rule",
                    score=2.0,
                    matched={"text_stats": 1.0, "calculator": 1.0},
                    rationale="Detected a chained request: collect text statistics first, then estimate reading time.",
                )

        has_system_info = any(
            token in normalized or token in content
            for token in ["system", "system info", "系统", "系统信息", "内存", "cpu"]
        )
        has_summary = any(
            token in normalized or token in content
            for token in ["summarize", "summary", "总结", "概括", "简要说明"]
        )
        if has_system_info and has_summary:
            return ToolPlan(
                need_tool=True,
                steps=[
                    ToolStep(
                        step_id="step1",
                        description="Get current system information",
                        tool_name="system_info",
                        tool_args={},
                        output_key="system_snapshot",
                    )
                ],
                final_response=(
                    "System summary: OS={step1.data.os}, CPU cores={step1.data.cpu_count}, "
                    "CPU usage={step1.data.cpu_percent}%, memory used={step1.data.memory_used_gb}GB "
                    "of {step1.data.memory_total_gb}GB."
                ),
                source="rule",
                score=1.5,
                matched={"system_info": 1.0},
                rationale="Detected a request to inspect system information and summarize it.",
            )

        return None

    def match_by_trigger(self, content: str) -> Dict[str, Any] | None:
        normalized = content.lower().strip()
        best_tool = None
        best_score = 0.0
        best_hits: Dict[str, float] = {}

        for tool in self.registry.list_tools():
            score = 0.0
            hits: Dict[str, float] = {}

            for keyword, weight in tool.trigger_words.items():
                if self.contain_keyword(normalized, keyword.lower()):
                    score += weight
                    hits[keyword] = weight

            for keyword, penalty in getattr(tool, "negative_triggers", {}).items():
                if self.contain_keyword(normalized, keyword.lower()):
                    score -= penalty

            if score > best_score and hits:
                best_score = score
                best_tool = tool
                best_hits = hits

        if best_tool and best_score >= self.config.trigger_threshold:
            return {
                "tool": best_tool,
                "score": best_score,
                "matched": best_hits,
            }

        return None

    @staticmethod
    def contain_keyword(content: str, keyword: str) -> bool:
        if not keyword:
            return False
        if re.search(r"[\u4e00-\u9fff]", keyword):
            return keyword in content
        pattern = rf"(?<![a-zA-Z0-9_]){re.escape(keyword)}(?![a-zA-Z0-9_])"
        return re.search(pattern, content) is not None

    def llm_based_plan(self, content: str, short_context: List[str]) -> ToolPlan | None:
        if not self.client:
            return ToolPlan(need_tool=False)

        prompt = self.build_planning_prompt(content, short_context)
        try:
            response = self.client.generate(prompt)
        except Exception as exc:
            error_info = classify_exception(
                exc,
                operation="task.plan.generate",
                dependency="task_llm",
            )
            logger.warning(
                "LLM planning failed error_type=%s error_code=%s",
                type(exc).__name__,
                error_info.code.value,
            )
            return ToolPlan(need_tool=False)

        parsed_data = self.parse_json(response)
        if not parsed_data:
            logger.warning(
                "Could not parse LLM planning output response_chars=%s",
                len(str(response or "")),
            )
            return ToolPlan(need_tool=False)

        steps = [
            ToolStep(
                step_id=str(item.get("step_id", f"step{index + 1}")),
                description=str(item.get("description", f"Step {index + 1}")),
                tool_name=str(item.get("tool_name", "")),
                tool_args=item.get("tool_args", {}) or {},
                output_key=item.get("output_key"),
                extract_path=item.get("extract_path"),
            )
            for index, item in enumerate(parsed_data.get("steps", []))
            if isinstance(item, dict)
        ]
        need_tool = parsed_data.get("need_tool", False)
        if steps:
            need_tool = True
        tool_name = parsed_data.get("tool_name")
        if isinstance(tool_name, str):
            tool_name = tool_name.strip() or None

        return ToolPlan(
            need_tool=need_tool,
            tool_name=tool_name,
            tool_args=parsed_data.get("tool_args", {}),
            steps=steps,
            final_response=parsed_data.get("final_response"),
            source="llm",
            rationale=parsed_data.get("rationale"),
        )

    def build_planning_prompt(self, content: str, short_context: List[str]) -> str:
        tool_schema = self.registry.get_all_schemas()
        return f"""
            User_input: "{content}"
            Short_context: "{short_context}"
            Available Tools (JSON): {json.dumps(tool_schema, ensure_ascii=False, indent=2)}
            INSTRUCTIONS:
            1. Analyze if the user's intent requires a tool.
            2. If the task is simple, return a single tool_name/tool_args plan.
            3. If the task requires multiple tools, return a steps array in execution order.
            4. Step arguments may reference previous outputs using placeholders like {{current_hour}} or {{step1.data.value}}.
            5. If a step needs to expose a value for later use, set output_key and extract_path.
            6. If NO tool is needed, return need_tool=false.
            OUTPUT FORMAT (Pure JSON only, no markdown):
            {{
                "need_tool": true,
                "tool_name": "exact_tool_name",
                "tool_args": {{ "arg_name": "value" }},
                "steps": [
                    {{
                        "step_id": "step1",
                        "description": "short description",
                        "tool_name": "exact_tool_name",
                        "tool_args": {{"arg_name": "value"}},
                        "output_key": "variable_name",
                        "extract_path": "data.value"
                    }}
                ],
                "final_response": "Optional summary template with placeholders like {{variable_name}}",
                "rationale": "brief reason"
            }}
        """.strip()

    def _datetime_args_from_content(self, content: str) -> Dict[str, Any]:
        tool = self.registry.get_tool("datetime_info")
        if tool is None:
            return {"timezone_name": "Asia/Shanghai"}
        return tool.extract_args(content)

    @staticmethod
    def _extract_text_payload(content: str) -> str:
        if ":" in content:
            suffix = content.split(":", 1)[1].strip()
            if suffix:
                return suffix
        if "：" in content:
            suffix = content.split("：", 1)[1].strip()
            if suffix:
                return suffix
        return content.strip()

    @staticmethod
    def parse_json(text: str) -> Optional[dict]:
        text = text.strip()
        for candidate in (text, *ToolPlanner.extract_candidates(text)):
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    @staticmethod
    def extract_candidates(text: str) -> List[str]:
        candidates: List[str] = []
        fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        candidates.extend(chunk.strip() for chunk in fenced if chunk.strip())

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            candidates.append(match.group(0).strip())
        return candidates

    @staticmethod
    def rule_based_plan_v0(content: str) -> Optional[ToolPlan]:
        if "weather" in content.lower():
            return ToolPlan(need_tool=True, tool_name="weather")
        if "system" in content.lower():
            return ToolPlan(need_tool=True, tool_name="system_info")
        return None
