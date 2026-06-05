from typing import Any

import structlog
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from config import settings
from .prompts import EXECUTOR_PROMPT
from .state import AgentState
from .tools import tools as agent_tools

log = structlog.get_logger()


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.agent_model,
        temperature=settings.agent_temperature,
        base_url=f"{settings.llm_gateway_url}/v1",
        api_key="sk-noop",
    )


async def executor(state: AgentState) -> dict[str, Any]:
    """Execute the current plan step using the LLM with tools."""
    step = state.plan[state.current_step] if state.plan and state.current_step < len(state.plan) else ""
    step_context = f"Current step ({state.current_step + 1}/{len(state.plan)}): {step}" if step else ""

    llm = _build_llm().bind_tools(agent_tools)
    messages = [
        SystemMessage(content=EXECUTOR_PROMPT),
        *([SystemMessage(content=step_context)] if step_context else []),
        *state.messages,
    ]
    response: AIMessage = await llm.ainvoke(messages)
    return {"messages": [response]}


async def execute_tools(state: AgentState) -> dict[str, Any]:
    tool_map = {t.name: t for t in agent_tools}
    last_message = state.messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {}

    results: list[ToolMessage] = []
    errors: list[str] = []

    for tc in last_message.tool_calls:
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            msg = f"Unknown tool: {tc['name']}"
            results.append(ToolMessage(content=msg, tool_call_id=tc["id"]))
            errors.append(msg)
            continue

        try:
            output = await tool_fn.ainvoke(tc["args"])
            results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
        except Exception as exc:
            log.error("tool_call_failed", tool=tc["name"], error=str(exc))
            msg = f"Error calling {tc['name']}: {exc!s}"
            results.append(ToolMessage(content=msg, tool_call_id=tc["id"]))
            errors.append(msg)

    return {"messages": results, "tool_errors": errors}


async def advance_check(state: AgentState) -> dict[str, Any]:
    """Advance to the next plan step."""
    next_step = state.current_step + 1
    if next_step < len(state.plan):
        return {"current_step": next_step}
    return {}


def should_continue(state: AgentState) -> str:
    """After executor: route to tools, HITL, or advance."""
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        if any(tc["name"] == "book_room" for tc in last_message.tool_calls):
            return "human_approval"
        return "tools"
    return "advance"


def should_retry(state: AgentState) -> str:
    if state.tool_errors and state.retry_count < 2:
        return "reflect"
    return "advance"


def should_advance_fn(state: AgentState) -> str:
    """After advancing: route to next executor step or end."""
    if state.current_step >= len(state.plan):
        return "end"
    return "executor"
