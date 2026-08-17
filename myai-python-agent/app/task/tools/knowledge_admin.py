from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.knowledge.evaluation.report import DEFAULT_FIXTURE, render_markdown, run_knowledge_report
from app.knowledge.service import KnowledgeService
from app.task.tool.tool import Tool, ToolPolicy, ToolResult


KnowledgeAdminOperation = Literal[
    "document_qa",
    "study_notes",
    "qa_cards",
    "compare_documents",
    "maintenance",
    "eval_report",
]


class KnowledgeAdminArgs(BaseModel):
    operation: KnowledgeAdminOperation = Field(description="Knowledge workflow operation to run.")
    user_id: str | None = Field(default=None, description="Runtime user id.")
    query: str | None = Field(default=None, description="Natural-language request or lookup query.")
    question: str | None = Field(default=None, description="Question for document-scoped QA.")
    file_id: str | None = Field(default=None, description="Primary knowledge-base file id.")
    file_name: str | None = Field(default=None, description="Primary knowledge-base file name.")
    other_file_id: str | None = Field(default=None, description="Secondary file id for comparison.")
    other_file_name: str | None = Field(default=None, description="Secondary file name for comparison.")
    top_k: int = Field(default=3, ge=1, le=10, description="Maximum evidence chunks.")
    dry_run: bool = Field(default=True, description="Run maintenance without applying changes.")
    rebuild: bool = Field(default=False, description="Rebuild selected knowledge file during maintenance.")
    report_format: Literal["summary", "markdown", "json"] = Field(default="summary", description="Eval report format.")
    fixture_path: str | None = Field(default=None, description="Optional knowledge eval fixture path.")


