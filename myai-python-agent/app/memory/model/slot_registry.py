from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Cardinality = Literal["single", "multi"]
ConflictPolicy = Literal["supersede", "coexist", "append", "pending"]
ConsolidationPolicy = Literal["replace_evidence", "coexist_with_evidence"]


@dataclass(frozen=True)
class SlotDefinition:
    mem_type: str
    slot: str
    aliases: tuple[str, ...] = ()
    cardinality: Cardinality = "multi"
    conflict_policy: ConflictPolicy = "coexist"
    confidence_adjustment: float = 0.0
    review_confidence_threshold: float = 0.7
    multi_candidate_confidence_threshold: float = 0.85
    retrieval_weight: float = 1.0
    low_importance_review_threshold: float | None = None
    consolidation_policy: ConsolidationPolicy = "replace_evidence"


DEFAULT_SLOT_DEFINITION = SlotDefinition(
    mem_type="general",
    slot="general",
    cardinality="multi",
    conflict_policy="coexist",
    confidence_adjustment=-0.03,
    retrieval_weight=1.0,
    consolidation_policy="replace_evidence",
)


@dataclass(frozen=True)
class ConfidenceCalibrationPolicy:
    source_adjustments: dict[str, float]
    extraction_method_adjustments: dict[str, float]
    unknown_source_adjustment: float = -0.01
    unknown_extraction_method_adjustment: float = -0.02
    multi_candidate_adjustment: float = -0.03
    weak_signal_adjustment: float = -0.08
    sensitive_adjustment: float = -0.05


CONFIDENCE_CALIBRATION_POLICY = ConfidenceCalibrationPolicy(
    source_adjustments={
        "user_explicit": 0.04,
        "chat_extraction": 0.0,
    },
    extraction_method_adjustments={
        "rule": 0.02,
        "llm": -0.04,
    },
)


SLOT_DEFINITIONS: tuple[SlotDefinition, ...] = (
    SlotDefinition("fact", "name", aliases=("\u59d3\u540d", "\u540d\u5b57"), cardinality="single", conflict_policy="supersede", confidence_adjustment=0.03, retrieval_weight=1.1),
    SlotDefinition("fact", "major", aliases=("\u4e13\u4e1a", "study"), cardinality="single", conflict_policy="supersede", confidence_adjustment=0.04, retrieval_weight=1.15),
    SlotDefinition("fact", "school", aliases=("\u5b66\u6821",), cardinality="single", conflict_policy="supersede", confidence_adjustment=0.03, retrieval_weight=1.1),
    SlotDefinition("fact", "location", aliases=("\u4f4f\u5740", "\u57ce\u5e02", "live"), cardinality="single", conflict_policy="supersede", confidence_adjustment=0.02, retrieval_weight=1.15),
    SlotDefinition("fact", "hometown", aliases=("\u5bb6\u4e61",), cardinality="single", conflict_policy="supersede", confidence_adjustment=0.02, retrieval_weight=1.05),
    SlotDefinition("fact", "job", aliases=("\u804c\u4e1a", "occupation", "profession"), cardinality="single", conflict_policy="supersede", confidence_adjustment=0.02, retrieval_weight=1.1),
    SlotDefinition("fact", "work", aliases=("\u5de5\u4f5c",), cardinality="single", conflict_policy="supersede", confidence_adjustment=0.02, retrieval_weight=1.05),
    SlotDefinition("fact", "birthday", aliases=("\u751f\u65e5",), cardinality="single", conflict_policy="supersede", confidence_adjustment=0.01, retrieval_weight=1.0),
    SlotDefinition("fact", "identity", aliases=("\u8eab\u4efd",), cardinality="multi", conflict_policy="coexist", confidence_adjustment=-0.02, retrieval_weight=1.0),
    SlotDefinition("preference", "preference", aliases=("\u559c\u597d", "like"), cardinality="multi", conflict_policy="coexist", confidence_adjustment=-0.02, retrieval_weight=1.2, consolidation_policy="coexist_with_evidence"),
    SlotDefinition("preference", "favorite", aliases=("\u6700\u559c\u6b22", "favorite"), cardinality="multi", conflict_policy="coexist", confidence_adjustment=-0.02, retrieval_weight=1.2, consolidation_policy="coexist_with_evidence"),
    SlotDefinition("decision", "decision", aliases=("\u8ba1\u5212", "\u76ee\u6807", "goal", "plan"), cardinality="multi", conflict_policy="append", confidence_adjustment=-0.03, retrieval_weight=1.25, low_importance_review_threshold=4),
    SlotDefinition("opinion", "opinion", aliases=("\u770b\u6cd5", "\u89c2\u70b9"), cardinality="multi", conflict_policy="coexist", confidence_adjustment=-0.06, retrieval_weight=1.05, low_importance_review_threshold=4),
)


