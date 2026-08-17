from collections import Counter
from pydantic import BaseModel, Field
from app.task.tool.tool import Tool, ToolResult

class TextStatsArgs(BaseModel):
    text: str = Field(..., description="Text to analyze")


class TextStatsTool(Tool):
    name = "text_stats"
    description = "Compute simple text statistics including length, token count and top characters."
    args = TextStatsArgs
    trigger_words = {
        "text": 0.8,
        "word count": 1.2,
        "character count": 1.2,
        "statistics": 0.8,
        "统计": 1.2,
        "字数": 1.0,
        "字符数": 1.0,
        "文本": 0.8,
    }

    def extract_args(self, content: str):
        markers = [":", "：", "text", "文本", "统计"]
        extracted = content
        for marker in markers:
            idx = content.find(marker)
            if idx != -1:
                extracted = content[idx + len(marker):].strip()
                if extracted:
                    break
        return {"text": extracted.strip()}

    def run(self, **kwargs):
        text = kwargs["text"]
        char_counter = Counter(ch for ch in text if not ch.isspace())
        top_characters = char_counter.most_common(5)
        data = {
            "character_count": len(text),
            "character_count_no_space": sum(char_counter.values()),
            "word_count": len(text.split()),
            "line_count": len(text.splitlines()) or 1,
            "top_characters": top_characters,
        }
        return ToolResult(success=True, data=data)