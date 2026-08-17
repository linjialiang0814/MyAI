from collections import defaultdict
from typing import Dict

from app.task.config.task_config import TaskConfig
from app.task.stats.record import DecisionRecord
from app.task.tool.tool_registry import ToolRegistry

class StatsManager:
    def __init__(self,
                 registry: ToolRegistry,
                 config: TaskConfig):
        self.registry = registry
        self.config = config

        self.tool_calls = defaultdict(int)
        self.tool_success = defaultdict(int)
        self.tool_failure = defaultdict(int)
        self.tool_latency_ms = defaultdict(float)

        self.rule_hits = 0
        self.llm_hits = 0
        self.workflow_hits = 0
        self.failures = 0
        self.no_tool_hits = 0

    def record(self, decision: DecisionRecord):
        plan = decision.plan or {}
        result = decision.result or {}
        source = plan.get("source", "none")
        steps = plan.get("steps") or []
        tool_name = plan.get("tool_name")

        if source == "rule":
            self.rule_hits += 1
        elif source == "llm":
            self.llm_hits += 1
        elif source == "workflow":
            self.workflow_hits += 1
        else:
            self.no_tool_hits += 1

        if not decision.success:
            self.failures += 1

        if steps:
            step_results = decision.step_results or []
            for step in step_results:
                current_tool = step.get("tool_name")
                if not current_tool:
                    continue
                self.tool_calls[current_tool] += 1
                if step.get("result", {}).get("success"):
                    self.tool_success[current_tool] += 1
                else:
                    self.tool_failure[current_tool] += 1
                if step.get("latency_ms") is not None:
                    self.tool_latency_ms[current_tool] += float(step["latency_ms"])
        elif tool_name:
            self.tool_calls[tool_name] += 1
            if result.get("success"):
                self.tool_success[tool_name] += 1
            else:
                self.tool_failure[tool_name] += 1
            if decision.latency_ms is not None:
                self.tool_latency_ms[tool_name] += decision.latency_ms

        if self.config.update_trigger_weights:
            self._update_trigger_weights(decision)

    def _update_trigger_weights(self, decision: DecisionRecord) -> None:
        plan = decision.plan or {}
        tool_name = plan.get("tool_name")
        matched = plan.get("matched") or {}
        reward = decision.reward
        if not tool_name or reward is None or not matched:
            return

        tool = self.registry.get_tool(tool_name)
        if tool is None:
            return

        for keyword, weight in matched.items():
            new_weight = weight + self.config.reward_lr * reward
            new_weight = max(self.config.min_trigger_weight, min(self.config.max_trigger_weight, new_weight))
            tool.trigger_words[keyword] = round(new_weight, 4)

    def show_record(self):
        print(f"rule hits: {self.rule_hits}, llm hits: {self.llm_hits}, failures: {self.failures}")
        for tool_name, calls in self.tool_calls.items():
            print(f"{tool_name}: {self.tool_success[tool_name]}/{calls} ({self.tool_success[tool_name] / calls:.2%})")

    def success_rate(self, tool_name: str)->float:
        calls = self.tool_calls[tool_name]
        if calls == 0:
            return 1.0
        return self.tool_success[tool_name] / calls

    def avg_latency_ms(self, tool_name: str) -> float:
        calls = self.tool_calls[tool_name]
        if calls == 0:
            return 0.0
        return self.tool_latency_ms[tool_name] / calls

    @staticmethod
    def compute_reward(decision:DecisionRecord):
        plan = decision.plan or {}
        result = decision.result or {}
        if not result.get("success", False):
            return -1.0
        if plan.get("source") == "rule":
            return 1.0
        if plan.get("source") == "llm":
            return 0.5
        return 0.0

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        tools = {}
        for tool_name in self.registry.list_tools():
            name = tool_name.name
            tools[name] = {
                "calls": self.tool_calls[name],
                "success_rate": round(self.success_rate(name), 4),
                "avg_latency_ms": round(self.avg_latency_ms(name), 2),
            }
        return {
            "planner": {
                "rule_hits": self.rule_hits,
                "llm_hits": self.llm_hits,
                "workflow_hits": self.workflow_hits,
                "no_tool_hits": self.no_tool_hits,
                "failures": self.failures,
            },
            "tools": tools,
        }

#tool成功率低，降低rule的优先级
#tool成功率高，提升rule的权重
