from pydantic import BaseModel, Field
from app.schemas.chat_history_message import ChatHistoryMessage

class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=100_000)
    conversation_id: int | None = None
    history: list[ChatHistoryMessage] | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)
