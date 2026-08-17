from __future__ import annotations

from functools import wraps
from threading import Lock, RLock
from typing import List, Optional
from uuid import uuid4

from app.memory.model.mem_item import MemoryItem, utc_now_iso
from app.memory.model.mem_types import MemoryStatus, MemoryType
from app.memory.store.in_mem_store import MemoryStore
from app.memory.store.chroma_store import ChromaMemoryStore
from app.memory.writer.extractor import MemoryToWrite
from app.memory.writer.smart_writer import SmartMemoryWriter, build_memory_writer
from app.memory.retrieval.retriever import MemoryRetriever,RetrievedMemory
from app.memory.retrieval.policy import MemoryPolicy
from app.memory.maintenance.decay import MemoryDecay
from app.memory.maintenance.consolidation import MemoryConsolidator
from app.memory.maintenance.dedup import MemoryDeduplicator
from app.memory.maintenance.conflict import MemoryConflictResolver
from app.memory.settings import MemorySettingsStore
from app.runtime.resilience import Deadline
from app.memory.governance import (
    build_source_ref,
    calibrate_confidence,
    classify_review_status,
    infer_sensitive_category,
    infer_sensitivity,
    normalize_governance_metadata,
)


def _per_user_synchronized(method):
    @wraps(method)
    def wrapper(self, user_id, *args, **kwargs):
        with self._lock_for_user(str(user_id)):
            return method(self, user_id, *args, **kwargs)

    return wrapper

