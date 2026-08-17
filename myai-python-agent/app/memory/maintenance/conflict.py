from app.memory.maintenance.dedup import ResolutionResult
from app.memory.store.in_mem_store import MemoryStore
from app.memory.store.chroma_store import ChromaMemoryStore
from app.memory.model.mem_item import MemoryItem, utc_now_iso
from app.memory.model.mem_types import MemoryStatus
from app.memory.model.slot_registry import get_slot_definition, normalize_slot, normalize_value

class MemoryConflictResolver:
    """
    the same slot but different value, then conflict
    supersede old, active new
    """

    def __init__(self, memory_store: ChromaMemoryStore):
        self.memory_store = memory_store

    def resolve(self, user_id: str, new_memory: MemoryItem) -> ResolutionResult:
        new_slot = normalize_slot(new_memory.mem_type, new_memory.metadata.get("slot"))
        definition = get_slot_definition(new_memory.mem_type, new_slot)
        update_intent = str(new_memory.metadata.get("update_intent", "") or "")
        if update_intent == "negation" and definition.cardinality == "multi":
            result = self._resolve_multi_value_negation(user_id, new_memory, new_slot)
            if result.action != "add":
                return result

        if definition.conflict_policy == "coexist":
            return ResolutionResult("add", reason=f"slot '{new_slot}' allows coexistence")
        if definition.conflict_policy == "append":
            return ResolutionResult("add", reason=f"slot '{new_slot}' appends values")
        if definition.conflict_policy == "pending":
            new_memory.metadata["review_status"] = "pending"
            new_memory.metadata["review_reason"] = f"pending because slot '{new_slot}' requires review"
            return ResolutionResult("add", reason=f"slot '{new_slot}' requires review")

        new_value = normalize_value(str(new_memory.metadata.get("value", "")))
        if not new_slot or not new_value:
            return ResolutionResult("add", reason="not applicable")

        existing = self.memory_store.get_all(user_id)
        for mem in existing:
            old_slot = normalize_slot(mem.mem_type, mem.metadata.get("slot"))
            old_value = normalize_value(str(mem.metadata.get("value","")))
            if (
                mem.mem_type == new_memory.mem_type
                and old_slot == new_slot
                and old_value
                and old_value != new_value
                and _is_current(mem)
            ):
                changed_at = utc_now_iso()
                mem.status = MemoryStatus.SUPERSEDED.value
                mem.metadata["superseded_by"] = new_memory.memory_id
                mem.metadata["superseded_at"] = changed_at
                mem.metadata["valid_to"] = changed_at
                mem.metadata["is_current"] = False
                if update_intent == "correction":
                    mem.metadata["historical_reason"] = f"corrected by newer value for slot '{new_slot}'"
                    new_memory.metadata["correction_applied"] = True
                else:
                    mem.metadata["historical_reason"] = f"replaced by newer value for slot '{new_slot}'"
                new_memory.metadata.setdefault("observed_at", changed_at)
                new_memory.metadata.setdefault("valid_from", changed_at)
                new_memory.metadata.setdefault("valid_to", "")
                new_memory.metadata["is_current"] = True
                new_memory.metadata["previous_memory_id"] = mem.memory_id
                reason_prefix = "correction" if update_intent == "correction" else "conflict"
                return ResolutionResult(
                    "supersede",
                    mem.memory_id,
                    reason=f"{reason_prefix} on slot '{new_slot}'",
                    target_memory=mem,
                )

        return ResolutionResult("add", reason = "no conflict found")

    def _resolve_multi_value_negation(
        self,
        user_id: str,
        new_memory: MemoryItem,
        new_slot: str,
    ) -> ResolutionResult:
        new_value = normalize_value(str(new_memory.metadata.get("value", "")))
        if not new_slot or not new_value:
            return ResolutionResult("add", reason="negation missing slot or value")

        changed_at = utc_now_iso()
        existing = self.memory_store.get_all(user_id)
        for mem in existing:
            old_slot = normalize_slot(mem.mem_type, mem.metadata.get("slot"))
            old_value = normalize_value(str(mem.metadata.get("value", "")))
            if (
                mem.mem_type == new_memory.mem_type
                and old_slot == new_slot
                and old_value == new_value
                and _is_current(mem)
            ):
                mem.status = MemoryStatus.SUPERSEDED.value
                mem.metadata["superseded_at"] = changed_at
                mem.metadata["valid_to"] = changed_at
                mem.metadata["is_current"] = False
                mem.metadata["historical_reason"] = f"negated by user for slot '{new_slot}'"
                mem.metadata["negated_by_content"] = new_memory.content
                new_memory.metadata["negation_applied"] = True
                new_memory.metadata["negated_memory_id"] = mem.memory_id
                self.memory_store.update_memory(user_id, mem)
                return ResolutionResult("negate", mem.memory_id, reason=f"negated value for slot '{new_slot}'")

        new_memory.metadata["review_status"] = "pending"
        new_memory.metadata["review_reason"] = f"pending because negation found no existing value for slot '{new_slot}'"
        return ResolutionResult("add", reason=f"negation found no existing value for slot '{new_slot}'")


def _is_current(memory: MemoryItem) -> bool:
    value = memory.metadata.get("is_current", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"", "1", "true", "yes", "on"}
    return bool(value)

