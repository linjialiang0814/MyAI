from __future__ import annotations

from datetime import datetime, timezone
import re
import time
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, create_model

from app.runtime.error_model import classify_exception
from app.task.mcp.models import MCPToolDescriptor
from app.task.tool.tool import Tool, ToolPolicy, ToolResult


class MCPClient(Protocol):
    def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        ...


class MCPToolAdapter(Tool):
    def __init__(self, descriptor: MCPToolDescriptor, client: MCPClient) -> None:
        self.descriptor = descriptor
        self.client = client
        self.name = descriptor.registry_name
        self.description = descriptor.description
        self.args = _model_from_json_schema(self.name, descriptor.input_schema)
        self.policy = ToolPolicy(**descriptor.to_policy_dict())

    @property
    def schema(self) -> dict[str, Any]:
        parameters = dict(self.descriptor.input_schema or {})
        parameters.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }

    def validate_args(self, args: dict[str, Any] | None) -> BaseModel:
        return self.args.model_validate(args or {})

    def extract_args(self, content: str) -> dict[str, Any]:
        if self.descriptor.server_id != "filesystem-readonly":
            return {}
        normalized = content.strip()
        if self.descriptor.name == "read_text":
            path = _extract_path(normalized)
            return {"path": path} if path else {}
        if self.descriptor.name == "list_files":
            path = _extract_path(normalized)
            return {"path": path or "."}
        if self.descriptor.name == "search_names":
            query = _extract_query(normalized)
            args: dict[str, Any] = {"query": query} if query else {}
            path = _extract_path(normalized)
            if path:
                args["path"] = path
            return args
        return {}

    def run(self, **kwargs) -> ToolResult:
        started_at = _utc_now()
        start = time.perf_counter()
        try:
            payload = self.client.call_tool(self.descriptor.server_id, self.descriptor.name, dict(kwargs))
        except Exception as exc:
            error_info = classify_exception(
                exc,
                operation=f"tool.{self.name}",
                dependency=self.descriptor.server_id,
            )
            return ToolResult(
                success=False,
                error=error_info.message,
                metadata={
                    **self._mcp_metadata(started_at=started_at, start=start, status="failed"),
                    "error_category": "mcp_call_exception",
                    "error_info": error_info.to_dict(),
                },
            )
        success = bool(payload.get("success", True))
        metadata = {
            **self._mcp_metadata(started_at=started_at, start=start, status="completed" if success else "failed"),
            **dict(payload.get("metadata") or {}),
        }
        if not success:
            return ToolResult(success=False, error=str(payload.get("error") or "MCP tool execution failed"), metadata=metadata)
        return ToolResult(success=True, data=payload.get("data"), metadata=metadata)

    def _mcp_metadata(self, *, started_at: str, start: float, status: str) -> dict[str, Any]:
        return {
            "tool_source": "mcp",
            "mcp_server_id": self.descriptor.server_id,
            "mcp_tool_name": self.descriptor.name,
            "mcp_registry_name": self.name,
            "mcp_call_status": status,
            "mcp_call_started_at": started_at,
            "mcp_call_finished_at": _utc_now(),
            "mcp_call_latency_ms": round((time.perf_counter() - start) * 1000.0, 3),
        }


def _model_from_json_schema(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    properties = dict((schema or {}).get("properties") or {})
    required = set((schema or {}).get("required") or [])
    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, field_schema in properties.items():
        annotation = _python_type(field_schema)
        default = ... if field_name in required else field_schema.get("default", None)
        fields[field_name] = (annotation, default)
    return create_model(
        f"{_pascal_name(name)}Args",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def _python_type(field_schema: dict[str, Any]) -> Any:
    json_type = field_schema.get("type")
    if isinstance(json_type, list):
        non_null = [item for item in json_type if item != "null"]
        json_type = non_null[0] if non_null else "string"
    if json_type == "string":
        return str
    if json_type == "integer":
        return int
    if json_type == "number":
        return float
    if json_type == "boolean":
        return bool
    if json_type == "array":
        return list
    if json_type == "object":
        return dict
    return Any


def _pascal_name(value: str) -> str:
    parts = [part for part in value.replace("-", "_").split("_") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "MCPTool"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_path(content: str) -> str | None:
    quoted = re.search(r"['\"]([^'\"]+\.[A-Za-z0-9]{1,12})['\"]", content)
    if quoted:
        return quoted.group(1).strip()
    path_match = re.search(r"([A-Za-z0-9_\-./\\]+\.[A-Za-z0-9]{1,12})", content)
    if path_match:
        return path_match.group(1).strip().strip(".,;:")
    dir_match = re.search(r"(?:under|in|from|目录|文件夹)\s+([A-Za-z0-9_\-./\\]+)", content, re.IGNORECASE)
    if dir_match:
        return dir_match.group(1).strip().strip(".,;:")
    return None


def _extract_query(content: str) -> str | None:
    quoted = re.search(r"['\"]([^'\"]+)['\"]", content)
    if quoted:
        return quoted.group(1).strip()
    patterns = [
        r"(?:search|find|lookup)\s+([A-Za-z0-9_\-.]+)",
        r"(?:搜索|查找)\s*([A-Za-z0-9_\-.\u4e00-\u9fff]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip().strip(".,;:")
    return None
