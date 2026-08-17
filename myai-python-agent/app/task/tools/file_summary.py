import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from app.knowledge.service import KnowledgeService
from app.task.tool.tool import Tool, ToolPolicy, ToolResult


class FileSummaryArgs(BaseModel):
    query: str | None = Field(default=None, description="The user's summary request")
    file_id: str | None = Field(default=None, description="Knowledge-base file id")
    file_name: str | None = Field(default=None, description="Knowledge-base file name")
    user_id: str | None = Field(default=None, description="Runtime user id")


class FileSummaryTool(Tool):
    name = "file_summary"
    description = "Summarize a file from the personal knowledge base."
    args = FileSummaryArgs
    policy = ToolPolicy(risk_level="filesystem", timeout_seconds=15.0)
    trigger_words = {
        "summarize file": 1.4,
        "file summary": 1.2,
        "document summary": 1.2,
        "总结文件": 1.5,
        "总结文档": 1.5,
        "文件总结": 1.4,
        "文档总结": 1.4,
    }

    def __init__(self, knowledge_service: KnowledgeService | None = None) -> None:
        self.knowledge_service = knowledge_service or KnowledgeService()

    def prepare_args(self, args: dict[str, Any] | None, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
        prepared = dict(args or {})
        if prepared.get("user_id"):
            return prepared
        if runtime_context and runtime_context.get("user_id"):
            prepared["user_id"] = runtime_context["user_id"]
        return prepared

    def extract_args(self, content: str) -> dict[str, Any]:
        stripped = content.strip()
        file_match = re.search(r"([A-Za-z0-9_\-\u4e00-\u9fff]+\.(?:pdf|docx|txt))", stripped, re.IGNORECASE)
        payload: dict[str, Any] = {"query": stripped}
        if file_match:
            payload["file_name"] = file_match.group(1)
        return payload

    def run(self, **kwargs) -> ToolResult:
        user_id = kwargs.get("user_id")
        if not user_id:
            return ToolResult(success=False, error="File summary requires a user_id context.")

        file_id = kwargs.get("file_id")
        file_name = kwargs.get("file_name")
        query = (kwargs.get("query") or "").strip()

        entry = self.knowledge_service.get_file_entry(user_id, file_id=file_id, file_name=file_name)
        if entry is None and query:
            hits = self.knowledge_service.query(user_id, query, top_k=1)
            if hits:
                entry = self.knowledge_service.get_file_entry(user_id, file_id=hits[0]["file_id"])

        if entry is None:
            return ToolResult(success=False, error="No matching knowledge-base file was found for summarization.")

        text = self.knowledge_service.get_file_text(user_id, file_id=entry["file_id"])
        profile = entry.get("document_profile") or {}
        if not profile and text:
            profile = self.knowledge_service._build_document_profile(text, entry["file_name"], entry["file_type"])
        if not text and not profile:
            return ToolResult(success=False, error="The target file could not be read.")

        highlights = profile.get("important_passages") or self._extract_highlights(text or "")
        keywords = profile.get("keywords") or self._extract_keywords(text or "")
        summary = profile.get("short_summary") or self.knowledge_service._build_summary(text or "", max_length=220)
        data = {
            "file_id": entry["file_id"],
            "file_name": entry["file_name"],
            "file_type": entry["file_type"],
            "uploaded_at": entry["uploaded_at"],
            "chunk_count": entry["chunk_count"],
            "summary": summary,
            "highlights": highlights,
            "keywords": keywords,
            "document_profile": profile,
            "outline": profile.get("outline", []),
            "possible_questions": profile.get("possible_questions", []),
            "document_language": profile.get("document_language", "unknown"),
        }
        return ToolResult(success=True, data=data)

    @staticmethod
    def _extract_highlights(text: str, max_items: int = 3) -> list[str]:
        parts = [part.strip() for part in re.split(r"[\r\n。！？!?]+", text) if part.strip()]
        return parts[:max_items]

    @staticmethod
    def _extract_keywords(text: str, max_items: int = 5) -> list[str]:
        chinese_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        english_tokens = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
        tokens = [token for token in chinese_tokens + english_tokens if token not in {"这是", "一个", "我们", "about", "with", "from"}]
        if not tokens:
            return []
        return [token for token, _ in Counter(tokens).most_common(max_items)]
