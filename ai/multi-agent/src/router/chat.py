from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.graph import graph
from agents.state import MultiAgentState
from kafka.producer import publish_agent_event

log = structlog.get_logger()
router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""


class ChatResponse(BaseModel):
    response: str
    workers_called: list[str]
    session_id: str


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty")

    initial_state = MultiAgentState(user_request=req.message)

    try:
        result = await graph.ainvoke(initial_state)
    except Exception as exc:
        log.error("graph_error", error=str(exc), message=req.message)
        raise HTTPException(status_code=500, detail="Agent error — please try again") from exc

    final_state = MultiAgentState.model_validate(result)
    workers_called = [r.worker for r in final_state.worker_results]

    await publish_agent_event(
        "agent.conversation.completed",
        {
            "session_id": req.session_id,
            "workers_called": workers_called,
            "user_request_length": len(req.message),
        },
    )

    return ChatResponse(
        response=final_state.final_response or "I was unable to complete your request.",
        workers_called=workers_called,
        session_id=req.session_id,
    )
