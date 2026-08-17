from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, List

from app.memory.retrieval.retriever import RetrievedMemory

SIM_THRESHOLD = 0.25
MAX_MEMORIES = 3
LOW_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class MemoryRetrievalDecision:
    memory: RetrievedMemory
    selected: bool
    reason: str
    final_score: float = 0.0
    factors: dict[str, Any] = field(default_factory=dict)

class MemoryPolicy:
    TYPE_WEIGHTS = {
        "preference": 1.2,
        "fact": 1.1,
        "decision": 1.25,
        "opinion": 1.05,
        "general": 1.0,
    }
    SOURCE_WEIGHTS = {
        "user_explicit": 1.08,
        "chat_extraction": 0.98,
        "memory_edit": 1.06,
        "migration": 0.95,
        "system": 1.0,
        "": 0.92,
    }
    FRESHNESS_HALF_LIFE_DAYS = {
        "decision": 90.0,
        "opinion": 180.0,
        "general": 365.0,
        "preference": 1825.0,
        "fact": 3650.0,
    }
    FRESHNESS_FLOORS = {
        "decision": 0.65,
        "opinion": 0.70,
        "general": 0.80,
        "preference": 0.90,
        "fact": 0.92,
    }

    @classmethod
    def filter_memories(
        cls,
        memories: List[RetrievedMemory],
        *,
        conversation_id: int | None = None,
        include_pending: bool = False,
        include_sensitive: bool = False,
    ) -> List[RetrievedMemory]:
        decisions = cls.explain_memories(
            memories,
            conversation_id=conversation_id,
            include_pending=include_pending,
            include_sensitive=include_sensitive,
        )
        return [decision.memory for decision in decisions if decision.selected]

    @classmethod
    def explain_memories(
        cls,
        memories: List[RetrievedMemory],
        *,
        conversation_id: int | None = None,
        include_pending: bool = False,
        include_sensitive: bool = False,
    ) -> List[MemoryRetrievalDecision]:
        decisions: list[MemoryRetrievalDecision] = []
        eligible: list[MemoryRetrievalDecision] = []
        for mem in memories:
            rejection_reason = cls._filter_reason(
                mem,
                conversation_id=conversation_id,
                include_pending=include_pending,
                include_sensitive=include_sensitive,
            )
            if rejection_reason:
                decisions.append(
                    MemoryRetrievalDecision(
                        memory=mem,
                        selected=False,
                        reason=rejection_reason,
                        factors=cls._base_factors(mem),
                    )
                )
                continue

            final_score, factors = cls._score(mem)
            mem.final_score = final_score
            eligible.append(
                MemoryRetrievalDecision(
                    memory=mem,
                    selected=False,
                    reason="eligible",
                    final_score=final_score,
                    factors=factors,
                )
            )

        eligible.sort(key=lambda decision: decision.final_score, reverse=True)
        for index, decision in enumerate(eligible):
            if index < MAX_MEMORIES:
                decision.selected = True
                decision.reason = "selected by retrieval score"
            else:
                decision.reason = "filtered because outside memory context limit"
            decisions.append(decision)

        return decisions

    @classmethod
    def _filter_reason(
        cls,
        mem: RetrievedMemory,
        *,
        conversation_id: int | None,
        include_pending: bool,
        include_sensitive: bool,
    ) -> str | None:
        # Cosine similarity may legitimately be exactly 1.0 for an identical
        # query and memory. Allow a small numerical tolerance above one because
        # float32/vector-store round-off can otherwise reject a perfect match.
        if (
            not math.isfinite(mem.similarity)
            or mem.similarity < SIM_THRESHOLD
            or mem.similarity > 1.000001
        ):
            return f"filtered because similarity {mem.similarity:.4f} is outside [{SIM_THRESHOLD:.2f}, 1.00]"
        if mem.mem_status != "active":
            return f"filtered because memory status is {mem.mem_status}"
        if not mem.retrieval_enabled:
            return "filtered because user disabled retrieval for this memory"
        if mem.user_hidden:
            return "filtered because user hid this memory"
        if mem.review_status == "rejected":
            return "filtered because review_status is rejected"
        if mem.review_status == "pending" and not include_pending:
            return "filtered because review_status is pending"
        if mem.sensitivity == "sensitive" and not include_sensitive:
            return "filtered because sensitivity is sensitive"
        if not cls._scope_allowed(mem, conversation_id):
            return "filtered because scope is not allowed for this conversation"
        return None

    @classmethod
    def _score(cls, mem: RetrievedMemory) -> tuple[float, dict[str, Any]]:
        type_weight = cls.TYPE_WEIGHTS.get(mem.mem_type, 1.0)
        slot_weight = max(0.1, float(mem.retrieval_weight or 1.0))
        source_weight = cls.SOURCE_WEIGHTS.get(mem.source, 0.92)
        freshness_weight, freshness_factors = cls._freshness_weight(mem)
        current_weight = 1.0 if mem.is_current else 0.55
        confidence = max(0.0, min(float(mem.confidence), 1.0))
        confidence_weight = 1.0
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            confidence_weight = 0.65
        elif confidence < 0.8:
            confidence_weight = 0.85
        if mem.sensitivity == "personal":
            confidence_weight *= 0.95
        similarity_component = 0.60 * mem.similarity
        score_component = 0.25 * min(mem.score, 1.0)
        importance_component = 0.15 * min(mem.importance / 10.0, 1.0)
        base_score = similarity_component + score_component + importance_component
        final_score = (
            base_score
            * type_weight
            * slot_weight
            * source_weight
            * freshness_weight
            * current_weight
            * confidence_weight
        )
        factors = cls._base_factors(mem)
        factors.update(
            {
                "similarity_component": round(similarity_component, 4),
                "score_component": round(score_component, 4),
                "importance_component": round(importance_component, 4),
                "type_weight": round(type_weight, 4),
                "slot_weight": round(slot_weight, 4),
                "source_weight": round(source_weight, 4),
                "freshness_weight": round(freshness_weight, 4),
                "current_weight": round(current_weight, 4),
                "confidence_weight": round(confidence_weight, 4),
                "base_score": round(base_score, 4),
                "final_score": round(final_score, 4),
            }
        )
        factors.update(freshness_factors)
        return final_score, factors

    @staticmethod
    def _base_factors(mem: RetrievedMemory) -> dict[str, Any]:
        return {
            "similarity": round(float(mem.similarity), 4),
            "score": round(float(mem.score), 4),
            "importance": round(float(mem.importance), 4),
            "confidence": round(float(mem.confidence), 4),
            "raw_confidence": round(float(mem.raw_confidence), 4),
            "mem_type": mem.mem_type,
            "slot": mem.slot,
            "retrieval_weight": round(float(mem.retrieval_weight), 4),
            "mem_status": mem.mem_status,
            "scope": mem.scope,
            "sensitivity": mem.sensitivity,
            "review_status": mem.review_status,
            "source": mem.source,
            "created_at": mem.created_at,
            "last_accessed_at": mem.last_accessed_at,
            "observed_at": mem.observed_at,
            "valid_from": mem.valid_from,
            "valid_to": mem.valid_to,
            "is_current": mem.is_current,
            "retrieval_enabled": mem.retrieval_enabled,
            "user_hidden": mem.user_hidden,
            "pinned": mem.pinned,
        }

    @staticmethod
    def _scope_allowed(mem: RetrievedMemory, conversation_id: int | None) -> bool:
        if mem.scope in ("", "global", "topic", "task"):
            return True
        if mem.scope != "conversation":
            return False
        if conversation_id is None:
            return False
        return mem.source_conversation_id == str(conversation_id)

    @classmethod
    def _freshness_weight(cls, mem: RetrievedMemory) -> tuple[float, dict[str, Any]]:
        anchor = mem.observed_at or mem.valid_from or mem.created_at
        anchor_dt = _parse_datetime(anchor)
        if anchor_dt is None:
            return 0.95, {"freshness_anchor": "", "freshness_age_days": None}

        now = datetime.now(timezone.utc)
        age_days = max(0.0, (now - anchor_dt).total_seconds() / 86400.0)
        half_life = cls.FRESHNESS_HALF_LIFE_DAYS.get(mem.mem_type, cls.FRESHNESS_HALF_LIFE_DAYS["general"])
        floor = cls.FRESHNESS_FLOORS.get(mem.mem_type, cls.FRESHNESS_FLOORS["general"])
        decay = math.exp(-age_days / half_life)
        weight = floor + (1.0 - floor) * decay

        if age_days <= 7:
            recent_boost = 0.03 if mem.mem_type in {"fact", "preference"} else 0.06
            weight += recent_boost

        weight = max(0.5, min(weight, 1.08))
        return round(weight, 4), {
            "freshness_anchor": anchor,
            "freshness_age_days": round(age_days, 2),
            "freshness_half_life_days": half_life,
        }


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
