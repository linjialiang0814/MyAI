from pydantic import BaseModel


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    created_at: str | None = None
