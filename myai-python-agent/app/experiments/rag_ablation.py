from __future__ import annotations

import re
import time
from typing import Any


def ingest_rag_corpus(service, documents: list[dict[str, Any]], user_id: str) -> dict[str, Any]:
    started = time.perf_counter()
    aliases_by_file_id: dict[str, str] = {}
    uploads: list[dict[str, Any]] = []
    for document in documents:
        payload = service.upload_file(
            user_id=user_id,
            filename=str(document["file_name"]),
            content=str(document["content"]).encode("utf-8"),
        )
        alias = str(document["alias"])
        aliases_by_file_id[str(payload["file_id"])] = alias
        uploads.append(
            {
                "alias": alias,
                "file_id": payload["file_id"],
                "file_name": payload["file_name"],
                "chunk_count": payload.get("chunk_count", 0),
                "content_hash": payload.get("content_hash", ""),
            }
        )
    return {
        "aliases_by_file_id": aliases_by_file_id,
        "uploads": uploads,
        "indexing_latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
    }


def retrieve_rag_evidence(
    *,
    service,
    user_id: str,
    variant: str,
    case: dict[str, Any],
    aliases_by_file_id: dict[str, str],
    top_k: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    hits = service.query(
        user_id,
        str(case["query"]),
        top_k=top_k,
        retrieval_strategy=variant,
    )
    latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
    evidence = []
    for rank, hit in enumerate(hits, start=1):
        evidence.append(
            {
                "rank": rank,
                "label": f"C{rank}",
                "chunk_id": hit.get("chunk_id", ""),
                "file_id": hit.get("file_id", ""),
                "file_alias": aliases_by_file_id.get(str(hit.get("file_id") or ""), ""),
                "file_name": hit.get("file_name", ""),
                "content": hit.get("content", ""),
                "citation_id": hit.get("citation_id", ""),
                "char_start": hit.get("char_start", 0),
                "char_end": hit.get("char_end", 0),
                "retrieval_score": hit.get("retrieval_score", 0.0),
                "vector_score": hit.get("vector_score", 0.0),
                "keyword_score": hit.get("keyword_score", 0.0),
                "rerank_score": hit.get("rerank_score", 0.0),
                "candidate_rank": hit.get("candidate_rank", 0),
                "final_rank": hit.get("final_rank", rank),
                "retrieval_strategy": hit.get("retrieval_strategy", variant),
                "rerank_applied": bool(hit.get("rerank_applied")),
            }
        )
    return {
        "variant": variant,
        "evidence": evidence,
        "retrieval_latency_ms": latency_ms,
        "candidate_count": max(
            [int((hit.get("selection_explanation") or {}).get("candidate_count") or len(hits)) for hit in hits]
            or [0]
        ),
    }


def build_rag_prompt(case: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    lines = [
        "SOURCES:",
    ]
    if evidence:
        for item in evidence:
            lines.append(f"[{item['label']}] {item['content']}")
    else:
        lines.append("(none)")
    lines.extend(
        [
            "",
            f"QUESTION: {case['query']}",
            "",
            "Answer concisely using only the sources.",
            "Output a short answer followed by the bracketed label copied from the source that supports it.",
            "Reply exactly UNKNOWN only when no source contains the answer.",
            "Do not invent labels or add an explanation.",
        ]
    )
    return "\n".join(lines)


def score_rag_citations(case: dict[str, Any], evidence: list[dict[str, Any]], answer: str) -> dict[str, Any]:
    gold_groups = _gold_evidence_groups(case)
    applicable = bool(gold_groups)
    matched_group_indexes: list[set[int]] = []
    correctness: list[bool] = []
    for item in evidence:
        matched = {
            index
            for index, group in enumerate(gold_groups)
            if _matches_gold_group(item, group)
        }
        matched_group_indexes.append(matched)
        correctness.append(bool(matched))

    matched_groups = set().union(*matched_group_indexes) if matched_group_indexes else set()
    correct_count = sum(1 for value in correctness if value)
    first_support_rank = next(
        (index for index, value in enumerate(correctness, start=1) if value),
        None,
    )
    available_labels = {
        str(item.get("label") or "").upper(): index
        for index, item in enumerate(evidence)
        if item.get("label")
    }
    parsed_labels = []
    for raw_number in re.findall(r"\[\s*C(\d+)\s*\]", str(answer or ""), flags=re.IGNORECASE):
        label = f"C{int(raw_number)}"
        if label not in parsed_labels:
            parsed_labels.append(label)
    invalid_labels = [label for label in parsed_labels if label not in available_labels]
    valid_labels = [label for label in parsed_labels if label in available_labels]
    correct_citation_labels = [
        label
        for label in valid_labels
        if correctness[available_labels[label]]
    ]
    generated_count = len(parsed_labels)
    generated_precision = (
        len(correct_citation_labels) / generated_count
        if generated_count
        else (1.0 if not applicable else 0.0)
    )
    generated_hit = bool(correct_citation_labels) if applicable else False
    return {
        "citation_applicable": applicable,
        "support_hit_at_k": bool(correct_count) if applicable else None,
        "support_recall_at_k": (
            len(matched_groups) / len(gold_groups)
            if gold_groups
            else None
        ),
        "support_precision_at_k": (
            correct_count / len(evidence)
            if evidence
            else (0.0 if applicable else None)
        ),
        "support_mrr": (1.0 / first_support_rank if first_support_rank else 0.0) if applicable else None,
        "citation_hit": generated_hit,
        "citation_precision": generated_precision,
        "generated_citation_count": generated_count,
        "generated_citation_labels": parsed_labels,
        "generated_citation_hit": generated_hit,
        "generated_citation_precision": generated_precision,
        "generated_citation_compliant": bool(parsed_labels) if applicable else not parsed_labels,
        "invalid_citation_labels": invalid_labels,
        "invalid_citation": bool(invalid_labels),
        "no_answer_citation_hallucination": bool(parsed_labels) and not applicable,
        "correct_generated_citation_labels": correct_citation_labels,
        "correct_evidence_labels": [
            evidence[index]["label"] for index, value in enumerate(correctness) if value
        ],
    }


def _gold_evidence_groups(case: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = list(case.get("gold_evidence") or [])
    if explicit:
        return [
            {
                "file_alias": str(item.get("file_alias") or ""),
                "anchors": [str(anchor).casefold() for anchor in item.get("anchors") or []],
                "match": str(item.get("match") or "all").lower(),
            }
            for item in explicit
        ]
    anchors = [str(item).casefold() for item in case.get("gold_content_anchors") or []]
    return [
        {"file_alias": str(alias), "anchors": anchors, "match": "any"}
        for alias in case.get("gold_file_aliases") or []
    ]


def _matches_gold_group(evidence: dict[str, Any], group: dict[str, Any]) -> bool:
    if str(evidence.get("file_alias") or "") != group["file_alias"]:
        return False
    anchors = list(group.get("anchors") or [])
    if not anchors:
        return True
    content = str(evidence.get("content") or "").casefold()
    if group.get("match") == "any":
        return any(anchor in content for anchor in anchors)
    return all(anchor in content for anchor in anchors)
