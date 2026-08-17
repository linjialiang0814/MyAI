from pydantic import BaseModel
from app.schemas.agent_trace import AgentRunResponse

class ChatResponse(BaseModel):
    reply: str
    run_id: str | None = None
    trace: AgentRunResponse | None = None