def normalize_slot(mem_type: str, slot: str | None) -> str:
    raw_slot = (slot or mem_type or "general").strip().lower().replace(" ", "_")
    for definition in SLOT_DEFINITIONS:
        names = (definition.slot, *definition.aliases)
        if definition.mem_type == mem_type and raw_slot in {name.lower().replace(" ", "_") for name in names}:
            return definition.slot
    return raw_slot or "general"


def normalize_value(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    normalized = " ".join(normalized.split())
    aliases = {
        "cs": "computer science",
        "\u8ba1\u7b97\u673a": "\u8ba1\u7b97\u673a\u79d1\u5b66",
        "ai": "artificial intelligence",
        "\u4eba\u5de5\u667a\u80fd\u4e13\u4e1a": "\u4eba\u5de5\u667a\u80fd",
    }
    return aliases.get(normalized, normalized)


def get_slot_definition(mem_type: str, slot: str | None) -> SlotDefinition:
    normalized = normalize_slot(mem_type, slot)
    for definition in SLOT_DEFINITIONS:
        if definition.mem_type == mem_type and definition.slot == normalized:
            return definition
    return SlotDefinition(
        mem_type=mem_type or DEFAULT_SLOT_DEFINITION.mem_type,
        slot=normalized or DEFAULT_SLOT_DEFINITION.slot,
        cardinality=DEFAULT_SLOT_DEFINITION.cardinality,
        conflict_policy=DEFAULT_SLOT_DEFINITION.conflict_policy,
        confidence_adjustment=DEFAULT_SLOT_DEFINITION.confidence_adjustment,
        review_confidence_threshold=DEFAULT_SLOT_DEFINITION.review_confidence_threshold,
        multi_candidate_confidence_threshold=DEFAULT_SLOT_DEFINITION.multi_candidate_confidence_threshold,
        retrieval_weight=DEFAULT_SLOT_DEFINITION.retrieval_weight,
        low_importance_review_threshold=DEFAULT_SLOT_DEFINITION.low_importance_review_threshold,
        consolidation_policy=DEFAULT_SLOT_DEFINITION.consolidation_policy,
    )


def enrich_metadata_with_slot_policy(mem_type: str, metadata: dict) -> dict:
    enriched = dict(metadata or {})
    slot = normalize_slot(mem_type, str(enriched.get("slot", "") or ""))
    value = normalize_value(str(enriched.get("value", "") or ""))
    definition = get_slot_definition(mem_type, slot)
    enriched["slot"] = slot
    enriched["value"] = value
    enriched["slot_cardinality"] = definition.cardinality
    enriched["conflict_policy"] = definition.conflict_policy
    enriched["slot_confidence_adjustment"] = definition.confidence_adjustment
    enriched["slot_review_confidence_threshold"] = definition.review_confidence_threshold
    enriched["slot_multi_candidate_confidence_threshold"] = definition.multi_candidate_confidence_threshold
    enriched["slot_retrieval_weight"] = definition.retrieval_weight
    enriched["slot_consolidation_policy"] = definition.consolidation_policy
    if definition.low_importance_review_threshold is not None:
        enriched["slot_low_importance_review_threshold"] = definition.low_importance_review_threshold
    else:
        enriched.pop("slot_low_importance_review_threshold", None)
    return enriched
