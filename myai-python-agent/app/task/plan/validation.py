from dataclasses import dataclass
from enum import Enum
from typing import Optional
from pydantic import ValidationError

from app.task.plan.planner import ToolPlan
from app.task.tool.tool_registry import ToolRegistry


class ErrorType(Enum):
    INVALID_TOOL = "Invalid_Tool"
    MISSING_ARG = "Missing_Arg"
    NOT_NEEDED = "Not_Needed"
    INCONSISTENT = "Inconsistent"
    EXECUTION_FAILED = "Execution_Failed"

@dataclass
class ValidationResult:
    valid: bool
    error_type: Optional[ErrorType] = None
    message: Optional[str] = None

class ToolValidation:
    def __init__(self,
                 tool_registry: ToolRegistry):
        self.tool_registry = tool_registry

    def validate_plan(self, plan: ToolPlan) -> ValidationResult:
        steps = plan.normalized_steps()
        if not plan.need_tool:
            if plan.tool_name is not None or steps:
                return ValidationResult(False, ErrorType.INCONSISTENT, "need_tool is false but tool content is set")
            return ValidationResult(True)

        if not steps:
            return ValidationResult(False, ErrorType.INCONSISTENT, "need_tool is true but no executable steps were produced")

        for step in steps:
            if not step.tool_name:
                return ValidationResult(False, ErrorType.INCONSISTENT, f"step '{step.step_id}' has empty tool_name")

            tool = self.tool_registry.get_tool(step.tool_name)
            if tool is None:
                return ValidationResult(False, ErrorType.INVALID_TOOL, f"tool '{step.tool_name}' not found")

            try:
                validated = tool.validate_args(step.tool_args)
            except ValidationError as exc:
                errors = exc.errors()
                message = "; ".join(
                    f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in errors
                )
                return ValidationResult(False, ErrorType.MISSING_ARG, f"{step.step_id}: {message}")

            step.tool_args = validated.model_dump()

        if not plan.steps and steps and len(steps) == 1:
            plan.tool_name = steps[0].tool_name
            plan.tool_args = steps[0].tool_args
        return ValidationResult(True)

    @staticmethod
    def build_recovery_prompt(
            error_type: ErrorType,
            message: str,
            last_plan: ToolPlan
    )->str:
        return (f"""
            Previous plan: {last_plan.to_dict()} was invalid.
            Error type: {error_type}
            Error message: {message}
            Please fix the JSON plan, correct your reasoning and generate a new plan.
            """)
