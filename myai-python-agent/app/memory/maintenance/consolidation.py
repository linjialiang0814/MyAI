from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Iterable

import numpy as np

from app.memory.model.mem_item import MemoryItem, utc_now_iso
from app.memory.model.mem_types import MemoryStatus
from app.memory.model.slot_registry import get_slot_definition, normalize_slot, normalize_value
from app.memory.store.chroma_store import ChromaMemoryStore


@dataclass
class ConsolidationAction:
    action: str
    memory_id: str
    kind: str
    evidence_memory_ids: list[str] = field(default_factory=list)
    reason: str = ""
    slot: str = ""
    policy: str = ""
    evidence_action: str = ""
    replaced_evidence_count: int = 0
    linked_evidence_count: int = 0


@dataclass
class ConsolidationReport:
    actions: list[ConsolidationAction] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return sum(1 for action in self.actions if action.action == "create_summary")

    def to_dict(self) -> dict:
        return {
            "created_count": self.created_count,
            "actions": [
                {
                    "action": action.action,
                    "memory_id": action.memory_id,
                    "kind": action.kind,
                    "evidence_memory_ids": action.evidence_memory_ids,
                    "reason": action.reason,
                    "slot": action.slot,
                    "policy": action.policy,
                    "evidence_action": action.evidence_action,
                    "replaced_evidence_count": action.replaced_evidence_count,
                    "linked_evidence_count": action.linked_evidence_count,
                }
                for action in self.actions
            ],
        }


