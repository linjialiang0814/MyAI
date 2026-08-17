from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import time
from typing import Any

from app.memory.mem_service import MemoryService
from app.memory.model.mem_item import MemoryItem
from app.memory.retrieval.retriever import MemoryRetriever
from app.memory.settings import MemorySettingsStore
from app.memory.store.in_mem_store import MemoryStore
from app.memory.writer.extractor import MemoryToWrite


class FrozenCandidateWriter:
    """Returns committed candidates so the experiment isolates governance."""

    def __init__(self, candidates_by_input: dict[str, list[MemoryToWrite]]):
        self.candidates_by_input = {key: list(value) for key, value in candidates_by_input.items()}

    def extract_candidates(self, text: str) -> list[MemoryToWrite]:
        candidates = self.candidates_by_input.get(text, [])
        if not candidates:
            return []
        candidate = candidates.pop(0)
        return [replace(candidate, metadata=dict(candidate.metadata))]


def retrieve_memory_evidence(
    *,
    variant: str,
    case: dict[str, Any],
    embedding_client,
    top_k: int,
    settings_dir: Path,
) -> dict[str, Any]:
    if variant == "none":
        return {
            "variant": variant,
            "evidence": [],
            "write_latency_ms": 0.0,
            "retrieval_latency_ms": 0.0,
            "write_results": [],
            "explanations": [],
            "candidate_count": 0,
            "selected_count": 0,
        }
    if variant not in {"basic", "governed"}:
        raise ValueError(f"Unsupported memory variant: {variant}")

    store = MemoryStore()
    user_id = f"thesis-{variant}-{case['id']}"
    observations = list(case.get("observations") or [])
    write_started = time.perf_counter()
    if variant == "basic":
        write_results = _write_basic(store, user_id, observations, embedding_client)
        write_latency_ms = _elapsed_ms(write_started)
        retrieval_started = time.perf_counter()
        query_vector = embedding_client.embed(str(case["query"]))
        retrieved = MemoryRetriever(store, top_k=top_k).retrieve(user_id, query_vector, query_text=None)
        retrieval_latency_ms = _elapsed_ms(retrieval_started)
        evidence = [_evidence_payload(store, user_id, item, rank) for rank, item in enumerate(retrieved, start=1)]
        return {
            "variant": variant,
            "evidence": evidence,
            "write_latency_ms": write_latency_ms,
            "retrieval_latency_ms": retrieval_latency_ms,
            "write_results": write_results,
            "explanations": [],
            "candidate_count": len(retrieved),
            "selected_count": len(evidence),
        }

    writer = FrozenCandidateWriter(_candidate_map(observations))
    service = MemoryService(
        embedding_client=embedding_client,
        memory_store=store,
        writer=writer,
        settings_store=MemorySettingsStore(settings_dir),
    )
    write_results = []
    for observation in observations:
        write_results.append(
            service.process_user_input(
                user_id,
                str(observation["content"]),
                conversation_id=observation.get("conversation_id"),
                source=str(observation.get("source") or "user_explicit"),
            )
        )
    write_latency_ms = _elapsed_ms(write_started)
    retrieval_started = time.perf_counter()
    retrieved, explanations = service.retrieve_for_context_with_explanation(
        user_id,
        str(case["query"]),
        conversation_id=case.get("conversation_id"),
    )
    retrieval_latency_ms = _elapsed_ms(retrieval_started)
    evidence = [_evidence_payload(store, user_id, item, rank) for rank, item in enumerate(retrieved, start=1)]
    return {
        "variant": variant,
        "evidence": evidence,
        "write_latency_ms": write_latency_ms,
        "retrieval_latency_ms": retrieval_latency_ms,
        "write_results": write_results,
        "explanations": explanations,
        "candidate_count": len(explanations),
        "selected_count": len(evidence),
    }


def build_memory_prompt(case: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    lines = [
        "This is a controlled memory benchmark.",
        "Answer only from the MEMORY EVIDENCE below.",
        "If the evidence does not contain a permitted answer, reply exactly UNKNOWN.",
        "Return only the short answer without explanation.",
        "",
        f"QUESTION: {case['query']}",
        "MEMORY EVIDENCE:",
    ]
    if evidence:
        lines.extend(f"[M{index}] {item['content']}" for index, item in enumerate(evidence, start=1))
    else:
        lines.append("(none)")
    return "\n".join(lines)


def _write_basic(store: MemoryStore, user_id: str, observations: list[dict[str, Any]], embedding_client) -> list[dict[str, Any]]:
    results = []
    for observation in observations:
        content = str(observation["content"])
        metadata = dict(observation.get("metadata") or {})
        metadata.update(
            {
                "slot": observation.get("slot", "general"),
                "value": observation.get("value", content),
                "source": observation.get("source", "user_explicit"),
                "review_status": "accepted",
                "sensitivity": "normal",
                "is_current": True,
                "benchmark_observation_id": observation["id"],
            }
        )
        memory = MemoryItem(
            user_id=user_id,
            content=content,
            vector=embedding_client.embed(content),
            mem_type=str(observation.get("mem_type") or "general"),
            score=0.9,
            importance=float(observation.get("importance") or 3),
            metadata=metadata,
        )
        store.add_item(user_id, memory)
        results.append({"written": True, "action": "add", "memory_id": memory.memory_id})
    return results


def _candidate_map(observations: list[dict[str, Any]]) -> dict[str, list[MemoryToWrite]]:
    mapped: dict[str, list[MemoryToWrite]] = {}
    for observation in observations:
        content = str(observation["content"])
        metadata = dict(observation.get("metadata") or {})
        metadata.update(
            {
                "slot": observation.get("slot", "general"),
                "value": observation.get("value", content),
                "extraction_method": "frozen_dataset",
                "extraction_reason": "committed thesis ablation candidate",
                "benchmark_observation_id": observation["id"],
            }
        )
        mapped.setdefault(content, []).append(
            MemoryToWrite(
                content=content,
                mem_type=str(observation.get("mem_type") or "general"),
                importance=int(observation.get("importance") or 3),
                confidence=float(observation.get("confidence") or 0.9),
                canonical_key=str(observation.get("slot") or "general"),
                canonical_value=str(observation.get("value") or content),
                metadata=metadata,
            )
        )
    return mapped


def _evidence_payload(store: MemoryStore, user_id: str, retrieved, rank: int) -> dict[str, Any]:
    stored = store.get_by_id(user_id, retrieved.memory_id)
    metadata = dict(stored.metadata or {}) if stored else {}
    return {
        "rank": rank,
        "memory_id": retrieved.memory_id,
        "observation_id": str(metadata.get("benchmark_observation_id") or ""),
        "content": retrieved.content,
        "similarity": round(float(retrieved.similarity), 6),
        "final_score": round(float(retrieved.final_score), 6),
        "slot": retrieved.slot,
        "review_status": retrieved.review_status,
        "sensitivity": retrieved.sensitivity,
        "is_current": retrieved.is_current,
    }


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)
