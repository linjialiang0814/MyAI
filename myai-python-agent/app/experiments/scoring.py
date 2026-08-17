from __future__ import annotations

import math
import re
import statistics
import unicodedata
from collections import Counter
from typing import Any, Iterable


def normalize_answer(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower().strip()
    text = re.sub(r"[\s\t\r\n]+", " ", text)
    text = re.sub(r"[\"'`*_#]+", "", text)
    return text.strip(" .,!?:;，。！？：；[](){}")


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    # Latin/numeric benchmark terms need token boundaries: plain substring
    # matching would make cs match physics, lin match baseline, and 3 match 30.
    # Chinese terms intentionally keep substring semantics because words are
    # not whitespace-delimited.
    if term.isascii() and re.search(r"[a-z0-9]", term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    return term in text


def score_answer(answer: str, expected: dict[str, Any]) -> dict[str, Any]:
    rubric_answer = re.sub(r"\[\s*C\d+\s*\]", "", str(answer or ""), flags=re.IGNORECASE)
    normalized = normalize_answer(rubric_answer)
    accepted = [normalize_answer(item) for item in expected.get("accepted_answers") or []]
    required = [normalize_answer(item) for item in expected.get("required_terms") or []]
    configured_groups = list(expected.get("required_term_groups") or [])
    required_groups = (
        [
            [normalize_answer(candidate) for candidate in group if normalize_answer(candidate)]
            for group in configured_groups
        ]
        if configured_groups
        else [[term] for term in required]
    )
    forbidden = [normalize_answer(item) for item in expected.get("forbidden_terms") or []]
    abstain = bool(expected.get("abstain"))
    if abstain:
        # The experiment prompts require the exact sentinel UNKNOWN. Keep the
        # scoring contract self-contained: only aliases explicitly frozen in
        # the case are accepted, rather than silently adding global synonyms.
        correct = normalized in set(accepted)
    else:
        accepted_match = bool(accepted and normalized in accepted)
        required_match = bool(required_groups) and all(
            any(_contains_term(normalized, candidate) for candidate in group)
            for group in required_groups
        )
        correct = (accepted_match or required_match) and not any(
            _contains_term(normalized, term) for term in forbidden
        )
    return {
        "correct": bool(correct),
        "normalized_answer": normalized,
        "required_terms_hit": sum(
            1
            for group in required_groups
            if any(_contains_term(normalized, candidate) for candidate in group)
        ),
        "required_terms_total": len(required_groups),
        "required_term_groups": required_groups,
        "forbidden_terms_hit": [term for term in forbidden if _contains_term(normalized, term)],
        "abstain_expected": abstain,
    }


def score_ranked_evidence(
    selected_ids: list[str],
    expected_ids: Iterable[str | Iterable[str]],
    forbidden_ids: Iterable[str] = (),
) -> dict[str, Any]:
    expected_groups: list[set[str]] = []
    for item in expected_ids:
        if isinstance(item, str):
            expected_groups.append({item})
        else:
            expected_groups.append({str(candidate) for candidate in item})
    forbidden = {str(item) for item in forbidden_ids}
    selected = [str(item) for item in selected_ids]
    relevant = [item for item in selected if any(item in group for group in expected_groups)]
    matched_groups = [group for group in expected_groups if any(item in group for item in selected)]
    forbidden_hits = [item for item in selected if item in forbidden]
    first_rank = next(
        (index for index, item in enumerate(selected, start=1) if any(item in group for group in expected_groups)),
        None,
    )
    applicable = bool(expected_groups)
    return {
        # Retrieval quality is undefined when a case intentionally has no gold
        # evidence. Context rejection and forbidden-evidence leakage are
        # measured separately for those abstention cases.
        "applicable": applicable,
        "recall_at_k": len(matched_groups) / len(expected_groups) if applicable else None,
        "precision_at_k": (
            len(relevant) / len(selected) if selected else 0.0
        ) if applicable else None,
        "mrr": (1.0 / first_rank if first_rank else 0.0) if applicable else None,
        "hit_at_k": bool(relevant) if applicable else None,
        "forbidden_hits": forbidden_hits,
        "leakage": bool(forbidden_hits),
        "leakage_applicable": True,
    }


def latency_summary(values: Iterable[float]) -> dict[str, float]:
    observed = sorted(float(value) for value in values)
    if not observed:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "mean": round(statistics.fmean(observed), 3),
        "p50": round(_percentile(observed, 0.50), 3),
        "p95": round(_percentile(observed, 0.95), 3),
        "max": round(max(observed), 3),
    }


def aggregate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _aggregate_core(cases)
    summary.update(
        {
            "by_repeat": _grouped_summaries(cases, "repeat", prefix="r"),
            "by_category": _grouped_summaries(cases, "category"),
            "by_language": _grouped_summaries(cases, "language"),
            "by_answerability": _grouped_summaries(cases, "answerability"),
            "repeat_consistency": _repeat_consistency(cases),
            "technical_repeat_note": (
                "Repeated executions are technical repeats; unique case count, not attempts, "
                "is the statistical sample size."
            ),
        }
    )
    return summary


def _aggregate_core(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    failures = sum(1 for case in cases if not case.get("execution_ok"))
    correct = sum(1 for case in cases if case.get("answer_score", {}).get("correct"))
    evidence = [case.get("evidence_score") or {} for case in cases]
    applicable_evidence = [
        item
        for item in evidence
        if item.get("applicable", item.get("recall_at_k") is not None)
    ]
    applicable_leakage = [
        item for item in evidence if item.get("leakage_applicable", False)
    ]
    applicable_citations = [case for case in cases if case.get("citation_applicable")]
    citation_cases = [case for case in cases if "generated_citation_count" in case]
    no_answer_citation_cases = [
        case for case in citation_cases if case.get("answerability") == "abstention"
    ]
    successful_no_answer = [
        case
        for case in cases
        if case.get("execution_ok") and case.get("answerability") == "abstention"
    ]
    answerable = [case for case in cases if case.get("answerability") == "answerable"]
    abstention = [case for case in cases if case.get("answerability") == "abstention"]
    rubric_accuracy = round(correct / total, 4) if total else 0.0
    return {
        "cases": total,
        "unique_cases": len({str(case.get("case_id") or "") for case in cases}),
        "rubric_accuracy": rubric_accuracy,
        "answer_accuracy": rubric_accuracy,
        "answerable_rubric_accuracy": _accuracy(answerable),
        "abstention_rubric_accuracy": _accuracy(abstention),
        "failure_rate": round(failures / total, 4) if total else 0.0,
        "failure_categories": dict(sorted(Counter(
            str(case.get("failure_category") or "unknown")
            for case in cases
            if not case.get("execution_ok")
        ).items())),
        "evidence_applicable_cases": len(applicable_evidence),
        "evidence_recall_at_k": _mean_or_none(
            item.get("recall_at_k") for item in applicable_evidence
        ),
        "evidence_precision_at_k": _mean_or_none(
            item.get("precision_at_k") for item in applicable_evidence
        ),
        "mrr": _mean_or_none(item.get("mrr") for item in applicable_evidence),
        "leakage_applicable_cases": len(applicable_leakage),
        "leakage_rate": _mean_or_none(
            1.0 if item.get("leakage") else 0.0 for item in applicable_leakage
        ),
        "support_applicable_cases": len(applicable_citations),
        "support_hit_at_k": _mean_or_none(
            1.0 if case.get("support_hit_at_k") else 0.0 for case in applicable_citations
        ),
        "support_precision_at_k": _mean_or_none(
            case.get("support_precision_at_k") for case in applicable_citations
        ),
        "citation_applicable_cases": len(applicable_citations),
        "citation_hit_rate": _mean_or_none(
            1.0 if case.get("generated_citation_hit") else 0.0 for case in applicable_citations
        ),
        "citation_precision": _mean_or_none(
            case.get("generated_citation_precision") for case in applicable_citations
        ),
        "citation_compliance_rate": _mean_or_none(
            1.0 if case.get("generated_citation_count", 0) else 0.0 for case in applicable_citations
        ),
        "invalid_citation_rate": _mean_or_none(
            1.0 if case.get("invalid_citation") else 0.0 for case in citation_cases
        ),
        "no_answer_citation_hallucination_rate": _mean_or_none(
            1.0 if case.get("no_answer_citation_hallucination") else 0.0
            for case in no_answer_citation_cases
        ),
        "grounded_rubric_accuracy": _mean_or_none(
            1.0
            if case.get("answer_score", {}).get("correct")
            and case.get("generated_citation_hit")
            else 0.0
            for case in applicable_citations
        ),
        "no_answer_successful_cases": len(successful_no_answer),
        "no_answer_empty_retrieval_rate": _mean_or_none(
            1.0 if int(case.get("selected_context_count") or 0) == 0 else 0.0
            for case in successful_no_answer
        ),
        "no_answer_forbidden_leakage_rate": _mean_or_none(
            1.0 if (case.get("evidence_score") or {}).get("leakage") else 0.0
            for case in successful_no_answer
            if (case.get("evidence_score") or {}).get("leakage_applicable", False)
        ),
        "candidate_count_mean": _mean(case.get("candidate_count") for case in cases),
        "selected_context_count_mean": _mean(case.get("selected_context_count") for case in cases),
        "write_latency_ms": latency_summary(_successful_values(cases, "write_latency_ms")),
        "retrieval_latency_ms": latency_summary(_successful_values(cases, "retrieval_latency_ms")),
        "generation_latency_ms": latency_summary(_successful_values(cases, "generation_latency_ms")),
        "end_to_end_latency_ms": latency_summary(_successful_values(cases, "end_to_end_latency_ms")),
        "all_attempt_end_to_end_latency_ms": latency_summary(
            _all_attempt_elapsed_values(cases)
        ),
        "failure_elapsed_ms": latency_summary(
            case.get("failure_elapsed_ms")
            for case in cases
            if not case.get("execution_ok") and case.get("failure_elapsed_ms") is not None
        ),
    }


def _accuracy(cases: list[dict[str, Any]]) -> float:
    if not cases:
        return 0.0
    return round(
        sum(1 for case in cases if case.get("answer_score", {}).get("correct")) / len(cases),
        4,
    )


def _successful_values(cases: list[dict[str, Any]], field: str) -> Iterable[float]:
    return (
        case[field]
        for case in cases
        if case.get("execution_ok") and case.get(field) is not None
    )


def _all_attempt_elapsed_values(cases: list[dict[str, Any]]) -> Iterable[float]:
    for case in cases:
        field = "end_to_end_latency_ms" if case.get("execution_ok") else "failure_elapsed_ms"
        if case.get(field) is not None:
            yield float(case[field])


def _grouped_summaries(
    cases: list[dict[str, Any]],
    field: str,
    *,
    prefix: str = "",
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        raw = case.get(field)
        label = f"{prefix}{raw}" if raw not in (None, "") else "unspecified"
        grouped.setdefault(str(label), []).append(case)
    return {key: _aggregate_core(value) for key, value in sorted(grouped.items())}


def _repeat_consistency(cases: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        grouped.setdefault(str(case.get("case_id") or ""), []).append(case)
    repeated = [items for items in grouped.values() if len(items) > 1]
    correctness_consistent = sum(
        1
        for items in repeated
        if len({bool(item.get("answer_score", {}).get("correct")) for item in items}) == 1
    )
    normalized_answer_consistent = sum(
        1
        for items in repeated
        if len({str(item.get("answer_score", {}).get("normalized_answer") or "") for item in items}) == 1
    )
    return {
        "repeated_unique_cases": len(repeated),
        "correctness_consistency_rate": round(correctness_consistent / len(repeated), 4) if repeated else 1.0,
        "normalized_answer_consistency_rate": (
            round(normalized_answer_consistent / len(repeated), 4) if repeated else 1.0
        ),
    }


def _mean(values: Iterable[Any]) -> float:
    observed = [float(value) for value in values if value is not None]
    return round(statistics.fmean(observed), 4) if observed else 0.0


def _mean_or_none(values: Iterable[Any]) -> float | None:
    observed = [float(value) for value in values if value is not None]
    return round(statistics.fmean(observed), 4) if observed else None


def _percentile(values: list[float], quantile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction
