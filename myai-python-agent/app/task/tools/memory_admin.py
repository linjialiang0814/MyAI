from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.memory.evaluation.governance_report import DEFAULT_FIXTURE, render_markdown, run_governance_report
from app.memory.embedding.factory import create_embedding_client
from app.memory.mem_service import MemoryService
from app.memory.model.slot_registry import (
    CONFIDENCE_CALIBRATION_POLICY,
    SLOT_DEFINITIONS,
    get_slot_definition,
)
from app.memory.settings import MemorySettingsStore, settings_schema
from app.task.tool.tool import Tool, ToolPolicy, ToolResult


MemoryAdminOperation = Literal[
    "maintenance",
    "eval_report",
    "policy_inspection",
    "settings_preview",
    "get_settings",
    "update_settings",
]


class MemoryAdminArgs(BaseModel):
    operation: MemoryAdminOperation = Field(description="Memory management workflow to run.")
    user_id: str | None = Field(default=None, description="Runtime user id for user-scoped workflows.")
    mem_type: str | None = Field(default=None, description="Optional memory type for policy inspection.")
    slot: str | None = Field(default=None, description="Optional memory slot for policy inspection.")
    report_format: Literal["summary", "markdown", "json"] = Field(
        default="summary",
        description="Report output format for eval_report.",
    )
    fixture_path: str | None = Field(default=None, description="Optional eval fixture path.")
    settings: dict[str, Any] | None = Field(default=None, description="Settings patch for update_settings.")


class MemoryAdminTool(Tool):
    name = "memory_admin"
    description = "Manage memory maintenance, governance eval reports, policy inspection, and persisted memory settings."
    args = MemoryAdminArgs
    policy = ToolPolicy(risk_level="sensitive", timeout_seconds=20.0)
    trigger_words = {
        "memory maintenance": 1.6,
        "memory admin": 1.5,
        "memory eval": 1.5,
        "memory report": 1.4,
        "memory policy": 1.4,
        "memory settings": 1.3,
        "update memory settings": 1.6,
        "记忆维护": 1.6,
        "记忆报告": 1.5,
        "记忆策略": 1.5,
        "记忆设置": 1.3,
    }

    def __init__(
        self,
        memory_service: MemoryService | None = None,
        settings_store: MemorySettingsStore | None = None,
    ) -> None:
        self.memory_service = memory_service or MemoryService(embedding_client=create_embedding_client())
        self.settings_store = settings_store or self.memory_service.settings_store

    def prepare_args(self, args: dict[str, Any] | None, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
        prepared = dict(args or {})
        if not prepared.get("user_id") and runtime_context and runtime_context.get("user_id"):
            prepared["user_id"] = runtime_context["user_id"]
        return prepared

    def policy_for_args(
        self,
        args: dict[str, Any] | None,
        runtime_context: dict[str, Any] | None = None,
    ) -> ToolPolicy:
        operation = (args or {}).get("operation")
        if operation in {"maintenance", "update_settings"}:
            return ToolPolicy(risk_level="sensitive", timeout_seconds=20.0, requires_confirmation=True)
        return self.policy

    def extract_args(self, content: str) -> dict[str, Any]:
        normalized = content.lower()
        operation: MemoryAdminOperation = "policy_inspection"
        if any(token in normalized or token in content for token in ["maintenance", "maintain", "维护", "整理"]):
            operation = "maintenance"
        elif any(token in normalized or token in content for token in ["eval", "report", "calibration", "评测", "报告"]):
            operation = "eval_report"
        elif any(token in normalized or token in content for token in ["update memory settings", "修改记忆设置", "更新记忆设置"]):
            operation = "update_settings"
        elif any(token in normalized or token in content for token in ["settings", "setting", "设置"]):
            operation = "get_settings"
        elif any(token in normalized or token in content for token in ["policy", "slot", "策略"]):
            operation = "policy_inspection"

        report_format = "markdown" if "markdown" in normalized else "summary"
        return {"operation": operation, "report_format": report_format}

    def run(
        self,
        *,
        operation: MemoryAdminOperation,
        user_id: str | None = None,
        mem_type: str | None = None,
        slot: str | None = None,
        report_format: str = "summary",
        fixture_path: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> ToolResult:
        if operation == "maintenance":
            if not user_id:
                return ToolResult(success=False, error="memory maintenance requires user_id")
            report = self.memory_service.maintenance(user_id)
            return ToolResult(
                success=True,
                data={
                    "operation": operation,
                    "user_id": user_id,
                    "report": report,
                    "summary": _maintenance_summary(report),
                },
            )
        if operation == "eval_report":
            path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE
            report = run_governance_report(path)
            if report_format == "markdown":
                data: Any = {"format": "markdown", "content": render_markdown(report), "summary": report["summary"]}
            elif report_format == "json":
                data = report
            else:
                data = {"format": "summary", "summary": report["summary"]}
            return ToolResult(success=True, data={"operation": operation, "report": data})
        if operation == "policy_inspection":
            return ToolResult(success=True, data=self._policy_inspection(mem_type=mem_type, slot=slot))
        if operation == "settings_preview":
            return ToolResult(success=True, data=_settings_preview(user_id=user_id, settings_store=self.settings_store))
        if operation == "get_settings":
            if not user_id:
                return ToolResult(success=False, error="get_settings requires user_id")
            return ToolResult(
                success=True,
                data={
                    "operation": operation,
                    "user_id": user_id,
                    "settings": self.settings_store.get(user_id).to_dict(),
                    "schema": settings_schema(),
                },
            )
        if operation == "update_settings":
            if not user_id:
                return ToolResult(success=False, error="update_settings requires user_id")
            updated = self.settings_store.update(user_id, settings or {})
            return ToolResult(
                success=True,
                data={
                    "operation": operation,
                    "user_id": user_id,
                    "settings": updated.to_dict(),
                    "schema": settings_schema(),
                },
            )
        return ToolResult(success=False, error=f"unsupported memory admin operation: {operation}")

    def _policy_inspection(self, *, mem_type: str | None, slot: str | None) -> dict[str, Any]:
        if mem_type or slot:
            definition = get_slot_definition(mem_type or "general", slot)
            slot_definitions = [asdict(definition)]
        else:
            slot_definitions = [asdict(definition) for definition in SLOT_DEFINITIONS]
        return {
            "operation": "policy_inspection",
            "slot_count": len(slot_definitions),
            "slots": slot_definitions,
            "confidence_calibration_policy": asdict(CONFIDENCE_CALIBRATION_POLICY),
            "supported_user_controls": [
                "retrieval_enabled",
                "pinned",
                "user_hidden",
                "user_locked",
                "is_current",
                "user_control_reason",
            ],
        }


def _maintenance_summary(report: dict[str, Any]) -> str:
    consolidation = report.get("consolidation", {})
    created_count = consolidation.get("created_count", 0)
    action_count = len(consolidation.get("actions", []))
    memory_count = report.get("memory_count", 0)
    return f"maintenance complete: summaries_created={created_count}, consolidation_actions={action_count}, memory_count={memory_count}"


def _settings_preview(
    *,
    user_id: str | None,
    settings_store: MemorySettingsStore,
) -> dict[str, Any]:
    payload = {
        "operation": "settings_preview",
        "status": "persisted",
        "schema": settings_schema(),
        "note": "Use get_settings to read persisted settings and update_settings to change them.",
    }
    if user_id:
        payload["user_id"] = user_id
        payload["settings"] = settings_store.get(user_id).to_dict()
    return payload
