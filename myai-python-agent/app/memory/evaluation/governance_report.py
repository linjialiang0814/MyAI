from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from app.memory.governance import normalize_governance_metadata
from app.memory.mem_service import MemoryService
from app.memory.store.in_mem_store import MemoryStore
from app.memory.writer.smart_writer import RuleBasedMemoryExtractor, SmartMemoryWriter


BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE = BASE_DIR / "tests" / "fixtures" / "memory_governance_eval.json"


class ReportEmbedding:
    def embed(self, text: str):
        normalized = text.lower()
        if normalized.startswith("what is"):
            return _unit([0.98, 0.18, 0.0, 0.0])
        if "major" in normalized or "computer science" in normalized or "cs" in normalized:
            return _unit([1.0, 0.0, 0.0, 0.0])
        if "python" in normalized or "javascript" in normalized:
            return _unit([0.0, 1.0, 0.0, 0.0])
        if "password" in normalized:
            return _unit([0.0, 0.0, 1.0, 0.0])
        return _unit([0.0, 0.0, 0.0, 1.0])


def _unit(values):
    vector = np.array(values, dtype=np.float32)
    norm = math.sqrt(float(np.dot(vector, vector)))
    if norm == 0:
        return vector
    return vector / norm


def run_governance_report(fixture_path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = _write_calibration_cases(fixture) + _direct_calibration_cases(fixture)
    passed = sum(1 for case in cases if case["passed"])
    fixture_inventory = _fixture_inventory(fixture)
    return {
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "accuracy": round(passed / len(cases), 4) if cases else 0.0,
            "executed_coverage": _executed_coverage(cases),
            "fixture_inventory": fixture_inventory,
            # Deprecated compatibility alias. This historically described the
            # fixture inventory, not the cases actually executed by this report.
            "coverage_by_section": fixture_inventory,
        },
        "cases": cases,
    }


