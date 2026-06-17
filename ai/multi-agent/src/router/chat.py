from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from langfuse.callback import CallbackHandler
from pydantic import BaseModel

from agents.graph import build_graph
from agents.state import MultiAgentState
from config import settings
from kafka.producer import publish_agent_event

log = structlog.get_logger()
router = APIRouter()

# Set at startup via set_graph(); falls back to None until then.
_graph: Any = None


def set_graph(g: Any) -> None:
    global _graph
    _graph = g


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""


class ChatResponse(BaseModel):
    response: str
    workers_called: list[str]
    session_id: str


def _invoke_config(session_id: str) -> dict[str, Any]:
    config: dict[str, Any] = {"configurable": {"thread_id": session_id}}
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        config["callbacks"] = [
            CallbackHandler(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                session_id=session_id,
            )
        ]
    return config


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty")

    if _graph is None:
        raise HTTPException(status_code=503, detail="Agent not ready")

    session_id = req.session_id or str(uuid.uuid4())
    initial_state = MultiAgentState(user_request=req.message)

    try:
        result = await _graph.ainvoke(initial_state, _invoke_config(session_id))
    except Exception as exc:
        log.error("graph_error", error=str(exc), message=req.message)
        raise HTTPException(status_code=500, detail="Agent error — please try again") from exc

    final_state = MultiAgentState.model_validate(result)
    workers_called = [r.worker for r in final_state.worker_results]

    await publish_agent_event(
        "agent.conversation.completed",
        {
            "session_id": session_id,
            "workers_called": workers_called,
            "user_request_length": len(req.message),
        },
    )

    return ChatResponse(
        response=final_state.final_response or "I was unable to complete your request.",
        workers_called=workers_called,
        session_id=session_id,
    )
