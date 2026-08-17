from __future__ import annotations

import re
from typing import Any

from app.memory.model.mem_item import utc_now_iso
from app.memory.model.slot_registry import CONFIDENCE_CALIBRATION_POLICY, enrich_metadata_with_slot_policy


DEFAULT_SCOPE = "global"
DEFAULT_SENSITIVITY = "normal"
DEFAULT_REVIEW_STATUS = "accepted"
PENDING_CONFIDENCE_THRESHOLD = 0.7
MULTI_CANDIDATE_PENDING_CONFIDENCE_THRESHOLD = 0.85
LOW_IMPORTANCE_REVIEW_TYPES = {"decision", "opinion"}
WEAK_SIGNAL_PATTERNS = (
    re.compile(r"\b(?:maybe|probably|perhaps|seems|might|guess|inferred|implied)\b", re.IGNORECASE),
    re.compile(r"(?:可能|也许|大概|似乎|推断|暗示)"),
)

HIGH_RISK_SECRET_PATTERNS = (
    re.compile(
        r"\b(?:my\s+)?(?:password|passcode|api\s*key|access\s*token|refresh\s*token|token|secret|private\s*key)\b"
        r"\s*(?:is|are|=|:)\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:password|passcode|api[_\s-]*key|access[_\s-]*token|refresh[_\s-]*token|token|secret|private[_\s-]*key)"
        r"\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:\u5bc6\u7801|\u53e3\u4ee4|\u5bc6\u94a5|token|api\s*key)"
        r"\s*(?:\u662f|\u4e3a|=|:|\uff1a)\s*\S+",
        re.IGNORECASE,
    ),
)

SENSITIVE_PERSONAL_PATTERNS = (
    re.compile(r"\b(?:id\s*card|bank\s*card|credit\s*card|social\s*security|ssn|passport)\b", re.IGNORECASE),
    re.compile(
        r"(?:\u8eab\u4efd\u8bc1|\u94f6\u884c\u5361|\u4fe1\u7528\u5361|\u62a4\u7167|\u793e\u4fdd)",
        re.IGNORECASE,
    ),
)


def infer_sensitive_category(content: str) -> str:
    if is_high_risk_secret(content):
        return "secret"
    if any(pattern.search(content) for pattern in SENSITIVE_PERSONAL_PATTERNS):
        return "personal_sensitive"
    return "none"


def is_high_risk_secret(content: str) -> bool:
    return any(pattern.search(content) for pattern in HIGH_RISK_SECRET_PATTERNS)


def infer_sensitivity(content: str, mem_type: str) -> str:
    if infer_sensitive_category(content) != "none":
        return "sensitive"
    if mem_type in {"fact", "preference", "decision", "opinion"}:
        return "personal"
    return DEFAULT_SENSITIVITY


def build_source_ref(
    *,
    conversation_id: int | None = None,
    message_id: int | str | None = None,
    task_run_id: str | None = None,
    step_id: str | None = None,
) -> dict[str, Any]:
    source_ref: dict[str, Any] = {}
    if conversation_id is not None:
        source_ref["conversation_id"] = conversation_id
    if message_id is not None:
        source_ref["message_id"] = message_id
    if task_run_id is not None:
        source_ref["task_run_id"] = task_run_id
    if step_id is not None:
        source_ref["step_id"] = step_id
    return source_ref


def flatten_source_ref(source_ref: dict[str, Any] | None) -> dict[str, Any]:
    ref = source_ref or {}
    return {
        "source_conversation_id": str(ref.get("conversation_id", "")),
        "source_message_id": str(ref.get("message_id", "")),
        "source_task_run_id": str(ref.get("task_run_id", "")),
        "source_step_id": str(ref.get("step_id", "")),
    }


def read_source_ref(metadata: dict[str, Any]) -> dict[str, Any]:
    source_ref: dict[str, Any] = {}
    conversation_id = metadata.get("source_conversation_id")
    message_id = metadata.get("source_message_id")
    task_run_id = metadata.get("source_task_run_id")
    step_id = metadata.get("source_step_id")
    if conversation_id not in (None, ""):
        source_ref["conversation_id"] = str(conversation_id)
    if message_id not in (None, ""):
        source_ref["message_id"] = str(message_id)
    if task_run_id not in (None, ""):
        source_ref["task_run_id"] = str(task_run_id)
    if step_id not in (None, ""):
        source_ref["step_id"] = str(step_id)
    return source_ref


def extraction_reason(mem_type: str, slot: str | None = None) -> str:
    if slot:
        return f"matched {mem_type} memory slot '{slot}'"
    return f"matched {mem_type} memory pattern"