class MemoryService:
    def __init__(
        self,
        embedding_client,
        memory_store: Optional[ChromaMemoryStore] = None,
        writer: SmartMemoryWriter | None = None,
        settings_store: MemorySettingsStore | None = None,
    ):
        self.embedding_client = embedding_client
        self.memory_store = memory_store if memory_store is not None else ChromaMemoryStore()
        self.writer = writer if writer is not None else build_memory_writer()
        self.retriever = MemoryRetriever(self.memory_store, top_k=12)
        self.policy = MemoryPolicy()
        self.decay = MemoryDecay(memory_store=self.memory_store)
        self.consolidator = MemoryConsolidator(self.memory_store)
        self.deduplicator = MemoryDeduplicator(self.memory_store)
        self.conflict_resolver = MemoryConflictResolver(self.memory_store)
        self.settings_store = settings_store if settings_store is not None else MemorySettingsStore()
        self._user_locks: dict[str, RLock] = {}
        self._user_locks_guard = Lock()

    def _lock_for_user(self, user_id: str) -> RLock:
        normalized = str(user_id)
        with self._user_locks_guard:
            return self._user_locks.setdefault(normalized, RLock())

    @_per_user_synchronized
    def process_user_input(
        self,
        user_id: str,
        text: str,
        *,
        conversation_id: int | None = None,
        message_id: int | str | None = None,
        source: str = "user_explicit",
        allow_unstructured_manual_write: bool = False,
    ) -> dict:
        settings = self.settings_store.get(user_id)
        if not settings.memory_enabled:
            return {"written": False, "reason": "memory disabled by user settings"}
        if not settings.auto_write_enabled:
            return {"written": False, "reason": "automatic memory write disabled by user settings"}
        candidates = self.writer.extract_candidates(text)
        if not candidates:
            if allow_unstructured_manual_write and source == "user_explicit":
                candidate = self._build_unstructured_manual_candidate(text)
                if candidate:
                    candidates = [candidate]
            if not candidates:
                return {"written": False, "reason": "writer rejected input"}

        candidate_count = len(candidates)
        extraction_batch_id = str(uuid4()) if candidate_count > 1 else ""
        results = [
            self._process_candidate(
                user_id,
                candidate,
                candidate_index=index,
                candidate_count=candidate_count,
                extraction_batch_id=extraction_batch_id,
                conversation_id=conversation_id,
                message_id=message_id,
                source=source,
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
        first = results[0]
        response = {
            "written": any(result.get("written") for result in results),
            "written_count": sum(1 for result in results if result.get("written")),
            "candidate_count": len(candidates),
            "results": results,
        }
        response.update(first)
        return response

    def try_process_user_input(self, user_id: str, text: str, **kwargs) -> dict:
        lock = self._lock_for_user(str(user_id))
        if not lock.acquire(blocking=False):
            return {
                "written": False,
                "deferred": True,
                "reason": "memory operation busy; skipped to protect request latency",
            }
        try:
            return self.process_user_input(user_id, text, **kwargs)
        finally:
            lock.release()

    def _build_unstructured_manual_candidate(self, text: str) -> MemoryToWrite | None:
        content = " ".join((text or "").strip().split())
        if len(content) < 2:
            return None
        return MemoryToWrite(
            content=content,
            mem_type=MemoryType.GENERAL.value,
            importance=3,
            confidence=0.72,
            canonical_key="manual_note",
            canonical_value=content,
            metadata={
                "slot": "manual_note",
                "value": content,
                "extraction_method": "manual",
                "extraction_reason": "explicit manual memory write fallback",
            },
        )

    @_per_user_synchronized
    def process_task_outcome(
        self,
        user_id: str,
        content: str,
        *,
        task_run_id: str,
        step_id: str | None = None,
        mem_type: str = MemoryType.DECISION.value,
        slot: str = "task_experience",
        confidence: float = 0.62,
        importance: float = 3.0,
        metadata: dict | None = None,
    ) -> dict:
        settings = self.settings_store.get(user_id)
        if not settings.memory_enabled:
            return {"written": False, "reason": "memory disabled by user settings"}
        if not settings.auto_write_enabled:
            return {"written": False, "reason": "automatic memory write disabled by user settings"}
        candidate_metadata = {
            "slot": slot,
            "value": content,
            "review_status": "pending",
            "review_reason": "pending because task outcome memories are inferred",
            "extraction_method": "task_outcome",
            "extraction_reason": "derived from completed task execution",
        }
        candidate_metadata.update(metadata or {})
        candidate = MemoryToWrite(
            content=content,
            mem_type=mem_type,
            importance=importance,
            confidence=confidence,
            metadata=candidate_metadata,
            canonical_key=slot,
            canonical_value=content,
        )
        return self._process_candidate(
            user_id,
            candidate,
            candidate_index=1,
            candidate_count=1,
            extraction_batch_id="",
            conversation_id=None,
            message_id=None,
            source="task_outcome",
            task_run_id=task_run_id,
            step_id=step_id,
        )

    def try_process_task_outcome(self, user_id: str, content: str, **kwargs) -> dict:
        lock = self._lock_for_user(str(user_id))
        if not lock.acquire(blocking=False):
            return {
                "written": False,
                "deferred": True,
                "reason": "memory operation busy; task outcome write skipped",
            }
        try:
            return self.process_task_outcome(user_id, content, **kwargs)
        finally:
            lock.release()

    def _process_candidate(
        self,
        user_id: str,
        candidate: MemoryToWrite,
        *,
        candidate_index: int,
        candidate_count: int,
        extraction_batch_id: str,
        conversation_id: int | None,
        message_id: int | str | None,
        source: str,
        task_run_id: str | None = None,
        step_id: str | None = None,
    ) -> dict:
        vector = self.embedding_client.embed(candidate.content)
        base_metadata = dict(candidate.metadata or {})
        if candidate_count > 1:
            base_metadata.update(
                {
                    "extraction_batch_id": extraction_batch_id,
                    "candidate_index": candidate_index,
                    "candidate_count": candidate_count,
                    "multi_candidate": True,
                }
            )
        governance_metadata = normalize_governance_metadata(
            base_metadata=base_metadata,
            content=candidate.content,
            mem_type=candidate.mem_type,
            confidence=candidate.confidence,
            source=source,
            source_ref=build_source_ref(
                conversation_id=conversation_id,
                message_id=message_id,
                task_run_id=task_run_id,
                step_id=step_id,
            ),
            importance=float(candidate.importance),
        )
        governance_metadata.update(
            {
                "canonical_key": candidate.canonical_key or "",
                "canonical_value": candidate.canonical_value or "",
            }
        )
        settings = self.settings_store.get(user_id)
        if settings.sensitive_requires_confirmation and governance_metadata.get("review_status") == "accepted":
            sensitivity = str(governance_metadata.get("sensitivity", "") or "")
            if sensitivity == "sensitive":
                governance_metadata["review_status"] = "pending"
                governance_metadata["review_reason"] = "pending because user settings require sensitive confirmation"
        memory = MemoryItem(
            user_id=user_id,
            content=candidate.content,
            vector=vector,
            mem_type=candidate.mem_type,
            score=0.90,
            importance=float(candidate.importance),
            metadata=governance_metadata,
        )

        dedup_result = self.deduplicator.resolve(user_id, memory)
        if dedup_result.action == "merge":
            return {
                "written": True,
                "action": "merge",
                "target_memory_id": dedup_result.target_memory_id,
                "reason": dedup_result.reason,
                "governance": governance_metadata,
            }

        conflict_result = self.conflict_resolver.resolve(user_id, memory)
        if conflict_result.action == "negate":
            return {
                "written": True,
                "action": "negate",
                "target_memory_id": conflict_result.target_memory_id,
                "reason": conflict_result.reason,
                "governance": governance_metadata,
            }
        self.memory_store.add_item(user_id, memory)
        if conflict_result.action == "supersede" and conflict_result.target_memory is not None:
            try:
                self.memory_store.update_memory(user_id, conflict_result.target_memory)
            except Exception:
                # Chroma has no multi-record transaction. Compensate by removing
                # the new value so the prior current fact remains authoritative.
                try:
                    self.memory_store.delete_by_id(user_id, memory.memory_id)
                except Exception:
                    pass
                raise
        return {
            "written": True,
            "action": conflict_result.action if conflict_result.action != "add" else "add",
            "memory_id": memory.memory_id,
            "reason": conflict_result.reason,
            "governance": governance_metadata,
        }

    @_per_user_synchronized
    def retrieve_for_context(
        self,
        user_id: str,
        query_text: str,
        *,
        conversation_id: int | None = None,
        include_sensitive: bool = False,
        ) -> List[RetrievedMemory]:
        if not self.settings_store.get(user_id).memory_enabled:
            return []
        query_vec = self.embedding_client.embed(query_text)
        retrieved = self.retriever.retrieve(user_id, query_vec, query_text=query_text)
        selected = self.policy.filter_memories(
            retrieved,
            conversation_id=conversation_id,
            include_sensitive=include_sensitive,
        )
        for memory in selected:
            self.memory_store.touch_memory(user_id, memory.memory_id, score=min(memory.score + 0.08, 1.0))
        return selected

    @_per_user_synchronized
    def retrieve_for_context_with_explanation(
        self,
        user_id: str,
        query_text: str,
        *,
        conversation_id: int | None = None,
        include_sensitive: bool = False,
    ) -> tuple[List[RetrievedMemory], list[dict]]:
        if not self.settings_store.get(user_id).memory_enabled:
            return [], []
        query_vec = self.embedding_client.embed(query_text)
        retrieved = self.retriever.retrieve(user_id, query_vec, query_text=query_text)
        decisions = self.policy.explain_memories(
            retrieved,
            conversation_id=conversation_id,
            include_sensitive=include_sensitive,
        )
        selected = [decision.memory for decision in decisions if decision.selected]
        for memory in selected:
            self.memory_store.touch_memory(user_id, memory.memory_id, score=min(memory.score + 0.08, 1.0))
        explanations = [
            {
                "memory_id": decision.memory.memory_id,
                "content": decision.memory.content,
                "selected": decision.selected,
                "reason": decision.reason,
                "final_score": round(float(decision.final_score), 4),
                "factors": decision.factors,
            }
            for decision in decisions
        ]
        return selected, explanations

    def try_retrieve_for_context_with_explanation(
        self,
        user_id: str,
        query_text: str,
        **kwargs,
    ) -> tuple[List[RetrievedMemory], list[dict]]:
        lock = self._lock_for_user(str(user_id))
        if not lock.acquire(blocking=False):
            return [], [
                {
                    "memory_id": "",
                    "content": "",
                    "selected": False,
                    "reason": "memory operation busy; retrieval skipped to protect request latency",
                    "final_score": 0.0,
                    "factors": {"deferred": True},
                }
            ]
        try:
            return self.retrieve_for_context_with_explanation(user_id, query_text, **kwargs)
        finally:
            lock.release()

    @_per_user_synchronized
    def maintenance(self, user_id: str, *, deadline: Deadline | None = None):
        return self._maintenance_unlocked(user_id, deadline=deadline)

    def try_maintenance(self, user_id: str, *, deadline: Deadline | None = None) -> dict:
        """Run only when the user's foreground memory path is idle."""
        lock = self._lock_for_user(str(user_id))
        if not lock.acquire(blocking=False):
            return {"deferred": True, "reason": "foreground memory operation active"}
        try:
            return self._maintenance_unlocked(user_id, deadline=deadline)
        finally:
            lock.release()

    def _maintenance_unlocked(self, user_id: str, *, deadline: Deadline | None = None) -> dict:
        if deadline is not None:
            deadline.raise_if_expired(operation="memory.maintenance.consolidation")
        consolidation_report = self.consolidator.consolidate_user(user_id)
        if deadline is not None:
            deadline.raise_if_expired(operation="memory.maintenance.consolidation")
        decayed = self.decay.apply_decay_by_user(user_id)
        if deadline is not None:
            deadline.raise_if_expired(operation="memory.maintenance.decay")
        return {
            "consolidation": consolidation_report.to_dict(),
            "memory_count": len(decayed),
        }

    @_per_user_synchronized
    def list_memories(self, user_id: str, mem_type: str | None = None) -> List[MemoryItem]:
        memories = self.memory_store.get_all(user_id)
        filtered = [mem for mem in memories if mem.status != "deleted"]
        if mem_type:
            filtered = [mem for mem in filtered if mem.mem_type == mem_type]
        filtered.sort(key=lambda mem: mem.created_at, reverse=True)
        return filtered

    @_per_user_synchronized
    def list_pending_memories(self, user_id: str) -> List[MemoryItem]:
        memories = self.list_memories(user_id)
        return [
            mem for mem in memories
            if mem.metadata.get("review_status") == "pending"
        ]

    @_per_user_synchronized
    def update_review_status(self, user_id: str, memory_id: str, review_status: str) -> MemoryItem | None:
        if review_status not in {"accepted", "rejected", "pending"}:
            raise ValueError(f"unsupported review_status: {review_status}")
        memory = self.memory_store.get_by_id(user_id, memory_id)
        if not memory or memory.status == "deleted":
            return None

        if review_status == "accepted" and infer_sensitive_category(memory.content) == "secret":
            memory.metadata["review_status"] = "rejected"
            memory.metadata["review_reason"] = "rejected because memory appears to contain a secret"
            self.memory_store.update_memory(user_id, memory)
            raise ValueError("secret memories cannot be accepted")
        memory.metadata["review_status"] = review_status
        if review_status == "accepted":
            memory.metadata.setdefault("review_decision", "user_accepted")
        elif review_status == "rejected":
            memory.metadata.setdefault("review_decision", "user_rejected")
        self.memory_store.update_memory(user_id, memory)
        return memory

    @_per_user_synchronized
    def edit_memory(
        self,
        user_id: str,
        memory_id: str,
        *,
        content: str | None = None,
        mem_type: str | None = None,
        scope: str | None = None,
        sensitivity: str | None = None,
        importance: float | None = None,
        retrieval_enabled: bool | None = None,
        pinned: bool | None = None,
        user_hidden: bool | None = None,
        user_locked: bool | None = None,
        is_current: bool | None = None,
        user_control_reason: str | None = None,
    ) -> MemoryItem | None:
        memory = self.memory_store.get_by_id(user_id, memory_id)
        if not memory or memory.status == "deleted":
            return None

        governance_edit = any(
            value is not None
            for value in (content, mem_type, scope, sensitivity, importance)
        )

        if mem_type is not None:
            allowed_types = {item.value for item in MemoryType}
            if mem_type not in allowed_types:
                raise ValueError(f"unsupported mem_type: {mem_type}")
            memory.mem_type = mem_type

        if content is not None:
            normalized_content = content.strip()
            if not normalized_content:
                raise ValueError("content cannot be blank")
            if normalized_content != memory.content:
                memory.metadata.setdefault("original_content", memory.content)
                memory.content = normalized_content
                memory.vector = self.embedding_client.embed(normalized_content)

        if importance is not None:
            memory.importance = float(importance)
            memory.metadata["importance"] = float(importance)

        if retrieval_enabled is not None:
            memory.metadata["retrieval_enabled"] = bool(retrieval_enabled)

        if pinned is not None:
            memory.metadata["pinned"] = bool(pinned)

        if user_hidden is not None:
            memory.metadata["user_hidden"] = bool(user_hidden)

        if user_locked is not None:
            memory.metadata["user_locked"] = bool(user_locked)

        if is_current is not None:
            memory.metadata["is_current"] = bool(is_current)
            if is_current:
                memory.metadata["valid_to"] = ""
                if memory.status == MemoryStatus.SUPERSEDED.value:
                    memory.status = MemoryStatus.ACTIVE.value
            else:
                memory.metadata["valid_to"] = utc_now_iso()
                memory.metadata.setdefault("historical_reason", "marked historical by user")

        if user_control_reason is not None:
            reason = user_control_reason.strip()
            if reason:
                memory.metadata["user_control_reason"] = reason
            else:
                memory.metadata.pop("user_control_reason", None)

        if not governance_edit:
            self.memory_store.update_memory(user_id, memory)
            return memory

        if scope is not None:
            if scope not in {"global", "conversation"}:
                raise ValueError(f"unsupported scope: {scope}")
            memory.metadata["scope"] = scope

        if sensitivity is not None:
            if sensitivity not in {"normal", "personal", "sensitive"}:
                raise ValueError(f"unsupported sensitivity: {sensitivity}")
            memory.metadata["sensitivity"] = sensitivity
        else:
            memory.metadata["sensitivity"] = infer_sensitivity(memory.content, memory.mem_type)

        sensitive_category = infer_sensitive_category(memory.content)
        memory.metadata["sensitive_category"] = sensitive_category
        if sensitive_category != "none":
            memory.metadata["sensitivity"] = "sensitive"
        memory.metadata["edited_before_accept"] = True
        memory.metadata["last_edited_at"] = utc_now_iso()

        if sensitive_category == "secret":
            memory.metadata["review_status"] = "rejected"
            memory.metadata["review_reason"] = "rejected because memory appears to contain a secret"
        else:
            raw_confidence = float(memory.metadata.get("raw_confidence", memory.metadata.get("confidence", 1.0)) or 1.0)
            source = str(memory.metadata.get("source") or "")
            calibrated_confidence, calibration_reason, calibration_factors = calibrate_confidence(
                raw_confidence=raw_confidence,
                mem_type=memory.mem_type,
                metadata=memory.metadata,
                source=source,
            )
            memory.metadata["raw_confidence"] = raw_confidence
            memory.metadata["calibrated_confidence"] = calibrated_confidence
            memory.metadata["confidence_calibration_reason"] = calibration_reason
            memory.metadata["confidence_calibration_factors"] = calibration_factors
            status, reason = classify_review_status(
                content=memory.content,
                mem_type=memory.mem_type,
                confidence=calibrated_confidence,
                importance=float(memory.importance),
                sensitivity=str(memory.metadata.get("sensitivity") or ""),
                candidate_count=int(memory.metadata.get("candidate_count") or 1),
                confidence_threshold=float(memory.metadata.get("slot_review_confidence_threshold") or 0.7),
                multi_candidate_confidence_threshold=float(
                    memory.metadata.get("slot_multi_candidate_confidence_threshold") or 0.85
                ),
                low_importance_review_threshold=_optional_float(
                    memory.metadata.get("slot_low_importance_review_threshold")
                ),
            )
            current_status = memory.metadata.get("review_status")
            if current_status == "rejected":
                memory.metadata["review_status"] = "pending"
                memory.metadata["review_reason"] = "pending after user edit"
            elif current_status in (None, "", "accepted"):
                memory.metadata["review_status"] = status
                memory.metadata["review_reason"] = reason
            else:
                memory.metadata["review_status"] = "pending"
                memory.metadata["review_reason"] = "pending after user edit"

        self.memory_store.update_memory(user_id, memory)
        return memory

    @_per_user_synchronized
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        return self.memory_store.delete_by_id(user_id, memory_id)

    def print_memories(self, user_id: str):
        memories = self.memory_store.get_all(user_id)
        for mem in memories:
            print(mem)


def _optional_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