def _write_calibration_cases(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    service = MemoryService(
        embedding_client=ReportEmbedding(),
        memory_store=MemoryStore(),
        writer=SmartMemoryWriter(extractors=[RuleBasedMemoryExtractor()]),
    )
    results: list[dict[str, Any]] = []
    for case in fixture.get("write_cases", []):
        if not _has_calibration_expectation(case):
            continue
        user_id = f"report-write-{case['id']}"
        write_result = service.process_user_input(user_id, case["input"])
        memory = None
        if write_result.get("memory_id"):
            memory = service.memory_store.get_by_id(user_id, write_result["memory_id"])
        metadata = memory.metadata if memory else {}
        results.append(_evaluate_metadata_case(case, metadata, section="write_cases"))
    return results


def _direct_calibration_cases(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in fixture.get("calibration_cases", []):
        metadata = normalize_governance_metadata(
            base_metadata=case.get("base_metadata", {}),
            content=case["content"],
            mem_type=case["mem_type"],
            confidence=case["confidence"],
            source=case["source"],
            importance=case["importance"],
        )
        results.append(_evaluate_metadata_case(case, metadata, section="calibration_cases"))
    return results


def _evaluate_metadata_case(case: dict[str, Any], metadata: dict[str, Any], *, section: str) -> dict[str, Any]:
    actual_confidence = _as_float(metadata.get("calibrated_confidence"))
    expected_min = case.get("expect_calibrated_confidence_min")
    expected_max = case.get("expect_calibrated_confidence_max")
    min_delta = _delta_from_min(actual_confidence, expected_min)
    max_delta = _delta_from_max(actual_confidence, expected_max)
    expected_status = case.get("expect_review_status")
    actual_status = metadata.get("review_status")
    expected_factors = case.get("expect_calibration_factors_contains", [])
    actual_factors = str(metadata.get("confidence_calibration_factors", "") or "")
    missing_factors = [factor for factor in expected_factors if factor not in actual_factors]

    mismatches: list[str] = []
    if expected_status is not None and actual_status != expected_status:
        mismatches.append(f"review_status expected={expected_status} actual={actual_status}")
    if min_delta is not None and min_delta < 0:
        mismatches.append(f"calibrated_confidence expected>={expected_min} actual={actual_confidence}")
    if max_delta is not None and max_delta < 0:
        mismatches.append(f"calibrated_confidence expected<={expected_max} actual={actual_confidence}")
    for factor in missing_factors:
        mismatches.append(f"missing calibration factor: {factor}")

    return {
        "id": case["id"],
        "section": section,
        "passed": not mismatches,
        "expected": {
            "review_status": expected_status,
            "calibrated_confidence_min": expected_min,
            "calibrated_confidence_max": expected_max,
            "factors_contains": expected_factors,
        },
        "actual": {
            "review_status": actual_status,
            "raw_confidence": metadata.get("raw_confidence"),
            "calibrated_confidence": actual_confidence,
            "confidence_calibration_factors": actual_factors,
            "confidence_calibration_reason": metadata.get("confidence_calibration_reason"),
        },
        "delta": {
            "min_margin": min_delta,
            "max_margin": max_delta,
        },
        "missing_factors": missing_factors,
        "mismatches": mismatches,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Memory Confidence Calibration Report",
        "",
        f"- total: {summary['total']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        f"- accuracy: {summary['accuracy']}",
        f"- executed coverage: {_coverage_label(summary.get('executed_coverage', {}))}",
        f"- fixture inventory: {_coverage_label(summary.get('fixture_inventory', {}))}",
        "",
        "| case | section | pass | raw | actual | expected | delta | status | factors |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        expected = _expected_range_label(case["expected"])
        delta = _delta_label(case["delta"])
        factors = case["actual"].get("confidence_calibration_factors") or ""
        lines.append(
            "| {id} | {section} | {passed} | {raw} | {actual} | {expected} | {delta} | {status} | {factors} |".format(
                id=_md(case["id"]),
                section=_md(case["section"]),
                passed="yes" if case["passed"] else "no",
                raw=_fmt(case["actual"].get("raw_confidence")),
                actual=_fmt(case["actual"].get("calibrated_confidence")),
                expected=_md(expected),
                delta=_md(delta),
                status=_md(str(case["actual"].get("review_status") or "")),
                factors=_md(factors),
            )
        )
    failures = [case for case in report["cases"] if not case["passed"]]
    if failures:
        lines.extend(["", "## Failures", ""])
        for case in failures:
            lines.append(f"- `{case['id']}`: " + "; ".join(case["mismatches"]))
    return "\n".join(lines) + "\n"


def _has_calibration_expectation(case: dict[str, Any]) -> bool:
    return any(
        key in case
        for key in (
            "expect_calibrated_confidence_min",
            "expect_calibrated_confidence_max",
            "expect_calibration_factors_contains",
        )
    )


def _fixture_inventory(fixture: dict[str, Any]) -> dict[str, int]:
    return {
        section: len(cases)
        for section, cases in fixture.items()
        if isinstance(cases, list)
    }


def _executed_coverage(cases: list[dict[str, Any]]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for case in cases:
        section = str(case.get("section") or "unknown")
        coverage[section] = coverage.get(section, 0) + 1
    return coverage


def _coverage_label(coverage: dict[str, int]) -> str:
    if not coverage:
        return "-"
    return ", ".join(f"{section}={count}" for section, count in sorted(coverage.items()))


def _delta_from_min(actual: float | None, expected_min: Any) -> float | None:
    if actual is None or expected_min is None:
        return None
    return round(actual - float(expected_min), 4)


def _delta_from_max(actual: float | None, expected_max: Any) -> float | None:
    if actual is None or expected_max is None:
        return None
    return round(float(expected_max) - actual, 4)


def _expected_range_label(expected: dict[str, Any]) -> str:
    parts: list[str] = []
    if expected.get("calibrated_confidence_min") is not None:
        parts.append(f">={_fmt(expected['calibrated_confidence_min'])}")
    if expected.get("calibrated_confidence_max") is not None:
        parts.append(f"<={_fmt(expected['calibrated_confidence_max'])}")
    return " ".join(parts) or "-"


def _delta_label(delta: dict[str, Any]) -> str:
    parts: list[str] = []
    if delta.get("min_margin") is not None:
        parts.append(f"min {_fmt(delta['min_margin'])}")
    if delta.get("max_margin") is not None:
        parts.append(f"max {_fmt(delta['max_margin'])}")
    return " ".join(parts) or "-"


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any) -> str:
    number = _as_float(value)
    if number is None:
        return ""
    return f"{number:.4f}"


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render memory governance confidence calibration report.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any case fails.")
    args = parser.parse_args()

    report = run_governance_report(args.fixture)
    rendered = (
        json.dumps(report, ensure_ascii=False, indent=2)
        if args.format == "json"
        else render_markdown(report)
    )
    print(rendered, end="" if rendered.endswith("\n") else "\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered if rendered.endswith("\n") else rendered + "\n", encoding="utf-8")
    if args.strict and report["summary"]["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
