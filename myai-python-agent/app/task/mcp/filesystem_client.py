from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from app.task.mcp.models import MCPToolDescriptor


_SENSITIVE_FILE_NAMES = {
    "authorized_keys",
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "known_hosts",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
}
_SENSITIVE_FILE_SUFFIXES = {
    ".env",
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
}
_SENSITIVE_NAME_TOKENS = {
    "credential",
    "credentials",
    "password",
    "passwd",
    "secret",
    "secrets",
    "token",
}


class SensitivePathError(PermissionError):
    pass


class ReadOnlyFilesystemMCPClient:
    server_id = "filesystem-readonly"

    def __init__(self, roots: dict[str, Path | str] | None = None) -> None:
        configured_roots = roots or {"workspace": _default_workspace_root()}
        self.roots = {name: Path(path).resolve() for name, path in configured_roots.items()}

    @classmethod
    def from_env(cls) -> "ReadOnlyFilesystemMCPClient":
        raw_roots = os.getenv("MYAI_MCP_FILESYSTEM_ROOTS", "").strip()
        if not raw_roots:
            raise ValueError("MYAI_MCP_FILESYSTEM_ROOTS is required when filesystem MCP is enabled")
        roots: dict[str, Path] = {}
        for index, item in enumerate(raw_roots.split(os.pathsep), start=1):
            path = item.strip()
            if path:
                roots[f"root{index}"] = Path(path)
        if not roots:
            raise ValueError("MYAI_MCP_FILESYSTEM_ROOTS must contain at least one allowed root")
        return cls(roots)

    def list_tools(self, server_id: str | None = None) -> list[MCPToolDescriptor]:
        if server_id not in (None, self.server_id):
            return []
        root_schema = {
            "type": "string",
            "description": "Allowed root id.",
            "enum": list(self.roots),
            "default": self._default_root_name(),
        }
        return [
            MCPToolDescriptor(
                server_id=self.server_id,
                name="list_files",
                description="List files and folders under an allowed read-only root.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path under the selected root.", "default": "."},
                        "root": root_schema,
                        "max_entries": {"type": "integer", "default": 100},
                    },
                    "required": [],
                },
                risk_level="filesystem/read",
                timeout_seconds=3.0,
                allowed_in_hosted=False,
                annotations={"readOnlyHint": True, "capabilities": ["filesystem.read"]},
            ),
            MCPToolDescriptor(
                server_id=self.server_id,
                name="read_text",
                description="Read a UTF-8 text file from an allowed read-only root.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path under the selected root."},
                        "root": root_schema,
                        "max_chars": {"type": "integer", "default": 12000},
                    },
                    "required": ["path"],
                },
                risk_level="filesystem/read",
                timeout_seconds=3.0,
                allowed_in_hosted=False,
                annotations={"readOnlyHint": True, "capabilities": ["filesystem.read"]},
            ),
            MCPToolDescriptor(
                server_id=self.server_id,
                name="search_names",
                description="Search file and folder names under an allowed read-only root.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Case-insensitive filename query."},
                        "path": {"type": "string", "description": "Relative search path.", "default": "."},
                        "root": root_schema,
                        "max_results": {"type": "integer", "default": 50},
                    },
                    "required": ["query"],
                },
                risk_level="filesystem/read",
                timeout_seconds=5.0,
                allowed_in_hosted=False,
                annotations={"readOnlyHint": True, "capabilities": ["filesystem.read"]},
            ),
        ]

    def inspect_connector(self) -> dict[str, Any]:
        roots = []
        for name, path in self.roots.items():
            exists = path.exists()
            is_dir = path.is_dir()
            readable = exists and is_dir
            roots.append(
                {
                    "name": name,
                    "path": str(path),
                    "exists": exists,
                    "readable": readable,
                }
            )
        healthy = bool(roots) and all(root["readable"] for root in roots)
        return {
            "server_id": self.server_id,
            "name": "Filesystem Read-Only",
            "description": "Read-only filesystem connector scoped to configured local roots.",
            "enabled": True,
            "health": {
                "ok": healthy,
                "message": "All configured roots are readable." if healthy else "One or more configured roots are unavailable.",
            },
            "settings": {
                "roots": roots,
                "env": {
                    "enabled": "MYAI_MCP_FILESYSTEM_ENABLED",
                    "roots": "MYAI_MCP_FILESYSTEM_ROOTS",
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
            return self._failure(f"Unknown filesystem MCP server: {server_id}", "unknown_server")
        try:
            if tool_name == "list_files":
                return self._success(self._list_files(arguments))
            if tool_name == "read_text":
                return self._success(self._read_text(arguments))
            if tool_name == "search_names":
                return self._success(self._search_names(arguments))
            return self._failure(f"Unknown filesystem MCP tool: {tool_name}", "unknown_tool")
        except SensitivePathError as exc:
            return self._failure(str(exc), "sensitive_path")
        except PermissionError as exc:
            return self._failure(str(exc), "path_outside_allowed_roots")
        except FileNotFoundError as exc:
            return self._failure(str(exc), "path_not_found")
        except IsADirectoryError as exc:
            return self._failure(str(exc), "expected_file")
        except NotADirectoryError as exc:
            return self._failure(str(exc), "expected_directory")
        except UnicodeDecodeError as exc:
            return self._failure(str(exc), "decode_error")

    def _list_files(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(arguments.get("path") or ".", arguments.get("root") or self._default_root_name())
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Expected directory: {path}")
        max_entries = _bounded_int(arguments.get("max_entries"), default=100, minimum=1, maximum=500)
        entries = []
        visible_children = [child for child in path.iterdir() if self._is_visible_path(child)]
        for child in sorted(visible_children, key=lambda item: (item.is_file(), item.name.lower()))[:max_entries]:
            entries.append(
                {
                    "name": child.name,
                    "path": self._display_path(child),
                    "type": "directory" if child.is_dir() else "file",
                    "size_bytes": child.stat().st_size if child.is_file() else None,
                }
            )
        return {"root": self._root_label(path), "path": self._display_path(path), "entries": entries}

    def _read_text(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(arguments.get("path") or "", arguments.get("root") or self._default_root_name())
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if not path.is_file():
            raise IsADirectoryError(f"Expected file: {path}")
        max_chars = _bounded_int(arguments.get("max_chars"), default=12000, minimum=1, maximum=50000)
        text = path.read_text(encoding="utf-8")
        truncated = len(text) > max_chars
        return {
            "root": self._root_label(path),
            "path": self._display_path(path),
            "content": text[:max_chars],
            "truncated": truncated,
            "chars": min(len(text), max_chars),
            "size_bytes": path.stat().st_size,
        }

    def _search_names(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query") or "").strip().lower()
        if not query:
            return {"query": "", "matches": []}
        path = self._resolve(arguments.get("path") or ".", arguments.get("root") or self._default_root_name())
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Expected directory: {path}")
        max_results = _bounded_int(arguments.get("max_results"), default=50, minimum=1, maximum=200)
        matches = []
        for current_path, directory_names, file_names in os.walk(path, followlinks=False):
            current = Path(current_path)
            directory_names[:] = [
                name for name in directory_names if self._is_visible_path(current / name)
            ]
            for name in sorted([*directory_names, *file_names], key=str.lower):
                child = current / name
                if not self._is_visible_path(child) or query not in name.lower():
                    continue
                matches.append(
                    {
                        "name": child.name,
                        "path": self._display_path(child),
                        "type": "directory" if child.is_dir() else "file",
                    }
                )
                if len(matches) >= max_results:
                    return {
                        "root": self._root_label(path),
                        "path": self._display_path(path),
                        "query": query,
                        "matches": matches,
                    }
        return {"root": self._root_label(path), "path": self._display_path(path), "query": query, "matches": matches}

    def _resolve(self, requested_path: str, root_name: str) -> Path:
        root = self.roots.get(str(root_name))
        if root is None:
            raise PermissionError(f"Unknown allowed root: {root_name}")
        candidate = Path(str(requested_path or "."))
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        if not _is_relative_to(resolved, root):
            raise PermissionError(f"Path is outside allowed root '{root_name}': {requested_path}")
        if _is_sensitive_path(resolved, root):
            raise SensitivePathError(f"Sensitive or hidden path is not accessible: {requested_path}")
        return resolved

    def _is_visible_path(self, path: Path) -> bool:
        resolved = path.resolve()
        for root in self.roots.values():
            if _is_relative_to(resolved, root):
                return not _is_sensitive_path(resolved, root)
        return False

    def _display_path(self, path: Path) -> str:
        root_name = self._root_label(path)
        root = self.roots[root_name]
        relative = path.resolve().relative_to(root)
        value = relative.as_posix()
        return "." if value == "." else value

    def _root_label(self, path: Path) -> str:
        resolved = path.resolve()
        for name, root in self.roots.items():
            if _is_relative_to(resolved, root):
                return name
        return "workspace"

    def _default_root_name(self) -> str:
        return next(iter(self.roots), "workspace")

    def _success(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "data": data, "metadata": {"connector": "filesystem_readonly"}}

    def _failure(self, error: str, category: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": error,
            "metadata": {"connector": "filesystem_readonly", "error_category": category},
        }


def _default_workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_sensitive_path(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    for part in relative.parts:
        normalized = part.casefold()
        if normalized.startswith("."):
            return True
        if normalized in _SENSITIVE_FILE_NAMES:
            return True
        if any(normalized.endswith(suffix) for suffix in _SENSITIVE_FILE_SUFFIXES):
            return True
        tokens = set(re.split(r"[^a-z0-9]+", normalized))
        if tokens & _SENSITIVE_NAME_TOKENS:
            return True
    return False


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))
