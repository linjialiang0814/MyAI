from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPServerConfig:
    server_id: str
    name: str
    enabled: bool = True
    description: str = ""
    risk_level: str = "safe"
    requires_confirmation: bool = False


@dataclass(frozen=True)
class MCPToolDescriptor:
    server_id: str
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "safe"
    timeout_seconds: float = 10.0
    retry_count: int = 0
    requires_confirmation: bool = False
    allowed_in_local: bool = True
    allowed_in_hosted: bool = True
    annotations: dict[str, Any] = field(default_factory=dict)
    policy_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def registry_name(self) -> str:
        safe_server = _safe_name(self.server_id)
        safe_tool = _safe_name(self.name)
        return f"mcp__{safe_server}__{safe_tool}"

    def to_policy_dict(self) -> dict[str, Any]:
        if self.policy_metadata:
            return {
                "risk_level": self.policy_metadata.get("risk_level", self.risk_level),
                "timeout_seconds": self.policy_metadata.get("timeout_seconds", self.timeout_seconds),
                "retry_count": self.policy_metadata.get("retry_count", self.retry_count),
                "requires_confirmation": self.policy_metadata.get("requires_confirmation", self.requires_confirmation),
                "allowed_in_local": self.policy_metadata.get("allowed_in_local", self.allowed_in_local),
                "allowed_in_hosted": self.policy_metadata.get("allowed_in_hosted", self.allowed_in_hosted),
            }
        return {
            "risk_level": self.risk_level,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "requires_confirmation": self.requires_confirmation,
            "allowed_in_local": self.allowed_in_local,
            "allowed_in_hosted": self.allowed_in_hosted,
        }


def _safe_name(value: str) -> str:
    cleaned = []
    for char in value.strip().lower():
        if char.isalnum() or char == "_":
            cleaned.append(char)
        elif char in {"-", ".", " "}:
            cleaned.append("_")
    name = "".join(cleaned).strip("_")
    return name or "tool"
