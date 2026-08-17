import ast
import operator as op
from typing import Any
from pydantic import BaseModel, Field
from app.task.tool.tool import Tool, ToolResult


_ALLOWED_OPERATORS: dict[type, Any] = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.FloorDiv: op.floordiv,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


class CalculatorArgs(BaseModel):
    expression: str = Field(..., description="Arithmetic expression to evaluate")


class CalculatorTool(Tool):
    name = "calculator"
    description = "Safely evaluate a basic arithmetic expression."
    args = CalculatorArgs
    trigger_words = {
        "calculate": 1.0,
        "calculator": 1.0,
        "compute": 1.0,
        "math": 0.8,
        "算": 1.0,
        "计算": 1.2,
        "表达式": 0.8,
    }
    negative_triggers = {"weather": 1.0, "天气": 1.0}

    def extract_args(self, content: str):
        import re

        candidates = re.findall(r"[0-9\s\+\-\*\/\%\(\)\.]{3,}", content)
        expression = max((c.strip() for c in candidates if any(ch.isdigit() for ch in c)), key=len, default=content.strip())
        return {"expression": expression}

    def run(self, **kwargs):
        expression = kwargs["expression"]
        try:
            value = self._safe_eval(expression)
            return ToolResult(success=True, data={"expression": expression, "value": value})
        except Exception as exc:
            return ToolResult(success=False, error=f"Invalid expression: {exc}")

    def _safe_eval(self, expression: str) -> Any:
        node = ast.parse(expression, mode="eval")
        return self._eval_node(node.body)

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](self._eval_node(node.left), self._eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](self._eval_node(node.operand))
        raise ValueError(f"Unsupported syntax: {ast.dump(node)}")
