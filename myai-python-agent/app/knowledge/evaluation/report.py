from __future__ import annotations

import argparse
import json
import os
import math
import shutil
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from app.knowledge.service import KnowledgeService


BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE = BASE_DIR / "tests" / "fixtures" / "knowledge_eval.json"


class KnowledgeEvalEmbedding:
    def embed(self, text: str):
        normalized = text.lower()
        values = [
            _score(normalized, ["agent", "orchestration", "automated", "planning", "tools", "workflow", "memories", "execution"]),
            _score(normalized, ["zxq9000", "部署", "deployment", "window", "phoenix", "上线"]),
            _score(normalized, ["machine", "learning", "机器学习", "数据", "computer"]),
            _score(normalized, ["citation", "audit", "snippet", "score", "chunk", "span"]),
            _score(normalized, ["myai", "hybrid", "retrieval", "检索", "vector", "keyword"]),
            _score(normalized, ["mars", "火星", "budget", "预算"]),
            0.05,
            0.01 * (len(normalized) % 11),
        ]
        vector = np.array(values, dtype=np.float32)
        norm = math.sqrt(float(np.dot(vector, vector)))
        if norm == 0:
            return vector
        return vector / norm


def run_knowledge_report(fixture_path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    eval_work_root = Path(os.getenv("MYAI_EVAL_WORK_DIR", str(BASE_DIR / ".tmp")))
    temp_root = eval_work_root / "knowledge_eval"
    temp_root.mkdir(parents=True, exist_ok=True)
    root = temp_root / f"run-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        service = KnowledgeService(
            persist_dir=str(root / "chroma"),
            base_dir=str(root / "knowledge"),
            embedding_client=KnowledgeEvalEmbedding(),
        )
        cases = [_run_case(service, case) for case in fixture.get("cases", [])]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    passed = sum(1 for case in cases if case["passed"])
    failed = len(cases) - passed
    query_cases = [case for case in cases if case["type"] == "query"]
    citation_cases = [case for case in cases if case.get("citation_required")]
    summary = {
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(cases), 4) if cases else 1.0,
        "hit_at_k": _rate([case.get("hit_at_k", False) for case in query_cases]),
        "expected_file_found": _rate([case.get("expected_file_found", False) for case in query_cases]),
        "citation_completeness": _rate([case.get("citation_complete", False) for case in citation_cases]),
        "average_latency_ms": round(sum(case["latency_ms"] for case in cases) / len(cases), 2) if cases else 0.0,
        "coverage_by_type": _coverage_by_type(cases),
    }
    return {
        "summary": summary,
        "cases": cases,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Knowledge Evaluation Report",
        "",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        f"- Hit@k: {summary['hit_at_k']:.2%}",
        f"- Expected file found: {summary['expected_file_found']:.2%}",
        f"- Citation completeness: {summary['citation_completeness']:.2%}",
        f"- Average latency ms: {summary['average_latency_ms']}",
        f"- Coverage: {_coverage_label(summary.get('coverage_by_type', {}))}",
        "",
        "| Case | Type | Pass | Hit@k | Expected File | Citation | Latency ms | Notes |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for case in report["cases"]:
        notes = "; ".join(case.get("errors") or []) or case.get("notes", "")
        lines.append(
            "| {id} | {type} | {passed} | {hit} | {file_found} | {citation} | {latency} | {notes} |".format(
                id=_md(case["id"]),
                type=_md(case["type"]),
                passed="yes" if case["passed"] else "no",
                hit=_bool_label(case.get("hit_at_k")),
                file_found=_bool_label(case.get("expected_file_found")),
                citation=_bool_label(case.get("citation_complete")),
                latency=case["latency_ms"],
                notes=_md(notes),
            )
        )
    failures = [case for case in report["cases"] if not case["passed"]]
    if failures:
        lines.extend(["", "## Failures", ""])
        for case in failures:
            lines.append(f"- `{case['id']}`: " + "; ".join(case["errors"]))
    return "\n".join(lines) + "\n"


def _run_case(service: KnowledgeService, case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    user_id = f"knowledge-eval-{case['id']}"
    uploads = _upload_files(service, user_id, case.get("files") or [])
    errors: list[str] = []
    result: dict[str, Any] = {
        "id": case["id"],
        "type": case["type"],
        "passed": True,
        "errors": errors,
        "latency_ms": 0,
        "uploaded_files": {alias: payload["file_id"] for alias, payload in uploads.items()},
        "hit_at_k": None,
        "expected_file_found": None,
        "citation_required": bool((case.get("expect") or {}).get("citation_complete")),
        "citation_complete": None,
    }

    if case["type"] == "upload":
        _check_upload_case(result, uploads, case.get("expect") or {})
    elif case["type"] == "duplicate":
        _check_duplicate_case(result, uploads, case.get("expect") or {})
    elif case["type"] == "query":
        _check_query_case(service, user_id, result, uploads, case)
    elif case["type"] == "qa":
        _check_qa_case(service, user_id, result, uploads, case)
    else:
        errors.append(f"unsupported case type: {case['type']}")

    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    result["passed"] = not errors
    return result


def _upload_files(service: KnowledgeService, user_id: str, files: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    uploads: dict[str, dict[str, Any]] = {}
    for item in files:
        uploads[item["alias"]] = service.upload_file(
            user_id=user_id,
            filename=item["file_name"],
            content=item["content"].encode("utf-8"),
        )
    return uploads


def _check_upload_case(result: dict[str, Any], uploads: dict[str, dict[str, Any]], expect: dict[str, Any]) -> None:
    payload = next(iter(uploads.values()), {})
    if expect.get("ingestion_status") and payload.get("ingestion_status") != expect["ingestion_status"]:
        result["errors"].append(f"ingestion_status expected={expect['ingestion_status']} actual={payload.get('ingestion_status')}")
    if expect.get("profile") and not payload.get("document_profile"):
        result["errors"].append("document_profile missing")
    if int(payload.get("chunk_count") or 0) < int(expect.get("min_chunk_count", 0)):
        result["errors"].append(f"chunk_count expected>={expect.get('min_chunk_count')} actual={payload.get('chunk_count')}")


def _check_duplicate_case(result: dict[str, Any], uploads: dict[str, dict[str, Any]], expect: dict[str, Any]) -> None:
    payloads = list(uploads.values())
    if len(payloads) < 2:
        result["errors"].append("duplicate case requires at least two uploads")
        return
    duplicate_report = payloads[-1].get("ingestion_report") or {}
    is_duplicate = duplicate_report.get("status") == "duplicate" and payloads[-1].get("file_id") == payloads[0].get("file_id")
    if bool(expect.get("duplicate")) != is_duplicate:
        result["errors"].append(f"duplicate expected={expect.get('duplicate')} actual={is_duplicate}")


def _check_query_case(
    service: KnowledgeService,
    user_id: str,
    result: dict[str, Any],
    uploads: dict[str, dict[str, Any]],
    case: dict[str, Any],
) -> None:
    expect = case.get("expect") or {}
    file_id = _alias_file_id(uploads, case.get("file_filter_alias"))
    hits = service.query(user_id, case["query"], top_k=int(case.get("top_k") or 3), file_id=file_id)
    expected_file_id = _alias_file_id(uploads, expect.get("file_alias"))
    hit_at_k = bool(expected_file_id and any(hit.get("file_id") == expected_file_id for hit in hits))
    expected_file_found = bool(hits and hits[0].get("file_id") == expected_file_id) if expected_file_id else None
    result.update(
        {
            "hit_count": len(hits),
            "top_file_id": hits[0].get("file_id") if hits else "",
            "top_citation_id": hits[0].get("citation_id") if hits else "",
            "top_retrieval_mode": hits[0].get("retrieval_mode") if hits else "",
            "hit_at_k": hit_at_k,
            "expected_file_found": expected_file_found,
            "citation_complete": _citation_complete(hits[0]) if hits and expect.get("citation_complete") else None,
        }
    )
    if expect.get("hit_at_k") and not hit_at_k:
        result["errors"].append(f"expected file not found in top {case.get('top_k')}: {expect.get('file_alias')}")
    if expected_file_found is False:
        result["errors"].append(f"top file expected={expect.get('file_alias')} actual={result.get('top_file_id')}")
    if expect.get("all_hits_file_alias"):
        expected_all_id = _alias_file_id(uploads, expect["all_hits_file_alias"])
        if any(hit.get("file_id") != expected_all_id for hit in hits):
            result["errors"].append(f"not all hits are from file alias {expect['all_hits_file_alias']}")
    if expect.get("retrieval_mode_contains") and expect["retrieval_mode_contains"] not in str(result.get("top_retrieval_mode") or ""):
        result["errors"].append(
            f"retrieval_mode expected to contain {expect['retrieval_mode_contains']} actual={result.get('top_retrieval_mode')}"
        )
    if expect.get("citation_complete") and not result.get("citation_complete"):
        result["errors"].append("citation is incomplete")


def _check_qa_case(
    service: KnowledgeService,
    user_id: str,
    result: dict[str, Any],
    uploads: dict[str, dict[str, Any]],
    case: dict[str, Any],
) -> None:
    expect = case.get("expect") or {}
    file_id = _alias_file_id(uploads, case.get("file_filter_alias"))
    qa = service.answer_document_question(user_id, file_id or "", case["question"], top_k=int(case.get("top_k") or 3))
    result.update(
        {
            "answer_status": qa.get("answer_status"),
            "evidence_count": qa.get("evidence_count"),
            "citation_complete": all(_citation_complete(hit) for hit in qa.get("hits") or []) if qa.get("hits") else False,
        }
    )
    for key in ("answer_status", "evidence_count"):
        if key in expect and qa.get(key) != expect[key]:
            result["errors"].append(f"{key} expected={expect[key]!r} actual={qa.get(key)!r}")


def _alias_file_id(uploads: dict[str, dict[str, Any]], alias: str | None) -> str | None:
    if not alias:
        return None
    payload = uploads.get(alias)
    return payload.get("file_id") if payload else None


def _citation_complete(hit: dict[str, Any]) -> bool:
    citation = hit.get("citation") or {}
    required = ("citation_id", "chunk_id", "file_id", "file_name", "char_start", "char_end", "snippet", "score")
    return all(citation.get(key) not in (None, "") for key in required) and bool(hit.get("citation_id"))


def _score(text: str, terms: list[str]) -> float:
    return float(sum(1 for term in terms if term in text))


def _rate(values: list[bool | None]) -> float:
    observed = [value for value in values if value is not None]
    if not observed:
        return 1.0
    return round(sum(1 for value in observed if value) / len(observed), 4)


def _coverage_by_type(cases: list[dict[str, Any]]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for case in cases:
        coverage[case["type"]] = coverage.get(case["type"], 0) + 1
    return coverage


def _coverage_label(coverage: dict[str, int]) -> str:
    if not coverage:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in sorted(coverage.items()))


def _bool_label(value: bool | None) -> str:
    if value is None:
        return "-"
    return "yes" if value else "no"


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run knowledge retrieval and QA evaluation fixture.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = run_knowledge_report(args.fixture)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered if rendered.endswith("\n") else rendered + "\n", encoding="utf-8")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")
    if args.strict and report["summary"]["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