class KnowledgeAdminTool(Tool):
    name = "knowledge_admin"
    description = "Run knowledge-base QA, study-note, maintenance, evaluation, and comparison workflows."
    args = KnowledgeAdminArgs
    policy = ToolPolicy(risk_level="filesystem", timeout_seconds=30.0)
    trigger_words = {
        "knowledge qa": 1.5,
        "document qa": 1.5,
        "study notes": 1.4,
        "qa cards": 1.4,
        "compare documents": 1.6,
        "knowledge maintenance": 1.6,
        "knowledge eval": 1.6,
        "knowledge report": 1.4,
        "文档问答": 1.6,
        "学习笔记": 1.5,
        "知识库维护": 1.6,
        "知识库评测": 1.6,
    }

    def __init__(self, knowledge_service: KnowledgeService | None = None) -> None:
        self.knowledge_service = knowledge_service or KnowledgeService()

    def prepare_args(self, args: dict[str, Any] | None, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
        prepared = dict(args or {})
        if not prepared.get("user_id") and runtime_context and runtime_context.get("user_id"):
            prepared["user_id"] = runtime_context["user_id"]
        if not prepared.get("query") and runtime_context and runtime_context.get("content"):
            prepared["query"] = runtime_context["content"]
        return prepared

    def policy_for_args(
        self,
        args: dict[str, Any] | None,
        runtime_context: dict[str, Any] | None = None,
    ) -> ToolPolicy:
        operation = (args or {}).get("operation")
        if operation == "maintenance" and (not (args or {}).get("dry_run", True) or (args or {}).get("rebuild")):
            return ToolPolicy(risk_level="filesystem", timeout_seconds=30.0, requires_confirmation=True)
        return self.policy

    def extract_args(self, content: str) -> dict[str, Any]:
        normalized = content.lower()
        operation: KnowledgeAdminOperation = "document_qa"
        if any(token in normalized or token in content for token in ["maintenance", "maintain", "知识库维护", "修复知识库"]):
            operation = "maintenance"
        elif any(token in normalized or token in content for token in ["eval", "report", "评测", "报告"]):
            operation = "eval_report"
        elif any(token in normalized or token in content for token in ["compare", "对比", "比较"]):
            operation = "compare_documents"
        elif any(token in normalized or token in content for token in ["qa cards", "flashcards", "问答卡", "题卡"]):
            operation = "qa_cards"
        elif any(token in normalized or token in content for token in ["study notes", "学习笔记", "复习笔记"]):
            operation = "study_notes"
        elif any(token in normalized or token in content for token in ["document qa", "ask document", "文档问答", "问这个文档"]):
            operation = "document_qa"

        names = re.findall(r"([A-Za-z0-9_\-\u4e00-\u9fff]+\.(?:pdf|docx|txt))", content, flags=re.IGNORECASE)
        payload: dict[str, Any] = {
            "operation": operation,
            "query": content.strip(),
            "question": content.strip(),
        }
        if names:
            payload["file_name"] = names[0]
        if len(names) > 1:
            payload["other_file_name"] = names[1]
        if "markdown" in normalized:
            payload["report_format"] = "markdown"
        return payload

    def run(
        self,
        *,
        operation: KnowledgeAdminOperation,
        user_id: str | None = None,
        query: str | None = None,
        question: str | None = None,
        file_id: str | None = None,
        file_name: str | None = None,
        other_file_id: str | None = None,
        other_file_name: str | None = None,
        top_k: int = 3,
        dry_run: bool = True,
        rebuild: bool = False,
        report_format: str = "summary",
        fixture_path: str | None = None,
    ) -> ToolResult:
        if operation == "eval_report":
            path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE
            report = run_knowledge_report(path)
            if report_format == "markdown":
                payload: Any = {"format": "markdown", "content": render_markdown(report), "summary": report["summary"]}
            elif report_format == "json":
                payload = report
            else:
                payload = {"format": "summary", "summary": report["summary"]}
            return ToolResult(success=True, data={"operation": operation, "report": payload})

        if not user_id:
            return ToolResult(success=False, error=f"{operation} requires user_id")

        if operation == "maintenance":
            report = self.knowledge_service.maintain(user_id, dry_run=dry_run, file_id=file_id, rebuild=rebuild)
            return ToolResult(success=True, data={"operation": operation, "report": report, "summary": _maintenance_summary(report)})
        if operation == "document_qa":
            entry = self._resolve_entry(user_id, file_id=file_id, file_name=file_name, query=query or question)
            if entry is None:
                return ToolResult(success=False, error="No matching knowledge-base file was found for document QA.")
            answer = self.knowledge_service.answer_document_question(user_id, entry["file_id"], question or query or "", top_k=top_k)
            return ToolResult(success=True, data={"operation": operation, **answer})
        if operation == "study_notes":
            entry = self._resolve_entry(user_id, file_id=file_id, file_name=file_name, query=query)
            if entry is None:
                return ToolResult(success=False, error="No matching knowledge-base file was found for study notes.")
            return ToolResult(success=True, data={"operation": operation, **self._study_notes(user_id, entry, query=query, top_k=top_k)})
        if operation == "qa_cards":
            entry = self._resolve_entry(user_id, file_id=file_id, file_name=file_name, query=query)
            if entry is None:
                return ToolResult(success=False, error="No matching knowledge-base file was found for Q&A cards.")
            return ToolResult(success=True, data={"operation": operation, **self._qa_cards(user_id, entry, top_k=top_k)})
        if operation == "compare_documents":
            first = self._resolve_entry(user_id, file_id=file_id, file_name=file_name, query=query)
            second = self._resolve_entry(user_id, file_id=other_file_id, file_name=other_file_name)
            if first is None or second is None:
                return ToolResult(success=False, error="Two matching knowledge-base files are required for comparison.")
            return ToolResult(success=True, data={"operation": operation, **self._compare_entries(first, second)})
        return ToolResult(success=False, error=f"unsupported knowledge admin operation: {operation}")

    def _resolve_entry(
        self,
        user_id: str,
        *,
        file_id: str | None = None,
        file_name: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any] | None:
        entry = self.knowledge_service.get_file_entry(user_id, file_id=file_id, file_name=file_name)
        if entry is not None:
            return entry
        if query:
            hits = self.knowledge_service.query(user_id, query, top_k=1)
            if hits:
                return self.knowledge_service.get_file_entry(user_id, file_id=hits[0]["file_id"])
        return None

    def _study_notes(self, user_id: str, entry: dict[str, Any], *, query: str | None, top_k: int) -> dict[str, Any]:
        profile = entry.get("document_profile") or self.knowledge_service._legacy_document_profile(entry)
        evidence_query = query or profile.get("title") or entry.get("file_name", "")
        hits = self.knowledge_service.query(user_id, evidence_query, top_k=top_k, file_id=entry["file_id"])
        return {
            "file_id": entry["file_id"],
            "file_name": entry["file_name"],
            "title": profile.get("title", entry["file_name"]),
            "summary": profile.get("short_summary", entry.get("summary", "")),
            "outline": profile.get("outline", []),
            "key_terms": profile.get("keywords", []),
            "highlights": profile.get("important_passages", []),
            "review_questions": profile.get("possible_questions", []),
            "citations": [hit.get("citation", {}) for hit in hits],
            "hits": hits,
        }

    def _qa_cards(self, user_id: str, entry: dict[str, Any], *, top_k: int) -> dict[str, Any]:
        profile = entry.get("document_profile") or self.knowledge_service._legacy_document_profile(entry)
        questions = profile.get("possible_questions") or [f"What does the document say about {entry['file_name']}?"]
        cards = []
        for question in questions[:5]:
            answer = self.knowledge_service.answer_document_question(user_id, entry["file_id"], question, top_k=top_k)
            cards.append(
                {
                    "question": question,
                    "answer": answer.get("answer", ""),
                    "answer_status": answer.get("answer_status", ""),
                    "citations": answer.get("citations", []),
                }
            )
        return {
            "file_id": entry["file_id"],
            "file_name": entry["file_name"],
            "cards": cards,
            "card_count": len(cards),
        }

    @staticmethod
    def _compare_entries(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
        first_profile = first.get("document_profile") or {}
        second_profile = second.get("document_profile") or {}
        first_terms = set(first_profile.get("keywords") or [])
        second_terms = set(second_profile.get("keywords") or [])
        return {
            "files": [
                {"file_id": first["file_id"], "file_name": first["file_name"], "summary": first_profile.get("short_summary", first.get("summary", ""))},
                {"file_id": second["file_id"], "file_name": second["file_name"], "summary": second_profile.get("short_summary", second.get("summary", ""))},
            ],
            "shared_terms": sorted(first_terms & second_terms),
            "first_only_terms": sorted(first_terms - second_terms),
            "second_only_terms": sorted(second_terms - first_terms),
            "comparison_basis": "document_profile_keywords_and_summaries",
        }


def _maintenance_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return (
        f"knowledge maintenance {report.get('status', 'unknown')}: "
        f"files={summary.get('files_checked', 0)}, "
        f"missing_chunks={summary.get('missing_chunks', 0)}, "
        f"orphans={summary.get('orphan_chunks', 0)}, "
        f"duplicates={summary.get('duplicate_groups', 0)}"
    )