class MemoryConsolidator:
    def __init__(
        self,
        memory_store: ChromaMemoryStore,
        *,
        min_repeated_observations: int = 2,
        min_preference_values: int = 2,
    ):
        self.memory_store = memory_store
        self.min_repeated_observations = min_repeated_observations
        self.min_preference_values = min_preference_values

    def consolidate_user(self, user_id: str) -> ConsolidationReport:
        memories = self.memory_store.get_all(user_id)
        self._repair_existing_summaries(user_id, memories)
        memories = self.memory_store.get_all(user_id)
        report = ConsolidationReport()
        existing_signatures = {
            str(mem.metadata.get("consolidation_signature", "") or "")
            for mem in memories
            if _blocks_consolidation_signature(mem)
        }

        report.actions.extend(
            self._consolidate_repeated_observations(user_id, memories, existing_signatures)
        )
        memories = self.memory_store.get_all(user_id)
        existing_signatures = {
            str(mem.metadata.get("consolidation_signature", "") or "")
            for mem in memories
            if _blocks_consolidation_signature(mem)
        }
        report.actions.extend(
            self._consolidate_long_term_preferences(user_id, memories, existing_signatures)
        )
        memories = self.memory_store.get_all(user_id)
        existing_signatures = {
            str(mem.metadata.get("consolidation_signature", "") or "")
            for mem in memories
            if _blocks_consolidation_signature(mem)
        }
        report.actions.extend(
            self._summarize_historical_facts(user_id, memories, existing_signatures)
        )
        return report

    def _consolidate_repeated_observations(
        self,
        user_id: str,
        memories: list[MemoryItem],
        existing_signatures: set[str],
    ) -> list[ConsolidationAction]:
        groups: dict[tuple[str, str, str], list[MemoryItem]] = {}
        for mem in memories:
            if not _eligible_evidence(mem) or _is_summary(mem):
                continue
            slot = normalize_slot(mem.mem_type, mem.metadata.get("slot"))
            value = normalize_value(str(mem.metadata.get("value", "") or ""))
            if not slot or not value:
                continue
            groups.setdefault((mem.mem_type, slot, value), []).append(mem)

        actions: list[ConsolidationAction] = []
        for (mem_type, slot, value), group in groups.items():
            if len(group) < self.min_repeated_observations:
                continue
            signature = f"repeated_observation:{mem_type}:{slot}:{value}"
            if signature in existing_signatures:
                continue
            policy = _consolidation_policy(mem_type, slot, default="replace_evidence")
            content = _summary_content(mem_type=mem_type, slot=slot, values=[value])
            summary = self._create_summary(
                user_id=user_id,
                content=content,
                mem_type=mem_type,
                kind="repeated_observation",
                signature=signature,
                evidence=group,
                slot=slot,
                value=value,
                reason=f"consolidated {len(group)} repeated observations for slot '{slot}'",
                policy=policy,
            )
            actions.append(
                ConsolidationAction(
                    action="create_summary",
                    memory_id=summary.memory_id,
                    kind="repeated_observation",
                    evidence_memory_ids=[mem.memory_id for mem in group],
                    reason=f"consolidated repeated {mem_type} memory",
                    slot=slot,
                    policy=policy,
                    evidence_action=_evidence_action(policy),
                    replaced_evidence_count=len(group) if policy == "replace_evidence" else 0,
                    linked_evidence_count=len(group),
                )
            )
        return actions

    def _consolidate_long_term_preferences(
        self,
        user_id: str,
        memories: list[MemoryItem],
        existing_signatures: set[str],
    ) -> list[ConsolidationAction]:
        groups: dict[str, list[MemoryItem]] = {}
        for mem in memories:
            if not _eligible_evidence(mem) or _is_summary(mem) or mem.mem_type != "preference":
                continue
            slot = normalize_slot(mem.mem_type, mem.metadata.get("slot"))
            if not slot:
                continue
            groups.setdefault(slot, []).append(mem)

        actions: list[ConsolidationAction] = []
        for slot, group in groups.items():
            values = sorted(
                {
                    normalize_value(str(mem.metadata.get("value", "") or "")) or mem.content
                    for mem in group
                }
            )
            if len(values) < self.min_preference_values:
                continue
            signature = f"long_term_preference:{slot}:{'|'.join(values)}"
            if signature in existing_signatures:
                continue
            policy = _consolidation_policy("preference", slot, default="coexist_with_evidence")
            summary = self._create_summary(
                user_id=user_id,
                content=_summary_content(mem_type="preference", slot=slot, values=values),
                mem_type="preference",
                kind="long_term_preference",
                signature=signature,
                evidence=group,
                slot=slot,
                value=", ".join(values),
                reason=f"consolidated {len(group)} long-term preference memories",
                policy=policy,
            )
            actions.append(
                ConsolidationAction(
                    action="create_summary",
                    memory_id=summary.memory_id,
                    kind="long_term_preference",
                    evidence_memory_ids=[mem.memory_id for mem in group],
                    reason="consolidated long-term preferences",
                    slot=slot,
                    policy=policy,
                    evidence_action=_evidence_action(policy),
                    replaced_evidence_count=len(group) if policy == "replace_evidence" else 0,
                    linked_evidence_count=len(group),
                )
            )
        return actions

    def _summarize_historical_facts(
        self,
        user_id: str,
        memories: list[MemoryItem],
        existing_signatures: set[str],
    ) -> list[ConsolidationAction]:
        groups: dict[str, list[MemoryItem]] = {}
        for mem in memories:
            if _is_summary(mem) or mem.mem_type != "fact":
                continue
            slot = normalize_slot(mem.mem_type, mem.metadata.get("slot"))
            if not slot:
                continue
            if _is_current(mem) and mem.status != MemoryStatus.ACTIVE.value:
                continue
            groups.setdefault(slot, []).append(mem)

        actions: list[ConsolidationAction] = []
        for slot, group in groups.items():
            historical = [mem for mem in group if not _is_current(mem) or mem.status != MemoryStatus.ACTIVE.value]
            current = [mem for mem in group if _is_current(mem) and mem.status == MemoryStatus.ACTIVE.value]
            if not historical or not current:
                continue
            ordered = sorted(group, key=lambda mem: str(mem.metadata.get("valid_from") or mem.created_at))
            values = [
                normalize_value(str(mem.metadata.get("value", "") or "")) or mem.content
                for mem in ordered
            ]
            signature = f"historical_fact_chain:{slot}:{'|'.join(values)}"
            if signature in existing_signatures:
                continue
            policy = "coexist_with_evidence"
            summary = self._create_summary(
                user_id=user_id,
                content=f"Historical {slot} history: " + " -> ".join(values),
                mem_type="fact",
                kind="historical_fact_chain",
                signature=signature,
                evidence=ordered,
                slot=slot,
                value=values[-1],
                reason=f"summarized {len(ordered)} historical fact states for slot '{slot}'",
                policy=policy,
            )
            actions.append(
                ConsolidationAction(
                    action="create_summary",
                    memory_id=summary.memory_id,
                    kind="historical_fact_chain",
                    evidence_memory_ids=[mem.memory_id for mem in ordered],
                    reason=f"summarized historical fact chain for slot '{slot}'",
                    slot=slot,
                    policy=policy,
                    evidence_action=_evidence_action(policy),
                    replaced_evidence_count=0,
                    linked_evidence_count=len(ordered),
                )
            )
        return actions

    def _create_summary(
        self,
        *,
        user_id: str,
        content: str,
        mem_type: str,
        kind: str,
        signature: str,
        evidence: list[MemoryItem],
        slot: str,
        value: str,
        reason: str,
        policy: str,
    ) -> MemoryItem:
        consolidated_at = utc_now_iso()
        evidence_ids = [mem.memory_id for mem in evidence]
        evidence_action = _evidence_action(policy)
        summary = MemoryItem(
            user_id=user_id,
            content=content,
            vector=_average_vectors(mem.vector for mem in evidence),
            mem_type=mem_type,
            score=min(1.0, max((mem.score for mem in evidence), default=0.8) + 0.05),
            importance=max((mem.importance for mem in evidence), default=1.0),
            metadata={
                "source": "memory_consolidation",
                "extraction_reason": reason,
                "confidence": max((float(mem.metadata.get("confidence", 0.8) or 0.8) for mem in evidence), default=0.8),
                "raw_confidence": max((float(mem.metadata.get("raw_confidence", 0.8) or 0.8) for mem in evidence), default=0.8),
                "calibrated_confidence": max(
                    (float(mem.metadata.get("calibrated_confidence", 0.8) or 0.8) for mem in evidence),
                    default=0.8,
                ),
                "scope": _common_value((mem.metadata.get("scope") for mem in evidence), default="global"),
                "sensitivity": _common_value((mem.metadata.get("sensitivity") for mem in evidence), default="personal"),
                "review_status": "accepted",
                "review_reason": "accepted by memory consolidation policy",
                "sensitive_category": _common_value(
                    (mem.metadata.get("sensitive_category") for mem in evidence),
                    default="none",
                ),
                "slot": slot,
                "value": value,
                "consolidation_summary": True,
                "consolidation_kind": kind,
                "consolidation_policy": policy,
                "consolidation_evidence_action": evidence_action,
                "consolidation_signature": signature,
                "consolidation_state": "pending",
                # A partially linked summary must never enter prompt context.
                # Repair promotes it only after every evidence record is linked.
                "retrieval_enabled": False,
                "consolidated_at": consolidated_at,
                "consolidated_count": len(evidence),
                "consolidated_from": json.dumps(evidence_ids, ensure_ascii=False),
                "consolidation_events": json.dumps(
                    [
                        {
                            "memory_id": mem.memory_id,
                            "content": mem.content,
                            "source": str(mem.metadata.get("source", "") or ""),
                            "observed_at": str(mem.metadata.get("observed_at", "") or ""),
                            "valid_from": str(mem.metadata.get("valid_from", "") or ""),
                            "valid_to": str(mem.metadata.get("valid_to", "") or ""),
                            "is_current": _is_current(mem),
                        }
                        for mem in evidence
                    ],
                    ensure_ascii=False,
                ),
                "observed_at": consolidated_at,
                "valid_from": consolidated_at,
                "valid_to": "",
                "is_current": True,
            },
        )
        self.memory_store.add_item(user_id, summary)
        for mem in evidence:
            self._apply_summary_to_evidence(
                mem,
                summary_id=summary.memory_id,
                consolidated_at=consolidated_at,
                policy=policy,
                evidence_action=evidence_action,
                kind=kind,
            )
            self.memory_store.update_memory(user_id, mem)
        summary.metadata["consolidation_state"] = "complete"
        summary.metadata["retrieval_enabled"] = True
        self.memory_store.update_memory(user_id, summary)
        return summary

    def _repair_existing_summaries(
        self,
        user_id: str,
        memories: list[MemoryItem],
    ) -> None:
        by_id = {memory.memory_id: memory for memory in memories}
        for summary in (memory for memory in memories if _is_summary(memory)):
            evidence_ids = _json_string_list(summary.metadata.get("consolidated_from"))
            if not evidence_ids:
                continue
            policy = str(summary.metadata.get("consolidation_policy") or "coexist_with_evidence")
            evidence_action = str(
                summary.metadata.get("consolidation_evidence_action")
                or _evidence_action(policy)
            )
            kind = str(summary.metadata.get("consolidation_kind") or "summary")
            consolidated_at = str(
                summary.metadata.get("consolidated_at")
                or summary.metadata.get("valid_from")
                or summary.created_at
            )
            missing = [memory_id for memory_id in evidence_ids if memory_id not in by_id]
            if missing:
                missing_json = json.dumps(missing)
                if (
                    summary.metadata.get("consolidation_state") != "degraded"
                    or summary.metadata.get("missing_evidence_ids") != missing_json
                    or bool(summary.metadata.get("retrieval_enabled"))
                ):
                    # Disable the incomplete summary before releasing evidence so
                    # an interrupted repair cannot leave it eligible for retrieval.
                    summary.metadata["consolidation_state"] = "degraded"
                    summary.metadata["missing_evidence_ids"] = missing_json
                    summary.metadata["retrieval_enabled"] = False
                    self.memory_store.update_memory(user_id, summary)
                for memory_id in evidence_ids:
                    evidence = by_id.get(memory_id)
                    if evidence is None:
                        continue
                    changed = self._release_degraded_summary_from_evidence(
                        evidence,
                        summary_id=summary.memory_id,
                        policy=policy,
                        kind=kind,
                    )
                    if changed:
                        self.memory_store.update_memory(user_id, evidence)
                target_state = "degraded"
                retrieval_enabled = False
            else:
                for memory_id in evidence_ids:
                    evidence = by_id[memory_id]
                    changed = self._apply_summary_to_evidence(
                        evidence,
                        summary_id=summary.memory_id,
                        consolidated_at=consolidated_at,
                        policy=policy,
                        evidence_action=evidence_action,
                        kind=kind,
                    )
                    if changed:
                        self.memory_store.update_memory(user_id, evidence)
                target_state = "complete"
                retrieval_enabled = True
            if (
                summary.metadata.get("consolidation_state") != target_state
                or summary.metadata.get("missing_evidence_ids") != json.dumps(missing)
                or bool(summary.metadata.get("retrieval_enabled")) != retrieval_enabled
            ):
                summary.metadata["consolidation_state"] = target_state
                summary.metadata["missing_evidence_ids"] = json.dumps(missing)
                summary.metadata["retrieval_enabled"] = retrieval_enabled
                self.memory_store.update_memory(user_id, summary)

    @staticmethod
    def _release_degraded_summary_from_evidence(
        memory: MemoryItem,
        *,
        summary_id: str,
        policy: str,
        kind: str,
    ) -> bool:
        if str(memory.metadata.get("consolidated_into") or "") != summary_id:
            return False
        before = (
            memory.status,
            str(memory.metadata.get("consolidated_into") or ""),
            str(memory.metadata.get("consolidated_at") or ""),
            str(memory.metadata.get("consolidation_policy") or ""),
            str(memory.metadata.get("consolidation_evidence_action") or ""),
            str(memory.metadata.get("is_current", "")),
            str(memory.metadata.get("valid_to") or ""),
            str(memory.metadata.get("historical_reason") or ""),
        )
        memory.metadata["consolidated_into"] = ""
        memory.metadata["consolidated_at"] = ""
        memory.metadata["consolidation_policy"] = ""
        memory.metadata["consolidation_evidence_action"] = ""
        memory.metadata["consolidation_released_from"] = summary_id
        memory.metadata["consolidation_release_reason"] = "summary_degraded_missing_evidence"
        memory.metadata["consolidation_released_at"] = utc_now_iso()
        if policy == "replace_evidence" and memory.status == MemoryStatus.SUPERSEDED.value:
            memory.status = MemoryStatus.ACTIVE.value
            memory.metadata["is_current"] = True
            memory.metadata["valid_to"] = ""
            memory.metadata["historical_reason"] = f"released from degraded {kind} summary"
        after = (
            memory.status,
            str(memory.metadata.get("consolidated_into") or ""),
            str(memory.metadata.get("consolidated_at") or ""),
            str(memory.metadata.get("consolidation_policy") or ""),
            str(memory.metadata.get("consolidation_evidence_action") or ""),
            str(memory.metadata.get("is_current", "")),
            str(memory.metadata.get("valid_to") or ""),
            str(memory.metadata.get("historical_reason") or ""),
        )
        return before != after

    @staticmethod
    def _apply_summary_to_evidence(
        memory: MemoryItem,
        *,
        summary_id: str,
        consolidated_at: str,
        policy: str,
        evidence_action: str,
        kind: str,
    ) -> bool:
        before = (
            memory.status,
            str(memory.metadata.get("consolidated_into") or ""),
            str(memory.metadata.get("consolidated_at") or ""),
            str(memory.metadata.get("consolidation_policy") or ""),
            str(memory.metadata.get("consolidation_evidence_action") or ""),
            str(memory.metadata.get("is_current", "")),
            str(memory.metadata.get("valid_to") or ""),
        )
        memory.metadata["consolidated_into"] = summary_id
        memory.metadata["consolidated_at"] = consolidated_at
        memory.metadata["consolidation_policy"] = policy
        memory.metadata["consolidation_evidence_action"] = evidence_action
        if policy == "replace_evidence" and memory.status == MemoryStatus.ACTIVE.value and _is_current(memory):
            memory.status = MemoryStatus.SUPERSEDED.value
            memory.metadata["is_current"] = False
            memory.metadata["valid_to"] = consolidated_at
            memory.metadata["historical_reason"] = f"consolidated into {kind} summary"
        after = (
            memory.status,
            str(memory.metadata.get("consolidated_into") or ""),
            str(memory.metadata.get("consolidated_at") or ""),
            str(memory.metadata.get("consolidation_policy") or ""),
            str(memory.metadata.get("consolidation_evidence_action") or ""),
            str(memory.metadata.get("is_current", "")),
            str(memory.metadata.get("valid_to") or ""),
        )
        return before != after


