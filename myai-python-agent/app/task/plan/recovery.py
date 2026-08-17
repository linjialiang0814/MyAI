from typing import List

from app.task.config.task_config import TaskConfig
from app.task.plan.validation import ToolValidation
from app.task.plan.planner import ToolPlan, ToolPlanner

#主要针对llm based rule的自修复

class RecoveryPlanner:
    def __init__(self,
                 planner: ToolPlanner,
                 validator: ToolValidation,
                 config: TaskConfig):
        self.planner = planner
        self.validator = validator
        self.config = config

    def plan(self, content: str, short_context: List[str] | None = None) -> ToolPlan:
        context_messages: List[str] = list(short_context or [])
        last_plan = ToolPlan(need_tool=False)

        for attempt in range(self.config.max_retries + 1):
            plan = self.planner.plan(content, context_messages)
            last_plan = plan
            validation = self.validator.validate_plan(plan)

            if validation.valid:
                return plan

            recovery_msg = self.validator.build_recovery_prompt(
                error_type=validation.error_type,
                message=validation.message,
                last_plan=plan
            )
            context_messages.append(recovery_msg)

        return ToolPlan(need_tool=False, rationale=f"Fallback after invalid plan: {last_plan.to_dict()}")

    def list_workflows(self) -> list[dict]:
        if hasattr(self.planner, "list_workflows"):
            return self.planner.list_workflows()
        return []


