from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.task.mcp.models import MCPToolDescriptor


class GitReadOnlyMCPClient:
    server_id = "git-readonly"

    def __init__(self, repo_root: Path | str | None = None) -> None:
        self.repo_root = Path(repo_root or os.getenv("MYAI_MCP_GIT_ROOT", "") or _default_repo_root()).resolve()
        self.git_bin = os.getenv("MYAI_MCP_GIT_BIN", "git")

    @classmethod
    def from_env(cls) -> "GitReadOnlyMCPClient":
        return cls()

    def list_tools(self, server_id: str | None = None) -> list[MCPToolDescriptor]:
        if server_id not in (None, self.server_id):
            return []
        return [
            MCPToolDescriptor(
                server_id=self.server_id,
                name="status",
                description="Inspect read-only git working tree status.",
                input_schema={"type": "object", "properties": {}, "required": []},
                risk_level="filesystem/read",
                timeout_seconds=3.0,
                allowed_in_hosted=False,
                annotations={"readOnlyHint": True, "capabilities": ["filesystem.read", "git.read"]},
            ),
            MCPToolDescriptor(
                server_id=self.server_id,
                name="log",
                description="Inspect recent git commits.",
                input_schema={
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "default": 5}},
                    "required": [],
                },
                risk_level="filesystem/read",
                timeout_seconds=3.0,
                allowed_in_hosted=False,
                annotations={"readOnlyHint": True, "capabilities": ["filesystem.read", "git.read"]},
            ),
            MCPToolDescriptor(
                server_id=self.server_id,
                name="show",
                description="Inspect a git revision without modifying the repository.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "rev": {"type": "string", "default": "HEAD"},
                        "max_chars": {"type": "integer", "default": 12000},
                    },
                    "required": [],
                },
                risk_level="filesystem/read",
                timeout_seconds=5.0,
                allowed_in_hosted=False,
                annotations={"readOnlyHint": True, "capabilities": ["filesystem.read", "git.read"]},
            ),
        ]

    def inspect_connector(self) -> dict[str, Any]:
        git_available = shutil.which(self.git_bin) is not None
        is_repo = (self.repo_root / ".git").exists()
        health = git_available and is_repo
        return {
            "server_id": self.server_id,
            "name": "Git Read-Only",
            "description": "Read-only local git connector for repository inspection.",
            "enabled": True,
            "health": {
                "ok": health,
                "message": "Git repository is readable." if health else "Git executable or repository metadata is unavailable.",
            },
            "settings": {
                "repo_root": str(self.repo_root),
                "git_bin": self.git_bin,
                "env": {
                    "enabled": "MYAI_MCP_GIT_ENABLED",
                    "repo_root": "MYAI_MCP_GIT_ROOT",
                    "git_bin": "MYAI_MCP_GIT_BIN",
                },
            },
            "risk_summary": {
                "risk_level": "filesystem/read",
                "requires_confirmation": False,
                "allowed_in_local": True,
                "allowed_in_hosted": False,
            },
        }

    def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if server_id != self.server_id:
            return self._failure(f"Unknown git MCP server: {server_id}", "unknown_server")
        try:
            if tool_name == "status":
                return self._success({"repo_root": str(self.repo_root), "status": self._git(["status", "--short", "--branch"])})
            if tool_name == "log":
                limit = _bounded_int(arguments.get("limit"), default=5, minimum=1, maximum=50)
                return self._success({"repo_root": str(self.repo_root), "limit": limit, "log": self._git(["log", "--oneline", f"-n{limit}"])})
            if tool_name == "show":
                rev = _safe_rev(str(arguments.get("rev") or "HEAD"))
                max_chars = _bounded_int(arguments.get("max_chars"), default=12000, minimum=1, maximum=50000)
                output = self._git(["show", "--stat", "--format=medium", "--no-ext-diff", rev])
                return self._success({"repo_root": str(self.repo_root), "rev": rev, "content": output[:max_chars], "truncated": len(output) > max_chars})
            return self._failure(f"Unknown git MCP tool: {tool_name}", "unknown_tool")
        except FileNotFoundError as exc:
            return self._failure(str(exc), "git_unavailable")
        except ValueError as exc:
            return self._failure(str(exc), "invalid_revision")
        except RuntimeError as exc:
            return self._failure(str(exc), "git_command_failed")

    def _git(self, args: list[str]) -> str:
        if not (self.repo_root / ".git").exists():
            raise RuntimeError(f"Not a git repository: {self.repo_root}")
        completed = subprocess.run(
            [self.git_bin, "-C", str(self.repo_root), *args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "git command failed").strip())
        return completed.stdout.strip()

    def _success(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "data": data, "metadata": {"connector": "git_readonly"}}

    def _failure(self, error: str, category: str) -> dict[str, Any]:
        return {"success": False, "error": error, "metadata": {"connector": "git_readonly", "error_category": category}}


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _safe_rev(value: str) -> str:
    rev = value.strip() or "HEAD"
    if not all(char.isalnum() or char in {"_", "-", ".", "/", "~", "^"} for char in rev):
        raise ValueError(f"Unsafe git revision: {value}")
    return rev
