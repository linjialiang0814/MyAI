from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evaluation.run import render_markdown, run_eval_suite
from app.observability.store import observability_store


@dataclass(frozen=True)
class QualityGateConfig:
    min_pass_rate: float = 1.0
    max_failed_reports: int = 0
    max_failed_cases: int = 0
    max_failed_cases_delta: int | None = 0
    max_pass_rate_drop: float | None = 0.0
    require_status_passed: bool = True
    report_min_pass_rate: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_pass_rate": self.min_pass_rate,
            "max_failed_reports": self.max_failed_reports,
            "max_failed_cases": self.max_failed_cases,
            "max_failed_cases_delta": self.max_failed_cases_delta,
            "max_pass_rate_drop": self.max_pass_rate_drop,
            "require_status_passed": self.require_status_passed,
            "report_min_pass_rate": self.report_min_pass_rate,
        }


DEFAULT_QUALITY_GATE_CONFIG = QualityGateConfig()


def quality_gate_config_from_dict(payload: dict[str, Any] | None) -> QualityGateConfig:
    if not payload:
        return DEFAULT_QUALITY_GATE_CONFIG
    return QualityGateConfig(
        min_pass_rate=float(payload.get("min_pass_rate", DEFAULT_QUALITY_GATE_CONFIG.min_pass_rate)),
        max_failed_reports=int(payload.get("max_failed_reports", DEFAULT_QUALITY_GATE_CONFIG.max_failed_reports)),
        max_failed_cases=int(payload.get("max_failed_cases", DEFAULT_QUALITY_GATE_CONFIG.max_failed_cases)),
        max_failed_cases_delta=_optional_int(payload.get("max_failed_cases_delta", DEFAULT_QUALITY_GATE_CONFIG.max_failed_cases_delta)),
        max_pass_rate_drop=_optional_float(payload.get("max_pass_rate_drop", DEFAULT_QUALITY_GATE_CONFIG.max_pass_rate_drop)),
        require_status_passed=bool(payload.get("require_status_passed", DEFAULT_QUALITY_GATE_CONFIG.require_status_passed)),
        report_min_pass_rate=dict(payload.get("report_min_pass_rate") or {}),
    )


def run_quality_gate(
    suite: str = "all",
    *,
    include_live: bool = False,
    config: QualityGateConfig | dict[str, Any] | None = None,
    record: bool = True,
) -> dict[str, Any]:
    normalized_config = quality_gate_config_from_dict(config if isinstance(config, dict) else None) if not isinstance(config, QualityGateConfig) else config
    report = run_eval_suite(suite=suite, include_live=include_live, record=record)
    history = observability_store.eval_summary() if record else {}
    gate = evaluate_quality_gate(report, config=normalized_config, history_delta=history.get("delta"))
    report["quality_gate"] = gate
    return report


