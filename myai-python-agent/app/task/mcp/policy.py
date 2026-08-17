from __future__ import annotations

from typing import Any

from app.task.mcp.models import MCPServerConfig, MCPToolDescriptor


SAFE_RISKS = {"safe", "read-only", "readonly", "local/read", "filesystem/read"}
CONFIRMATION_RISKS = {
    "network",
    "filesystem/write",
    "browser/session",
    "account/action",
    "sensitive",
    "destructive",
    "unknown",
}
BLOCKED_IN_HOSTED_RISKS = {"filesystem/write", "browser/session", "destructive"}


def map_mcp_tool_policy(descriptor: MCPToolDescriptor, server: MCPServerConfig | None = None) -> dict[str, Any]:
    annotations = dict(descriptor.annotations or {})
    raw_risk = _first_non_empty(
        annotations.get("risk_level"),
        annotations.get("riskLevel"),
        annotations.get("risk"),
        descriptor.risk_level,
        server.risk_level if server else None,
        "unknown",
    )
    risk_level = _normalize_risk(str(raw_risk), annotations)
    destructive = _as_bool(annotations.get("destructiveHint"), default=False) or _as_bool(
        annotations.get("destructive"), default=False
    )
    read_only = _as_bool(annotations.get("readOnlyHint"), default=False) or _as_bool(
        annotations.get("read_only"), default=False
    )
    open_world = _as_bool(annotations.get("openWorldHint"), default=False) or _as_bool(
        annotations.get("network"), default=False
    )

    if destructive:
        risk_level = "destructive"
    elif read_only and risk_level in {"unknown", "safe"}:
        risk_level = "filesystem/read"
    elif open_world and risk_level in {"unknown", "safe"}:
        risk_level = "network"

    requires_confirmation = (
        descriptor.requires_confirmation
        or (server.requires_confirmation if server else False)
        or _as_bool(annotations.get("requires_confirmation"), default=False)
        or _as_bool(annotations.get("requiresConfirmation"), default=False)
        or risk_level in CONFIRMATION_RISKS
    )
    allowed_in_hosted = descriptor.allowed_in_hosted and risk_level not in BLOCKED_IN_HOSTED_RISKS
    timeout_seconds = _as_float(annotations.get("timeout_seconds") or annotations.get("timeoutSeconds"), descriptor.timeout_seconds)
    retry_count = _as_int(annotations.get("retry_count") or annotations.get("retryCount"), descriptor.retry_count)
    if risk_level in {"sensitive", "destructive", "account/action", "filesystem/write"}:
        retry_count = 0

    return {
        "risk_level": risk_level,
        "timeout_seconds": timeout_seconds,
        "retry_count": max(0, retry_count),
        "requires_confirmation": requires_confirmation,
        "allowed_in_local": descriptor.allowed_in_local,
        "allowed_in_hosted": allowed_in_hosted,
        "policy_source": "mcp_metadata",
        "policy_reason": _policy_reason(risk_level, annotations, requires_confirmation),
    }


def _normalize_risk(value: str, annotations: dict[str, Any]) -> str:
    normalized = value.strip().lower().replace("_", "/").replace("-", "/")
    capabilities = [str(item).lower() for item in _as_list(annotations.get("capabilities") or annotations.get("categories"))]
    if normalized in {"", "none"}:
        normalized = "unknown"
    if normalized in {"read", "readonly", "read/only", "file/read", "filesystem/read"}:
        return "filesystem/read"
    if normalized in {"write", "file/write", "filesystem/write"}:
        return "filesystem/write"
    if normalized in {"account", "action", "account/action"}:
        return "account/action"
    if normalized in {"browser", "browser/session"}:
        return "browser/session"
    if normalized in {"net", "network", "open/world"}:
        return "network"
    if normalized in {"secret", "sensitive"}:
        return "sensitive"
    if normalized in {"destroy", "destructive", "delete"}:
        return "destructive"
    if normalized in SAFE_RISKS:
        return "safe" if normalized == "safe" else normalized
    if "filesystem.write" in capabilities or "file_write" in capabilities or "write" in capabilities:
        return "filesystem/write"
    if "filesystem.read" in capabilities or "file_read" in capabilities:
        return "filesystem/read"
    if "browser" in capabilities:
        return "browser/session"
    if "network" in capabilities:
        return "network"
    if "account" in capabilities or "action" in capabilities:
        return "account/action"
    return "unknown"


def _policy_reason(risk_level: str, annotations: dict[str, Any], requires_confirmation: bool) -> str:
    source = "metadata"
    if annotations.get("destructiveHint") or annotations.get("destructive"):
        source = "destructive hint"
    elif annotations.get("readOnlyHint") or annotations.get("read_only"):
        source = "read-only hint"
    elif annotations.get("openWorldHint") or annotations.get("network"):
        source = "open-world/network hint"
    confirmation = "requires confirmation" if requires_confirmation else "no confirmation required"
    return f"{risk_level} from {source}; {confirmation}"


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _as_float(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int) -> int:
    try:
        if value in (None, ""):
            return int(default)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