def _eligible_evidence(mem: MemoryItem) -> bool:
    return (
        mem.status == MemoryStatus.ACTIVE.value
        and _is_current(mem)
        and str(mem.metadata.get("review_status", "accepted") or "accepted") == "accepted"
        and str(mem.metadata.get("sensitivity", "normal") or "normal") != "sensitive"
    )


def _json_string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _is_summary(mem: MemoryItem) -> bool:
    value = mem.metadata.get("consolidation_summary", False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _blocks_consolidation_signature(mem: MemoryItem) -> bool:
    if not _is_summary(mem):
        return False
    return str(mem.metadata.get("consolidation_state") or "complete") != "degraded"


def _is_current(mem: MemoryItem) -> bool:
    value = mem.metadata.get("is_current", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"", "1", "true", "yes", "on"}
    return bool(value)


def _consolidation_policy(mem_type: str, slot: str, *, default: str) -> str:
    policy = get_slot_definition(mem_type, slot).consolidation_policy or default
    if policy not in {"replace_evidence", "coexist_with_evidence"}:
        return default
    return policy


def _evidence_action(policy: str) -> str:
    if policy == "replace_evidence":
        return "supersede_evidence"
    return "link_evidence_only"


def _average_vectors(vectors: Iterable[np.ndarray]) -> np.ndarray:
    arrays = [np.array(vector, dtype=np.float32) for vector in vectors if len(vector) > 0]
    if not arrays:
        return np.array([], dtype=np.float32)
    return np.mean(arrays, axis=0).astype(np.float32)


def _common_value(values: Iterable, *, default: str) -> str:
    normalized = [str(value) for value in values if value not in (None, "")]
    if not normalized:
        return default
    first = normalized[0]
    if all(value == first for value in normalized):
        return first
    return default


def _summary_content(*, mem_type: str, slot: str, values: list[str]) -> str:
    if mem_type == "preference":
        return f"Consolidated preference {slot}: " + ", ".join(values)
    return f"Consolidated {mem_type} {slot}: " + ", ".join(values)
