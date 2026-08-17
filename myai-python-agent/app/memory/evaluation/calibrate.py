from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE = BASE_DIR / "tests" / "fixtures" / "memory_llm_calibration.json"

from app.memory.writer.llm_extractor import LLMMemoryExtractor
from app.model.factory import create_llm


def evaluate_case(extractor: LLMMemoryExtractor, case: dict[str, Any]) -> dict[str, Any]:
    candidate = extractor.extract(case["input"])
    actual_write = candidate is not None
    passed = actual_write == bool(case["expect_write"])
    mismatches: list[str] = []

    if passed and candidate:
        expected_type = case.get("expect_mem_type")
        expected_slot = case.get("expect_slot")
        if expected_type and candidate.mem_type != expected_type:
            passed = False
            mismatches.append(f"mem_type expected={expected_type} actual={candidate.mem_type}")
        if expected_slot and candidate.metadata.get("slot") != expected_slot:
            passed = False
            mismatches.append(
                f"slot expected={expected_slot} actual={candidate.metadata.get('slot')}"
            )
        confidence_min = case.get("expect_confidence_min")
        confidence_max = case.get("expect_confidence_max")
        if confidence_min is not None and candidate.confidence < float(confidence_min):
            passed = False
            mismatches.append(
                f"confidence expected>={confidence_min} actual={candidate.confidence}"
            )
        if confidence_max is not None and candidate.confidence > float(confidence_max):
            passed = False
            mismatches.append(
                f"confidence expected<={confidence_max} actual={candidate.confidence}"
            )
    elif not passed:
        mismatches.append(
            f"write expected={bool(case['expect_write'])} actual={actual_write}"
        )

    actual = {"should_write": actual_write}
    if candidate:
        actual.update(
            {
                "content": candidate.content,
                "mem_type": candidate.mem_type,
                "slot": candidate.metadata.get("slot"),
                "value": candidate.metadata.get("value"),
                "confidence": candidate.confidence,
                "importance": candidate.importance,
                "sensitivity": candidate.metadata.get("sensitivity"),
                "scope": candidate.metadata.get("scope"),
                "reason": candidate.metadata.get("extraction_reason"),
            }
        )

    return {
        "id": case["id"],
        "passed": passed,
        "expected": {
            key: value
            for key, value in case.items()
            if key.startswith("expect_")
        },
        "actual": actual,
        "mismatches": mismatches,
    }


def run_calibration(fixture_path: Path) -> dict[str, Any]:
    load_dotenv(BASE_DIR / ".env")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    extractor = LLMMemoryExtractor(create_llm(role="memory"))
    results = [evaluate_case(extractor, case) for case in fixture["cases"]]
    passed = sum(1 for result in results if result["passed"])
    write_cases = [result for result in results if result["expected"]["expect_write"]]
    no_write_cases = [result for result in results if not result["expected"]["expect_write"]]

    return {
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "accuracy": round(passed / len(results), 4) if results else 0.0,
            "write_case_passed": sum(1 for result in write_cases if result["passed"]),
            "write_case_total": len(write_cases),
            "no_write_case_passed": sum(1 for result in no_write_cases if result["passed"]),
            "no_write_case_total": len(no_write_cases),
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live LLM memory extraction calibration.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any case fails.")
    args = parser.parse_args()

    report = run_calibration(args.fixture)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if args.strict and report["summary"]["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
