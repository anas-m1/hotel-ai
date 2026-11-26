import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from opentelemetry import context as otel_context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    _langfuse_client: Any | None = None

    def _get_langfuse_callback() -> CallbackHandler:
        global _langfuse_client
        if _langfuse_client is None:
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_host,
                additional_headers={"x-langfuse-ingestion-version": "4"},
            )
        return CallbackHandler(public_key=settings.langfuse_public_key)
except ImportError:
    _get_langfuse_callback = None
from langgraph.types import Command
from pydantic import BaseModel, Field

from agent.instance import get_graph
from agent.provenance import eval_info
from config import settings

log = structlog.get_logger()
router = APIRouter()


class ChatRequest(BaseModel):
    read_only: bool = False
    message: str
    session_id: str = ""
    user_id: str = ""


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    interrupt: dict[str, Any] | None = None
    # Expose names and outcomes for demos/evals without returning arguments that
    # may contain guest data.
    tool_trace: list[dict[str, str]] = Field(default_factory=list)


class ResumeRequest(BaseModel):
    session_id: str
    approved: bool


def _config(session_id: str, user_id: str = "") -> dict[str, Any]:
    callbacks = []
    if _get_langfuse_callback and settings.langfuse_public_key and settings.langfuse_secret_key:
        callbacks.append(_get_langfuse_callback())
    return {
        "configurable": {"thread_id": session_id},
        "callbacks": callbacks,
        "run_name": "hotel-booking-agent",
        "metadata": {
            "langfuse_session_id": session_id,
            **({"langfuse_user_id": user_id} if user_id else {}),
            "langfuse_tags": ["hotel-ai", "booking-assistant"],
        },
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
        if isinstance(msg, AIMessage) and msg.content:
            return str(msg.content)
    return ""


def _extract_tool_trace(result: dict[str, Any]) -> list[dict[str, str]]:
    call_names: dict[str, str] = {}
    for message in result.get("messages", []):
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                call_names[tool_call["id"]] = tool_call["name"]

    trace = []
    for message in result.get("messages", []):
        if isinstance(message, ToolMessage) and message.tool_call_id in call_names:
            status = (
                "cancelled" if "cancelled by user" in str(message.content).lower() else "executed"
            )
            if message.status == "error":
                status = "failed"
            if message.additional_kwargs.get("execution_status") == "blocked":
                status = "blocked"
            trace.append(
                {
                    "name": call_names[message.tool_call_id],
                    "status": status,
                    "call_id": message.tool_call_id,
                    "error_category": str(message.additional_kwargs.get("error_category", "")),
                }
            )
    return trace


@router.get("/eval-info")
async def evaluation_identity() -> dict:
    """Return configured model and source identity, without credentials or prompts."""
    return eval_info()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request = None) -> dict[str, Any]:
    graph = get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not ready")

    session_id = req.session_id or str(uuid.uuid4())
    config = _config(session_id, req.user_id)

    # Link read-only experiment requests to the SDK experiment observation.
    # Accept only W3C trace context, never remote baggage/settings.
    token = None
    if req.read_only and request and request.headers.get("traceparent"):
        parent = TraceContextTextMapPropagator().extract(dict(request.headers))
        token = otel_context.attach(parent)
    try:
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=req.message)],
                "session_id": session_id,
                "user_id": req.user_id,
                # Each new user message gets a fresh tool budget; resume keeps it.
                "step_count": 0,
                "read_only": req.read_only,
            },
            config,
        )
    finally:
        if token is not None:
            otel_context.detach(token)

    interrupts = await _get_interrupts(session_id)
    reply = _extract_reply(result)
    if not reply:
        log.warning("agent_empty_final_response", session_id=session_id)
        reply = (
            "I couldn't complete that lookup just now. "
            "Please try again with a hotel name or location."
        )

    return {
        "reply": reply,
        "session_id": session_id,
        "interrupt": interrupts[0] if interrupts else None,
        "tool_trace": _extract_tool_trace(result),
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
    if not reply:
        log.warning("agent_empty_final_response", session_id=req.session_id)
        reply = (
            "I couldn't complete that lookup just now. "
            "Please try again with a hotel name or location."
        )

    return {
        "reply": reply,
        "session_id": req.session_id,
        "interrupt": interrupts[0] if interrupts else None,
        "tool_trace": _extract_tool_trace(result),
    }
