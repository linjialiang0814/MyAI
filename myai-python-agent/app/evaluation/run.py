from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from app.evaluation.registry import EvalReportDefinition
from app.evaluation.registry import iter_eval_report_definitions
from app.evaluation.registry import load_report_functions
from app.observability.store import observability_store


def run_eval_suite(
    suite: str = "all",
    *,
    include_live: bool = False,
    record: bool = True,
) -> dict[str, Any]:
    selected = _select_reports(suite, include_live=include_live)
    started = time.perf_counter()
    suite_results = [_run_definition(definition) for definition in selected]
    duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
    passed = sum(1 for result in suite_results if result["status"] == "passed")
    failed = sum(1 for result in suite_results if result["status"] == "failed")
    skipped = sum(1 for result in suite_results if result["status"] == "skipped")
    total_cases = sum(int((result.get("summary") or {}).get("total") or 0) for result in suite_results)
    passed_cases = sum(int((result.get("summary") or {}).get("passed") or 0) for result in suite_results)
    failed_cases = sum(int((result.get("summary") or {}).get("failed") or 0) for result in suite_results)
    skipped_cases = sum(int((result.get("summary") or {}).get("skipped") or 0) for result in suite_results)
    executed_cases = max(0, total_cases - skipped_cases)
    report = {
        "summary": {
            "suite": suite,
            "reports": len(suite_results),
            "passed_reports": passed,
            "failed_reports": failed,
            "skipped_reports": skipped,
            "total": total_cases,
            "passed": passed_cases,
            "failed": failed_cases,
            "skipped": skipped_cases,
            "pass_rate": round(passed_cases / executed_cases, 4) if executed_cases else 1.0,
            "duration_ms": duration_ms,
            "status": "failed" if failed else "passed",
        },
        "reports": suite_results,
    }
    if record:
        report["observability_record"] = observability_store.record_eval_run(report)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Unified Evaluation Report",
        "",
        f"- Suite: {summary['suite']}",
        f"- Reports: {summary['reports']}",
        f"- Passed reports: {summary['passed_reports']}",
        f"- Failed reports: {summary['failed_reports']}",
        f"- Skipped reports: {summary['skipped_reports']}",
        f"- Total cases: {summary['total']}",
        f"- Passed cases: {summary['passed']}",
        f"- Failed cases: {summary['failed']}",
        f"- Skipped cases: {summary.get('skipped', 0)}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        f"- Duration ms: {summary['duration_ms']}",
        "",
        "| Report | Domain | Status | Cases | Pass Rate | Duration ms | Notes |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in report["reports"]:
        item_summary = item.get("summary") or {}
        notes = item.get("error") or item.get("skip_reason") or ""
        lines.append(
            "| {name} | {domain} | {status} | {total} | {pass_rate} | {duration} | {notes} |".format(
                name=_md(item["name"]),
                domain=_md(item["domain"]),
                status=_md(item["status"]),
                total=item_summary.get("total", 0),
                pass_rate=f"{float(item_summary.get('pass_rate', 1.0)):.2%}",
                duration=item.get("duration_ms", 0),
                notes=_md(str(notes)),
            )
        )
    return "\n".join(lines)


def _select_reports(suite: str, *, include_live: bool) -> list[EvalReportDefinition]:
    normalized = suite.strip().lower()
    definitions = iter_eval_report_definitions()
    if normalized not in {"all", "*"}:
        definitions = [
            definition
            for definition in definitions
            if definition.domain == normalized or definition.report_id == normalized
        ]
    if not include_live:
        definitions = [definition for definition in definitions if not definition.requires_live_llm]
    if not definitions:
        raise ValueError(f"No evaluation reports matched suite: {suite}")
    return definitions


def _run_definition(definition: EvalReportDefinition) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        run_fn, render_fn = load_report_functions(definition)
        fixture = Path(definition.fixture_path) if definition.fixture_path else None
        raw_report = run_fn(fixture) if fixture else run_fn()
        summary = _normalize_summary(raw_report.get("summary") or {})
        rendered = render_fn(raw_report) if render_fn else json.dumps(raw_report, ensure_ascii=False, indent=2)
        status = "failed" if int(summary.get("failed") or 0) > 0 else "passed"
        return {
            "report_id": definition.report_id,
            "name": definition.name,
            "domain": definition.domain,
            "status": status,
            "summary": summary,
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "coverage": definition.coverage,
            "content": rendered,
        }
    except Exception as exc:
        return {
            "report_id": definition.report_id,
            "name": definition.name,
            "domain": definition.domain,
            "status": "failed",
            "summary": {"total": 0, "passed": 0, "failed": 1, "pass_rate": 0.0},
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "coverage": definition.coverage,
            "error": str(exc),
        }


def _normalize_summary(summary: dict[str, Any]) -> dict[str, Any]:
    total = int(summary.get("total") or 0)
    failed = int(summary.get("failed") or 0)
    passed = int(summary.get("passed") if summary.get("passed") is not None else max(0, total - failed))
    pass_rate = summary.get("pass_rate")
    if pass_rate is None:
        pass_rate = summary.get("accuracy")
    if pass_rate is None:
        pass_rate = round(passed / total, 4) if total else 1.0
    normalized = dict(summary)
    normalized.update({"total": total, "passed": passed, "failed": failed, "pass_rate": float(pass_rate)})
    return normalized


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run unified MyAI evaluation suites.")
    parser.add_argument("--suite", default="all", help="all, memory, task, knowledge, mcp, or a report id.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--include-live", action="store_true", help="Include reports that require a live LLM/provider.")
    parser.add_argument("--quality-gate", action="store_true", help="Evaluate the default local quality gate.")
    args = parser.parse_args()

    if args.quality_gate:
        from app.evaluation.quality import render_quality_markdown, run_quality_gate

        report = run_quality_gate(args.suite, include_live=args.include_live)
        rendered = (
            json.dumps(report, ensure_ascii=False, indent=2)
            if args.format == "json"
            else render_quality_markdown(report)
        )
    else:
        report = run_eval_suite(args.suite, include_live=args.include_live)
        rendered = json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.strict and args.quality_gate and not report["quality_gate"]["passed"]:
        raise SystemExit(1)
    if args.strict and report["summary"]["failed_reports"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