def run_maintenance_report(
    suite: str = "all",
    *,
    include_live: bool = False,
    config: QualityGateConfig | dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = run_quality_gate(suite=suite, include_live=include_live, config=config, record=True)
    history = observability_store.eval_summary()
    gate = report["quality_gate"]
    return {
        "summary": {
            "suite": suite,
            "status": "passed" if gate["passed"] else "failed",
            "checks": gate["summary"]["checks"],
            "failed_checks": gate["summary"]["failed_checks"],
            "eval_status": report["summary"]["status"],
            "pass_rate": report["summary"]["pass_rate"],
        },
        "quality_gate": gate,
        "history": history,
        "recommendations": build_maintenance_recommendations(gate, history),
        "eval": report,
    }


def evaluate_quality_gate(
    report: dict[str, Any],
    *,
    config: QualityGateConfig = DEFAULT_QUALITY_GATE_CONFIG,
    history_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = report.get("summary") or {}
    checks = [
        _check(
            "suite_status",
            not config.require_status_passed or summary.get("status") == "passed",
            f"Suite status must be passed; actual={summary.get('status', 'unknown')}.",
            "Run the failing report directly and inspect its case-level output.",
        ),
        _check(
            "suite_pass_rate",
            float(summary.get("pass_rate") or 0) >= config.min_pass_rate,
            f"Suite pass rate must be >= {config.min_pass_rate:.2%}; actual={float(summary.get('pass_rate') or 0):.2%}.",
            "Inspect failed cases before changing thresholds.",
        ),
        _check(
            "failed_reports",
            int(summary.get("failed_reports") or 0) <= config.max_failed_reports,
            f"Failed reports must be <= {config.max_failed_reports}; actual={int(summary.get('failed_reports') or 0)}.",
            "Open the failed report content and fix the first deterministic regression.",
        ),
        _check(
            "failed_cases",
            int(summary.get("failed") or 0) <= config.max_failed_cases,
            f"Failed cases must be <= {config.max_failed_cases}; actual={int(summary.get('failed') or 0)}.",
            "Use the report case ids as the maintenance queue.",
        ),
    ]
    checks.extend(_report_checks(report, config))
    checks.extend(_delta_checks(history_delta, config))
    failed_checks = [check for check in checks if not check["passed"]]
    return {
        "passed": not failed_checks,
        "status": "passed" if not failed_checks else "failed",
        "config": config.to_dict(),
        "summary": {
            "checks": len(checks),
            "passed_checks": len(checks) - len(failed_checks),
            "failed_checks": len(failed_checks),
        },
        "checks": checks,
    }


def build_maintenance_recommendations(gate: dict[str, Any], history: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations = []
    failed_checks = [check for check in gate.get("checks", []) if not check.get("passed")]
    for check in failed_checks:
        recommendations.append(
            {
                "priority": "high",
                "source": check.get("id"),
                "title": check.get("message"),
                "next_action": check.get("remediation"),
            }
        )
    delta = history.get("delta") or {}
    if not failed_checks and delta and (delta.get("failed_cases_delta") or 0) > 0:
        recommendations.append(
            {
                "priority": "medium",
                "source": "history_delta",
                "title": "Failed cases increased compared with the previous eval run.",
                "next_action": "Compare latest and previous report ids before merging larger changes.",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "priority": "low",
                "source": "quality_gate",
                "title": "All configured quality gates passed.",
                "next_action": "Keep the current eval history as the baseline for future regression deltas.",
            }
        )
    return recommendations


def render_quality_markdown(report: dict[str, Any]) -> str:
    gate = report.get("quality_gate") or {}
    lines = [
        render_markdown(report),
        "",
        "## Quality Gate",
        "",
        f"- Status: {gate.get('status', 'unknown')}",
        f"- Checks: {(gate.get('summary') or {}).get('passed_checks', 0)}/{(gate.get('summary') or {}).get('checks', 0)} passed",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in gate.get("checks", []):
        lines.append(f"| {_md(check['id'])} | {'passed' if check['passed'] else 'failed'} | {_md(check['message'])} |")
    return "\n".join(lines)


def render_maintenance_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MyAI Maintenance Report",
        "",
        f"- Suite: {report['summary']['suite']}",
        f"- Status: {report['summary']['status']}",
        f"- Eval status: {report['summary']['eval_status']}",
        f"- Pass rate: {report['summary']['pass_rate']:.2%}",
        f"- Failed checks: {report['summary']['failed_checks']}",
        "",
        "## Recommendations",
        "",
    ]
    for item in report.get("recommendations", []):
        lines.append(f"- [{item['priority']}] {item['title']} Next: {item['next_action']}")
    lines.extend(["", "## Quality Gate", ""])
    for check in report.get("quality_gate", {}).get("checks", []):
        lines.append(f"- [{'x' if check['passed'] else ' '}] {check['id']}: {check['message']}")
    return "\n".join(lines)


def _report_checks(report: dict[str, Any], config: QualityGateConfig) -> list[dict[str, Any]]:
    checks = []
    for item in report.get("reports", []):
        threshold = config.report_min_pass_rate.get(item.get("report_id")) or config.report_min_pass_rate.get(item.get("domain"))
        if threshold is None:
            continue
        pass_rate = float((item.get("summary") or {}).get("pass_rate") or 0)
        checks.append(
            _check(
                f"report_pass_rate:{item.get('report_id')}",
                pass_rate >= float(threshold),
                f"{item.get('name')} pass rate must be >= {float(threshold):.2%}; actual={pass_rate:.2%}.",
                "Inspect this report's failed cases and keep the threshold domain-specific.",
            )
        )
    return checks


def _delta_checks(history_delta: dict[str, Any] | None, config: QualityGateConfig) -> list[dict[str, Any]]:
    if not history_delta:
        return []
    checks = []
    if config.max_failed_cases_delta is not None:
        failed_delta = int(history_delta.get("failed_cases_delta") or 0)
        checks.append(
            _check(
                "failed_cases_delta",
                failed_delta <= config.max_failed_cases_delta,
                f"Failed case delta must be <= {config.max_failed_cases_delta}; actual={failed_delta}.",
                "Compare latest and previous eval records to identify the new failing cases.",
            )
        )
    if config.max_pass_rate_drop is not None:
        pass_rate_delta = float(history_delta.get("pass_rate_delta") or 0)
        checks.append(
            _check(
                "pass_rate_delta",
                pass_rate_delta >= -abs(config.max_pass_rate_drop),
                f"Pass rate drop must be <= {abs(config.max_pass_rate_drop):.2%}; actual={pass_rate_delta:.2%}.",
                "Review recent code changes in the affected report domain.",
            )
        )
    return checks


def _check(check_id: str, passed: bool, message: str, remediation: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": bool(passed),
        "status": "passed" if passed else "failed",
        "message": message,
        "remediation": remediation,
    }


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
