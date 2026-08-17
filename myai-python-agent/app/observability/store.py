from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_RUNS_PATH = Path(
    os.getenv(
        "MYAI_OBSERVABILITY_STORE_PATH",
        str(BASE_DIR / ".runtime" / "observability" / "eval_runs.jsonl"),
    )
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ObservabilityStore:
    def __init__(self, max_eval_runs: int = 50, persist_path: str | Path | None = DEFAULT_EVAL_RUNS_PATH) -> None:
        self.max_eval_runs = max_eval_runs
        self.persist_path = Path(persist_path) if persist_path else None
        self.eval_runs: deque[dict[str, Any]] = deque(maxlen=max_eval_runs)
        self._load_eval_runs()

    def record_eval_run(self, report: dict[str, Any]) -> dict[str, Any]:
        summary = dict(report.get("summary") or {})
        now = utc_now()
        record = {
            "run_id": str(uuid4()),
            "kind": "eval",
            "suite": summary.get("suite", ""),
            "status": summary.get("status", "unknown"),
            "started_at": now,
            "finished_at": now,
            "duration_ms": summary.get("duration_ms", 0),
            "summary": summary,
            "reports": [
                {
                    "report_id": item.get("report_id"),
                    "name": item.get("name"),
                    "domain": item.get("domain"),
                    "status": item.get("status"),
                    "summary": item.get("summary") or {},
                    "duration_ms": item.get("duration_ms", 0),
                    "error": item.get("error"),
                }
                for item in report.get("reports", [])
            ],
        }
        self.eval_runs.appendleft(record)
        self._append_eval_run(record)
        return record

    def list_eval_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        return list(self.eval_runs)[: max(1, limit)]

    def latest_eval_run(self) -> dict[str, Any] | None:
        return self.eval_runs[0] if self.eval_runs else None

    def clear_eval_runs(self, delete_persisted: bool = False) -> None:
        self.eval_runs.clear()
        if delete_persisted and self.persist_path and self.persist_path.exists():
            self.persist_path.unlink()

    def eval_summary(self) -> dict[str, Any]:
        runs = list(self.eval_runs)
        failed = sum(1 for run in runs if run.get("status") == "failed")
        passed = sum(1 for run in runs if run.get("status") == "passed")
        latest = self.latest_eval_run()
        previous = runs[1] if len(runs) > 1 else None
        return {
            "runs": len(runs),
            "passed": passed,
            "failed": failed,
            "latest": latest,
            "previous": previous,
            "delta": self._eval_delta(latest, previous),
            "storage": {
                "persisted": self.persist_path is not None,
                "path": str(self.persist_path) if self.persist_path else None,
                "retention": self.max_eval_runs,
            },
        }

    def _load_eval_runs(self) -> None:
        if not self.persist_path or not self.persist_path.exists():
            return
        records: list[dict[str, Any]] = []
        try:
            lines = self.persist_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("kind") == "eval":
                records.append(record)
        for record in records[-self.max_eval_runs :]:
            self.eval_runs.appendleft(record)

    def _append_eval_run(self, record: dict[str, Any]) -> None:
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self.persist_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            return

    def _eval_delta(self, latest: dict[str, Any] | None, previous: dict[str, Any] | None) -> dict[str, Any] | None:
        if not latest or not previous:
            return None
        latest_summary = latest.get("summary") or {}
        previous_summary = previous.get("summary") or {}
        return {
            "from_run_id": previous.get("run_id"),
            "to_run_id": latest.get("run_id"),
            "status_changed": latest.get("status") != previous.get("status"),
            "pass_rate_delta": self._numeric_delta(latest_summary, previous_summary, "pass_rate"),
            "failed_reports_delta": self._numeric_delta(latest_summary, previous_summary, "failed_reports"),
            "failed_cases_delta": self._numeric_delta(
                latest_summary,
                previous_summary,
                "failed",
                fallback_key="failed_cases",
            ),
            "total_cases_delta": self._numeric_delta(
                latest_summary,
                previous_summary,
                "total",
                fallback_key="total_cases",
            ),
            "duration_ms_delta": self._numeric_delta(latest, previous, "duration_ms"),
        }

    def _numeric_delta(
        self,
        latest: dict[str, Any],
        previous: dict[str, Any],
        key: str,
        *,
        fallback_key: str | None = None,
    ) -> float | int:
        latest_value = self._numeric_value(latest, key, fallback_key)
        previous_value = self._numeric_value(previous, key, fallback_key)
        if isinstance(latest_value, float) or isinstance(previous_value, float):
            return round(float(latest_value) - float(previous_value), 6)
        return int(latest_value) - int(previous_value)

    @staticmethod
    def _numeric_value(payload: dict[str, Any], key: str, fallback_key: str | None) -> Any:
        if key in payload and payload.get(key) is not None:
            return payload[key]
        if fallback_key and fallback_key in payload and payload.get(fallback_key) is not None:
            return payload[fallback_key]
        return 0


observability_store = ObservabilityStore()
