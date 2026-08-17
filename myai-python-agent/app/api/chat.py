from app.schemas.chat_request import ChatRequest
from app.schemas.chat_response import ChatResponse
from app.schemas.agent_trace import AgentRunResponse, AgentStepResponse
from app.api.dependencies import get_agent_service
from app.core.service import AgentService

from fastapi import APIRouter, Depends, Header, HTTPException

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    agent_service: AgentService = Depends(get_agent_service),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not request.message.strip():
        raise HTTPException(status_code = 400, detail="Empty message")

    idempotency_key = _resolve_idempotency_key(request.idempotency_key, idempotency_header)
    result = agent_service.generate_reply(
        user_id=request.user_id,
        message=request.message,
        conversation_id=request.conversation_id,
        history=[item.model_dump() for item in request.history] if request.history else None,
        idempotency_key=idempotency_key,
    )
    trace = AgentRunResponse(
        run_id=result.trace.run_id,
        status=result.trace.status,
        started_at=result.trace.started_at,
        finished_at=result.trace.finished_at,
        steps=[AgentStepResponse(**step.__dict__) for step in result.trace.steps],
    )

    return ChatResponse(
        reply=result.reply,
        run_id=result.trace.run_id,
        trace=trace
    )


def _resolve_idempotency_key(body_key: str | None, header_key: str | None) -> str | None:
    normalized_body = (body_key or "").strip()
    normalized_header = (header_key or "").strip()
    if normalized_body and normalized_header and normalized_body != normalized_header:
        raise HTTPException(status_code=400, detail="Idempotency key header and body value differ")
    return normalized_header or normalized_body or None