def calibrate_confidence(
    *,
    raw_confidence: float,
    mem_type: str,
    metadata: dict[str, Any],
    source: str,
) -> tuple[float, str, str]:
    confidence = max(0.0, min(float(raw_confidence), 1.0))
    factors: list[str] = [f"raw={confidence:.2f}"]
    slot = str(metadata.get("slot", "") or mem_type or "general")
    slot_adjustment = _as_float(metadata.get("slot_confidence_adjustment"), default=0.0)
    confidence += slot_adjustment
    factors.append(f"slot:{slot}={slot_adjustment:+.2f}")

    policy = CONFIDENCE_CALIBRATION_POLICY
    source_adjustment = policy.source_adjustments.get(
        source,
        policy.unknown_source_adjustment if source else 0.0,
    )
    confidence += source_adjustment
    factors.append(f"source:{source or 'unknown'}={source_adjustment:+.2f}")

    extraction_method = str(metadata.get("extraction_method") or "rule")
    method_adjustment = policy.extraction_method_adjustments.get(
        extraction_method,
        policy.unknown_extraction_method_adjustment,
    )
    confidence += method_adjustment
    factors.append(f"method:{extraction_method}={method_adjustment:+.2f}")

    candidate_count = _as_int(metadata.get("candidate_count"), default=1)
    if candidate_count > 1:
        confidence += policy.multi_candidate_adjustment
        factors.append(f"multi_candidate={policy.multi_candidate_adjustment:+.2f}")

    reason_text = " ".join(
        str(metadata.get(key, "") or "") for key in ("extraction_reason", "reason", "update_intent")
    )
    if any(pattern.search(reason_text) for pattern in WEAK_SIGNAL_PATTERNS):
        confidence += policy.weak_signal_adjustment
        factors.append(f"weak_signal={policy.weak_signal_adjustment:+.2f}")

    sensitivity = str(metadata.get("sensitivity") or "")
    if sensitivity == "sensitive":
        confidence += policy.sensitive_adjustment
        factors.append(f"sensitive={policy.sensitive_adjustment:+.2f}")

    calibrated = round(max(0.0, min(confidence, 1.0)), 4)
    reason = f"calibrated from raw confidence {raw_confidence:.2f} using " + ", ".join(factors[1:])
    return calibrated, reason, "; ".join(factors)


def classify_review_status(
    *,
    content: str,
    mem_type: str,
    confidence: float,
    importance: float,
    sensitivity: str | None = None,
    candidate_count: int = 1,
    confidence_threshold: float = PENDING_CONFIDENCE_THRESHOLD,
    multi_candidate_confidence_threshold: float = MULTI_CANDIDATE_PENDING_CONFIDENCE_THRESHOLD,
    low_importance_review_threshold: float | None = None,
) -> tuple[str, str]:
    sensitive_category = infer_sensitive_category(content)
    if sensitive_category == "secret":
        return "rejected", "rejected because memory appears to contain a secret"

    effective_sensitivity = sensitivity or infer_sensitivity(content, mem_type)
    if effective_sensitivity == "sensitive":
        return "pending", "pending because memory appears sensitive"
    if candidate_count > 1 and confidence < multi_candidate_confidence_threshold:
        return (
            "pending",
            "pending because multi-candidate confidence "
            f"{confidence:.2f} is below {multi_candidate_confidence_threshold:.2f}",
        )
    if confidence < confidence_threshold:
        return "pending", f"pending because confidence {confidence:.2f} is below {confidence_threshold:.2f}"
    if low_importance_review_threshold is not None and importance < low_importance_review_threshold:
        return "pending", f"pending because {mem_type} memory has low importance"
    return DEFAULT_REVIEW_STATUS, "accepted by automatic governance policy"


