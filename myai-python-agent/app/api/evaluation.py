from fastapi import APIRouter, HTTPException

from app.evaluation.quality import DEFAULT_QUALITY_GATE_CONFIG
from app.evaluation.quality import run_maintenance_report
from app.evaluation.quality import run_quality_gate
from app.evaluation.run import run_eval_suite
from app.evaluation.registry import get_eval_report, list_eval_reports
from app.observability.store import observability_store


router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.get("/reports")
def list_reports():
    reports = list_eval_reports()
    summary = {
        "total": len(reports),
        "domains": sorted({report["domain"] for report in reports}),
        "deterministic": len([report for report in reports if report.get("deterministic")]),
        "requires_live_llm": len([report for report in reports if report.get("requires_live_llm")]),
    }
    return {"summary": summary, "reports": reports}


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    report = get_eval_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Eval report not found")
    return report


@router.post("/runs")
def run_reports(suite: str = "all", include_live: bool = False):
    try:
        return run_eval_suite(suite=suite, include_live=include_live)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/gates/config")
def get_quality_gate_config():
    return {"config": DEFAULT_QUALITY_GATE_CONFIG.to_dict()}


@router.post("/gates/run")
def run_quality_gate_report(suite: str = "all", include_live: bool = False):
    try:
        return run_quality_gate(suite=suite, include_live=include_live)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/maintenance-report")
def create_maintenance_report(suite: str = "all", include_live: bool = False):
    try:
        return run_maintenance_report(suite=suite, include_live=include_live)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs")
def list_runs(limit: int = 10):
    return {"runs": observability_store.list_eval_runs(limit=limit)}
