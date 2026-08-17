from typing import Any

import requests
from pydantic import BaseModel, Field

from app.task.tool.tool import Tool, ToolPolicy, ToolResult


class WebSearchArgs(BaseModel):
    query: str = Field(..., description="Search query")
    max_results: int = Field(default=5, ge=1, le=10, description="Maximum number of returned results")


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web for recent or factual information and return concise results."
    args = WebSearchArgs
    idempotent = True
    policy = ToolPolicy(risk_level="network", timeout_seconds=8.0, retry_count=1)
    trigger_words = {
        "search": 1.2,
        "look up": 1.0,
        "find online": 1.0,
        "web": 0.8,
        "搜索": 1.3,
        "网页": 1.0,
        "上网查": 1.1,
        "查一下": 0.9,
    }
    negative_triggers = {"knowledge": 0.8, "memory": 0.6}

    def extract_args(self, content: str) -> dict[str, Any]:
        stripped = content.strip()
        for marker in ["search", "look up", "搜索", "查一下", "上网查"]:
            lowered = stripped.lower()
            index = lowered.find(marker) if marker.isascii() else stripped.find(marker)
            if index != -1:
                value = stripped[index + len(marker) :].strip(" ：:，,。?？")
                if value:
                    return {"query": value}
        return {"query": stripped}

    def run(self, **kwargs) -> ToolResult:
        query = kwargs["query"].strip()
        max_results = int(kwargs.get("max_results", 5))
        try:
            response = requests.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            return ToolResult(success=False, error=f"Web search failed: {exc}")

        results: list[dict[str, Any]] = []
        abstract_text = payload.get("AbstractText")
        abstract_url = payload.get("AbstractURL")
        if abstract_text:
            results.append(
                {
                    "title": payload.get("Heading") or query,
                    "snippet": abstract_text,
                    "url": abstract_url or "",
                    "source": "instant_answer",
                }
            )

        for item in payload.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if "Topics" in item:
                topics = item.get("Topics") or []
            else:
                topics = [item]
            for topic in topics:
                if len(results) >= max_results:
                    break
                text = topic.get("Text")
                url = topic.get("FirstURL", "")
                if text:
                    title, snippet = self._split_topic_text(text)
                    results.append(
                        {
                            "title": title,
                            "snippet": snippet,
                            "url": url,
                            "source": "related_topic",
                        }
                    )

        if not results:
            return ToolResult(success=False, error=f"No web results found for: {query}")

        return ToolResult(success=True, data={"query": query, "results": results[:max_results]})

    @staticmethod
    def _split_topic_text(text: str) -> tuple[str, str]:
        if " - " in text:
            title, snippet = text.split(" - ", 1)
            return title.strip(), snippet.strip()
        return text.strip(), text.strip()
