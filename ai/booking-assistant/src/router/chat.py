import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from langfuse.callback import CallbackHandler
from langgraph.types import Command
from pydantic import BaseModel

from ..agent.instance import get_graph
from ..config import settings

log = structlog.get_logger()
router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    user_id: str = ""


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    interrupt: dict[str, Any] | None = None


class ResumeRequest(BaseModel):
    session_id: str
    approved: bool


def _config(session_id: str, user_id: str = "") -> dict[str, Any]:
    callbacks = []
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        callbacks.append(
            CallbackHandler(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                session_id=session_id,
                user_id=user_id or None,
            )
        )
    return {
        "configurable": {"thread_id": session_id},
        "callbacks": callbacks,
    }


async def _get_interrupts(session_id: str) -> list[dict[str, Any]]:
    try:
        graph = get_graph()
        state = await graph.aget_state({"configurable": {"thread_id": session_id}})
        results = []
        for task in state.tasks:
            for interrupt in task.interrupts:
                results.append(interrupt.value)
        return results
    except Exception:
        return []


def _extract_reply(result: dict[str, Any]) -> str:
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content and not isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> dict[str, Any]:
    graph = get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not ready")

    session_id = req.session_id or str(uuid.uuid4())
    config = _config(session_id, req.user_id)

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=req.message)],
            "session_id": session_id,
            "user_id": req.user_id,
            "tool_errors": [],
            "retry_count": 0,
        },
        config,
    )

    interrupts = await _get_interrupts(session_id)
    reply = _extract_reply(result)

    return {
        "reply": reply,
        "session_id": session_id,
        "interrupt": interrupts[0] if interrupts else None,
    }


@router.post("/chat/resume", response_model=ChatResponse)
async def resume(req: ResumeRequest) -> dict[str, Any]:
    graph = get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not ready")

    config = _config(req.session_id)
    result = await graph.ainvoke(Command(resume=req.approved), config)

    interrupts = await _get_interrupts(req.session_id)
    reply = _extract_reply(result)

    return {
        "reply": reply,
        "session_id": req.session_id,
        "interrupt": interrupts[0] if interrupts else None,
    }
