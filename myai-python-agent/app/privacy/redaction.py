from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any


SECRET_KEY_MARKERS = ("password", "passwd", "secret", "token", "api_key", "apikey", "credential")
PATH_KEYS = {
    "path",
    "file_path",
    "stored_path",
    "persist_path",
    "repo_root",
    "root_path",
    "storage_path",
}


def privacy_metadata(include_sensitive: bool = False) -> dict[str, Any]:
    return {
        "sensitive_included": bool(include_sensitive),
        "redaction_applied": not include_sensitive,
        "redacted_fields": sorted([*PATH_KEYS, *SECRET_KEY_MARKERS]),
        "policy": "Default API responses redact local absolute paths and secret-like values. Use include_sensitive=true only for local troubleshooting.",
    }


def sanitize_for_api(value: Any, *, include_sensitive: bool = False) -> Any:
    if include_sensitive:
        return copy.deepcopy(value)
    return _sanitize(value, parent_key="")


def _sanitize(value: Any, *, parent_key: str) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_dict_value(key, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item, parent_key=parent_key) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item, parent_key=parent_key) for item in value]
    if isinstance(value, Path):
        return _redact_path(str(value))
    if isinstance(value, str) and _is_path_key(parent_key) and _looks_like_absolute_path(value):
        return _redact_path(value)
    return value


def _sanitize_dict_value(key: str, value: Any) -> Any:
    normalized = key.lower()
    if _is_secret_key(normalized):
        return "[redacted-secret]" if value not in (None, "") else value
    if _is_path_key(normalized):
        if isinstance(value, str) and _looks_like_absolute_path(value):
            return _redact_path(value)
        if isinstance(value, Path):
            return _redact_path(str(value))
    return _sanitize(value, parent_key=normalized)


def _is_secret_key(key: str) -> bool:
    return any(marker in key for marker in SECRET_KEY_MARKERS)


def _is_path_key(key: str) -> bool:
    return key in PATH_KEYS or key.endswith("_path") or key.endswith("_root")


def _looks_like_absolute_path(value: str) -> bool:
    stripped = value.strip()
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", stripped)
        or stripped.startswith("\\\\")
        or stripped.startswith("/")
    )


def _redact_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/").rstrip("/")
    if not normalized:
        return "[local-path]"
    name = normalized.split("/")[-1] or "root"
    return f"[local-path:{name}]"
