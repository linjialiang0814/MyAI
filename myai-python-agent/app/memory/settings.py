from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any


@dataclass(frozen=True)
class UserMemorySettings:
    memory_enabled: bool = True
    auto_write_enabled: bool = True
    sensitive_requires_confirmation: bool = True
    default_memory_view: str = "simple"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UserMemorySettings":
        data = data or {}
        return cls(
            memory_enabled=_as_bool(data.get("memory_enabled"), True),
            auto_write_enabled=_as_bool(data.get("auto_write_enabled"), True),
            sensitive_requires_confirmation=_as_bool(data.get("sensitive_requires_confirmation"), True),
            default_memory_view=_default_view(data.get("default_memory_view")),
        )

    def update(self, patch: dict[str, Any]) -> "UserMemorySettings":
        current = asdict(self)
        for key in current:
            if key in patch and patch[key] is not None:
                current[key] = patch[key]
        return UserMemorySettings.from_dict(current)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemorySettingsStore:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        resolved_base_dir = base_dir or os.getenv("MYAI_MEMORY_SETTINGS_DIR", "./memory_settings")
        self.base_path = Path(resolved_base_dir)
        self._lock = threading.RLock()
        self._last_known_good: dict[str, UserMemorySettings] = {}

    def get(self, user_id: str) -> UserMemorySettings:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            raise ValueError("user_id cannot be blank")
        with self._lock:
            path = self._path(normalized_user_id)
            if not path.exists():
                settings = UserMemorySettings()
                self._last_known_good[normalized_user_id] = settings
                return settings
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("memory settings must be a JSON object")
                settings = UserMemorySettings.from_dict(payload)
                self._last_known_good[normalized_user_id] = settings
                return settings
            except (OSError, ValueError, json.JSONDecodeError):
                cached = self._last_known_good.get(normalized_user_id)
                if cached is not None:
                    return cached
                # Existing but unreadable settings fail closed. Falling back to the
                # feature-on defaults could silently re-enable memory after a torn
                # or externally corrupted write.
                return UserMemorySettings(
                    memory_enabled=False,
                    auto_write_enabled=False,
                    sensitive_requires_confirmation=True,
                )

    def update(self, user_id: str, patch: dict[str, Any]) -> UserMemorySettings:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            raise ValueError("user_id cannot be blank")
        with self._lock:
            settings = self.get(normalized_user_id).update(patch)
            path = self._path(normalized_user_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(settings.to_dict(), ensure_ascii=False, indent=2) + "\n"
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                    delete=False,
                    dir=path.parent,
                    prefix="settings-",
                    suffix=".tmp",
                ) as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                    temporary_path = Path(handle.name)
                os.replace(temporary_path, path)
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink(missing_ok=True)
            self._last_known_good[normalized_user_id] = settings
            return settings

    def _path(self, user_id: str) -> Path:
        safe_user_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(user_id))
        return self.base_path / safe_user_id / "settings.json"


def settings_schema() -> list[dict[str, Any]]:
    return [
        {
            "key": "memory_enabled",
            "default": True,
            "description": "Allow the assistant to persist and retrieve durable user memories.",
        },
        {
            "key": "auto_write_enabled",
            "default": True,
            "description": "Allow accepted memory candidates to be written automatically.",
        },
        {
            "key": "sensitive_requires_confirmation",
            "default": True,
            "description": "Route sensitive memories to confirmation before retrieval.",
        },
        {
            "key": "default_memory_view",
            "default": "simple",
            "description": "Default frontend view for memory cards.",
        },
    ]


def _as_bool(value: Any, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _default_view(value: Any) -> str:
    view = str(value or "simple").strip().lower()
    if view not in {"simple", "audit"}:
        return "simple"
    return view