def normalize_governance_metadata(
    *,
    base_metadata: dict[str, Any] | None,
    content: str,
    mem_type: str,
    confidence: float,
    source: str,
    source_ref: dict[str, Any] | None = None,
    scope: str = DEFAULT_SCOPE,
    review_status: str | None = None,
    importance: float = 1.0,
) -> dict[str, Any]:
    metadata = dict(base_metadata or {})
    metadata = enrich_metadata_with_slot_policy(mem_type, metadata)
    metadata.update(flatten_source_ref(source_ref))
    slot = str(metadata.get("slot", "") or "")
    metadata.setdefault("source", source)
    metadata.setdefault("extraction_reason", extraction_reason(mem_type, slot))
    raw_confidence = float(confidence)
    metadata.setdefault("confidence", raw_confidence)
    metadata.setdefault("raw_confidence", raw_confidence)
    metadata.setdefault("scope", scope)
    candidate_count = _as_int(metadata.get("candidate_count"), default=1)
    if candidate_count > 1:
        metadata.setdefault("multi_candidate", True)
        metadata.setdefault("candidate_count", candidate_count)
    sensitivity = str(metadata.get("sensitivity") or infer_sensitivity(content, mem_type))
    metadata.setdefault("sensitivity", sensitivity)
    calibrated_confidence, calibration_reason, calibration_factors = calibrate_confidence(
        raw_confidence=raw_confidence,
        mem_type=mem_type,
        metadata=metadata,
        source=source,
    )
    metadata["calibrated_confidence"] = calibrated_confidence
    metadata["confidence_calibration_reason"] = calibration_reason
    metadata["confidence_calibration_factors"] = calibration_factors
    sensitive_category = infer_sensitive_category(content)
    auto_review_status, review_reason = classify_review_status(
        content=content,
        mem_type=mem_type,
        confidence=calibrated_confidence,
        importance=float(importance),
        sensitivity=sensitivity,
        candidate_count=candidate_count,
        confidence_threshold=_as_float(
            metadata.get("slot_review_confidence_threshold"),
            default=PENDING_CONFIDENCE_THRESHOLD,
        ),
        multi_candidate_confidence_threshold=_as_float(
            metadata.get("slot_multi_candidate_confidence_threshold"),
            default=MULTI_CANDIDATE_PENDING_CONFIDENCE_THRESHOLD,
        ),
        low_importance_review_threshold=_optional_float(metadata.get("slot_low_importance_review_threshold")),
    )
    metadata.setdefault("sensitive_category", sensitive_category)
    if sensitive_category == "secret":
        metadata["review_status"] = "rejected"
        metadata["review_reason"] = review_reason
    else:
        metadata.setdefault("review_status", review_status or auto_review_status)
        metadata.setdefault("review_reason", review_reason)
    observed_at = str(metadata.get("observed_at") or utc_now_iso())
    metadata.setdefault("observed_at", observed_at)
    metadata.setdefault("valid_from", observed_at)
    metadata.setdefault("valid_to", "")
    metadata.setdefault("is_current", True)
    return metadata


def governance_response_fields(metadata: dict[str, Any] | None) -> dict[str, Any]:
    meta = dict(metadata or {})
    return {
        "source": meta.get("source"),
        "source_ref": read_source_ref(meta),
        "extraction_reason": meta.get("extraction_reason"),
        "confidence": meta.get("confidence"),
        "raw_confidence": meta.get("raw_confidence"),
        "calibrated_confidence": meta.get("calibrated_confidence"),
        "confidence_calibration_reason": meta.get("confidence_calibration_reason"),
        "confidence_calibration_factors": meta.get("confidence_calibration_factors"),
        "scope": meta.get("scope"),
        "sensitivity": meta.get("sensitivity"),
        "review_status": meta.get("review_status"),
        "review_reason": meta.get("review_reason"),
        "sensitive_category": meta.get("sensitive_category"),
        "edited_before_accept": _as_bool(meta.get("edited_before_accept"), default=False),
        "last_edited_at": meta.get("last_edited_at"),
        "original_content": meta.get("original_content"),
        "merged_count": meta.get("merged_count"),
        "merged_from": meta.get("merged_from"),
        "merge_events": meta.get("merge_events"),
        "last_merged_at": meta.get("last_merged_at"),
        "last_merge_reason": meta.get("last_merge_reason"),
        "last_merge_type": meta.get("last_merge_type"),
        "extraction_batch_id": meta.get("extraction_batch_id"),
        "candidate_index": meta.get("candidate_index"),
        "candidate_count": meta.get("candidate_count"),
        "multi_candidate": _as_bool(meta.get("multi_candidate"), default=False),
        "observed_at": meta.get("observed_at"),
        "valid_from": meta.get("valid_from"),
        "valid_to": meta.get("valid_to"),
        "is_current": _as_bool(meta.get("is_current"), default=True),
        "consolidation_summary": _as_bool(meta.get("consolidation_summary"), default=False),
        "consolidation_kind": meta.get("consolidation_kind"),
        "consolidation_policy": meta.get("consolidation_policy"),
        "consolidation_evidence_action": meta.get("consolidation_evidence_action"),
        "consolidated_at": meta.get("consolidated_at"),
        "consolidated_count": meta.get("consolidated_count"),
        "consolidated_from": meta.get("consolidated_from"),
        "consolidation_events": meta.get("consolidation_events"),
        "consolidated_into": meta.get("consolidated_into"),
        "retrieval_enabled": _as_bool(meta.get("retrieval_enabled"), default=True),
        "pinned": _as_bool(meta.get("pinned"), default=False),
        "user_hidden": _as_bool(meta.get("user_hidden"), default=False),
        "user_locked": _as_bool(meta.get("user_locked"), default=False),
        "user_control_reason": meta.get("user_control_reason"),
    }


def _as_bool(value: Any, *, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int(value: Any, *, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, *, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
