from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping


_SECRET_KEY_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "authorization",
    "cookie",
)
_PATH_KEY_MARKERS = ("path", "root", "directory", "filename")
_BODY_KEYS = {
    "body",
    "content",
    "document",
    "memory",
    "prompt",
    "raw",
    "snippet",
    "text",
}
_EVIDENCE_COLLECTION_KEYS = {"citations", "hits", "memories", "selected", "snippets"}
_EVIDENCE_ID_KEYS = {
    "citation_id",
    "chunk_id",
    "file_id",
    "file_name",
    "memory_id",
    "mem_type",
    "page",
    "rank",
    "scope",
    "source",
}
_AGENT_SCALAR_KEYS = {
    "attempt",
    "background",
    "call_latency_ms",
    "call_status",
    "candidate_count",
    "confidence",
    "connector_id",
    "error",
    "latency_ms",
    "max_attempts",
    "memory_id",
    "need_tool",
    "policy_decision",
    "reason",
    "recovery_status",
    "retryable",
    "selected_count",
    "source",
    "status",
    "step_count",
    "success",
    "task_run_id",
    "tool_name",
    "written",
    "written_count",
}
_MAX_STRING_CHARS = 8_192
_MAX_COLLECTION_ITEMS = 100
_MAX_DEPTH = 8

_ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|credential)\b"
    r"\s*(?::|=|is)\s*([^\s,;]+)"
)
_CHINESE_SECRET_RE = re.compile(
    r"(?i)(密码|口令|密钥|令牌|api\s*key)\s*(?:是|为|=|:|：)\s*\S+"
)
_PERSONAL_IDENTIFIER_RE = re.compile(
    r"(?i)\b(ssn|passport|id\s*card|bank\s*card|credit\s*card)\b"
    r"\s*(?::|=|is)\s*([^\s,;]+)"
)
_CHINESE_PERSONAL_IDENTIFIER_RE = re.compile(
    r"(身份证(?:号)?|银行卡(?:号)?|信用卡(?:号)?|护照(?:号)?|社保(?:号)?)"
    r"\s*(?:是|为|=|:|：)\s*\S+"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_OPENAI_STYLE_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?i)(?<![\w])(?:[A-Z]:[\\/]|\\\\)[^\r\n\t\"']+")
_POSIX_HOME_PATH_RE = re.compile(r"(?<![\w])/(?:home|Users|root|var|tmp)/[^\r\n\t\"']+")


def sanitize_text_for_storage(value: str | None, *, max_chars: int = _MAX_STRING_CHARS) -> str | None:
    """Redact common inline credentials and local absolute paths before persistence."""
    if value is None:
        return None
    text = str(value)
    text = _ASSIGNMENT_SECRET_RE.sub(lambda match: f"{match.group(1)}=[redacted-secret]", text)
    text = _CHINESE_SECRET_RE.sub(lambda match: f"{match.group(1)}=[redacted-secret]", text)
    text = _PERSONAL_IDENTIFIER_RE.sub(
        lambda match: f"{match.group(1)}=[redacted-personal]",
        text,
    )
    text = _CHINESE_PERSONAL_IDENTIFIER_RE.sub(
        lambda match: f"{match.group(1)}=[redacted-personal]",
        text,
    )
    text = _BEARER_RE.sub("Bearer [redacted-secret]", text)
    text = _OPENAI_STYLE_KEY_RE.sub("[redacted-secret]", text)
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub("[local-path]", text)
    text = _POSIX_HOME_PATH_RE.sub("[local-path]", text)
    if len(text) > max_chars:
        digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]
        text = f"{text[:max_chars]}...[truncated sha256={digest} chars={len(text)}]"
    return text


