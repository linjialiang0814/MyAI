from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.task.mcp.models import MCPToolDescriptor


class MockMCPClient:
    def __init__(self, descriptors: list[MCPToolDescriptor] | None = None) -> None:
        self._descriptors = descriptors or []
        self._handlers: dict[tuple[str, str], Callable[[dict[str, Any]], Any]] = {}
        self.calls: list[dict[str, Any]] = []

    def list_tools(self, server_id: str | None = None) -> list[MCPToolDescriptor]:
        if server_id is None:
            return list(self._descriptors)
        return [descriptor for descriptor in self._descriptors if descriptor.server_id == server_id]

    def register_handler(
        self,
        server_id: str,
        tool_name: str,
        handler: Callable[[dict[str, Any]], Any],
    ) -> None:
        self._handlers[(server_id, tool_name)] = handler

    def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"server_id": server_id, "tool_name": tool_name, "arguments": dict(arguments)})
        handler = self._handlers.get((server_id, tool_name))
        if handler is None:
            return {
                "success": False,
                "error": f"Mock MCP handler not found for {server_id}/{tool_name}",
                "metadata": {"error_category": "missing_handler"},
            }
        try:
            data = handler(dict(arguments))
            if isinstance(data, dict) and "success" in data:
                return data
            return {"success": True, "data": data, "metadata": {"mock": True}}
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "metadata": {"mock": True, "error_category": "handler_exception"},
            }
