import uuid
from typing import Any

import structlog
from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel

from ..agent.graph import build_graph
from ..agent.state import AgentState

log = structlog.get_logger()
router = APIRouter()

_graph = build_graph()


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


def _config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


async def _get_interrupts(session_id: str) -> list[dict[str, Any]]:
    try:
        state = await _graph.aget_state(_config(session_id))
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
    session_id = req.session_id or str(uuid.uuid4())
    config = _config(session_id)

    result = await _graph.ainvoke(
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
    config = _config(req.session_id)

    result = await _graph.ainvoke(Command(resume=req.approved), config)

    interrupts = await _get_interrupts(req.session_id)
    reply = _extract_reply(result)

    return {
        "reply": reply,
        "session_id": req.session_id,
        "interrupt": interrupts[0] if interrupts else None,
    }