def sanitize_structured_for_storage(value: Any, *, _depth: int = 0, _parent_key: str = "") -> Any:
    """Create a bounded, JSON-safe snapshot using explicit secret/body handling rules."""
    if _depth >= _MAX_DEPTH:
        return "[truncated-depth]"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        if _is_body_key(_parent_key):
            return _body_reference(value)
        return sanitize_text_for_storage(value)
    if isinstance(value, Path):
        return f"[local-path:{value.name or 'root'}]"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return sanitize_structured_for_storage(value.model_dump(), _depth=_depth + 1, _parent_key=_parent_key)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (raw_key, item) in enumerate(value.items()):
            if index >= _MAX_COLLECTION_ITEMS:
                result["_truncated_items"] = len(value) - _MAX_COLLECTION_ITEMS
                break
            key = str(raw_key)
            normalized = key.strip().lower()
            if _is_secret_key(normalized):
                result[key] = None if item in (None, "") else "[redacted-secret]"
            elif _is_path_key(normalized):
                result[key] = _path_reference(item)
            else:
                result[key] = sanitize_structured_for_storage(
                    item,
                    _depth=_depth + 1,
                    _parent_key=normalized,
                )
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        sanitized = [
            sanitize_structured_for_storage(item, _depth=_depth + 1, _parent_key=_parent_key)
            for item in items[:_MAX_COLLECTION_ITEMS]
        ]
        if len(items) > _MAX_COLLECTION_ITEMS:
            sanitized.append({"_truncated_items": len(items) - _MAX_COLLECTION_ITEMS})
        return sanitized
    return f"[unsupported:{type(value).__name__}]"


def sanitize_agent_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Persist an allow-listed trace summary, not raw prompt, memory, or knowledge bodies."""
    if not metadata:
        return {}
    result: dict[str, Any] = {}
    for key in _AGENT_SCALAR_KEYS:
        if key in metadata:
            result[key] = sanitize_structured_for_storage(metadata[key], _parent_key=key)

    for collection_key in _EVIDENCE_COLLECTION_KEYS:
        collection = metadata.get(collection_key)
        if not isinstance(collection, (list, tuple)):
            continue
        result[f"{collection_key}_count"] = len(collection)
        safe_items = []
        for item in collection[:_MAX_COLLECTION_ITEMS]:
            if not isinstance(item, Mapping):
                continue
            safe_item = {
                key: sanitize_structured_for_storage(item[key], _parent_key=key)
                for key in _EVIDENCE_ID_KEYS
                if key in item
            }
            if safe_item:
                safe_items.append(safe_item)
        if safe_items:
            result[collection_key] = safe_items

    plan = metadata.get("plan")
    if isinstance(plan, Mapping):
        steps = plan.get("steps")
        result["plan"] = {
            key: sanitize_structured_for_storage(plan[key], _parent_key=key)
            for key in ("source", "need_tool", "workflow_id")
            if key in plan
        }
        if isinstance(steps, (list, tuple)):
            result["plan"]["step_count"] = len(steps)

    task_result = metadata.get("result")
    if isinstance(task_result, Mapping):
        result["result"] = {
            key: sanitize_structured_for_storage(task_result[key], _parent_key=key)
            for key in ("success", "cancelled", "error", "summary", "task_run_id")
            if key in task_result
        }
    return result


def _is_secret_key(key: str) -> bool:
    return any(marker in key for marker in _SECRET_KEY_MARKERS)


def _is_path_key(key: str) -> bool:
    return any(marker in key for marker in _PATH_KEY_MARKERS)


def _is_body_key(key: str) -> bool:
    return key in _BODY_KEYS or key.endswith("_content") or key.endswith("_text")


def _body_reference(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"[redacted-body sha256={digest} chars={len(value)}]"


def _path_reference(value: Any) -> Any:
    if value in (None, ""):
        return value
    if isinstance(value, Path):
        name = value.name
    else:
        normalized = str(value).strip().replace("\\", "/").rstrip("/")
        name = normalized.rsplit("/", 1)[-1]
    return f"[local-path:{name or 'root'}]"
