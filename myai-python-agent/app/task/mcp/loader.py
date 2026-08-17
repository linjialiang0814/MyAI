from __future__ import annotations

from typing import Protocol

from app.task.mcp.adapter import MCPClient, MCPToolAdapter
from app.task.mcp.models import MCPServerConfig, MCPToolDescriptor
from app.task.mcp.policy import map_mcp_tool_policy
from app.task.tool.tool_registry import ToolRegistry


class MCPDiscoveryClient(MCPClient, Protocol):
    def list_tools(self, server_id: str | None = None) -> list[MCPToolDescriptor]:
        ...


class MCPToolRegistryLoader:
    def __init__(self, servers: list[MCPServerConfig], client: MCPDiscoveryClient) -> None:
        self.servers = servers
        self.client = client

    def load_tools(self) -> list[MCPToolAdapter]:
        tools: list[MCPToolAdapter] = []
        for server in self.servers:
            if not server.enabled:
                continue
            for descriptor in self.client.list_tools(server.server_id):
                tools.append(MCPToolAdapter(_apply_server_defaults(descriptor, server), self.client))
        return tools

    def register_into(self, registry: ToolRegistry) -> list[MCPToolAdapter]:
        tools = self.load_tools()
        registry.register_many(tools)
        return tools


def _apply_server_defaults(descriptor: MCPToolDescriptor, server: MCPServerConfig) -> MCPToolDescriptor:
    policy = map_mcp_tool_policy(descriptor, server)
    return MCPToolDescriptor(
        server_id=descriptor.server_id,
        name=descriptor.name,
        description=descriptor.description,
        input_schema=descriptor.input_schema,
        risk_level=policy["risk_level"],
        timeout_seconds=policy["timeout_seconds"],
        retry_count=policy["retry_count"],
        requires_confirmation=policy["requires_confirmation"],
        allowed_in_local=policy["allowed_in_local"],
        allowed_in_hosted=policy["allowed_in_hosted"],
        annotations=descriptor.annotations,
        policy_metadata=policy,
    )
