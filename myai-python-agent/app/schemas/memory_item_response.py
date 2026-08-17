from pydantic import BaseModel, Field
from typing import Any


class MemoryItemResponse(BaseModel):
    memory_id: str
    content: str
    mem_type: str
    score: float
    importance: float
    created_at: str
    last_accessed_at: str
    access_count: int
    status: str
    source: str | None = None
    source_ref: dict[str, Any] = Field(default_factory=dict)
    extraction_reason: str | None = None
    confidence: float | None = None
    raw_confidence: float | None = None
    calibrated_confidence: float | None = None
    confidence_calibration_reason: str | None = None
    confidence_calibration_factors: str | None = None
    scope: str | None = None
    sensitivity: str | None = None
    review_status: str | None = None
    review_reason: str | None = None
    sensitive_category: str | None = None
    edited_before_accept: bool | None = None
    last_edited_at: str | None = None
    original_content: str | None = None
    merged_count: int | None = None
    merged_from: str | None = None
    merge_events: str | None = None
    last_merged_at: str | None = None
    last_merge_reason: str | None = None
    last_merge_type: str | None = None
    extraction_batch_id: str | None = None
    candidate_index: int | None = None
    candidate_count: int | None = None
    multi_candidate: bool | None = None
    observed_at: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    is_current: bool | None = None
    consolidation_summary: bool | None = None
    consolidation_kind: str | None = None
    consolidation_policy: str | None = None
    consolidation_evidence_action: str | None = None
    consolidated_at: str | None = None
    consolidated_count: int | None = None
    consolidated_from: str | None = None
    consolidation_events: str | None = None
    consolidated_into: str | None = None
    retrieval_enabled: bool | None = None
    pinned: bool | None = None
    user_hidden: bool | None = None
    user_locked: bool | None = None
    user_control_reason: str | None = None
