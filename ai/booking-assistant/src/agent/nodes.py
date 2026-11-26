from typing import Any

import httpx
import structlog
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from config import settings

from .llm import call_llm
from .prompts import AGENT_PROMPT
from .state import AgentState
from .tools import tools as agent_tools

log = structlog.get_logger()

# Reserve the last LLM call for a text answer so an exhausted tool loop never
# returns an unexecuted tool call as if it were a completed response.
MAX_STEPS = 4
READ_ONLY_TOOLS = frozenset(
    {
        "search_hotels",
        "semantic_search_hotels",
        "get_hotel",
        "list_rooms",
        "check_availability",
        "get_guest",
        "get_booking",
    }
)


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.agent_model,
        temperature=settings.agent_temperature,
        base_url=f"{settings.llm_gateway_url}/v1",
        api_key="sk-noop",
        model_kwargs={"max_tokens": 1024},
    )


async def agent_node(state: AgentState) -> dict[str, Any]:
    """ReAct agent: think → act → observe loop."""
    llm = _build_llm()
    if state.step_count < MAX_STEPS - 1:
        llm = llm.bind_tools(agent_tools, tool_choice="auto")
    else:
        log.info("agent_final_answer_mode", step_count=state.step_count)
    messages = [SystemMessage(content=AGENT_PROMPT), *state.messages]
    response = await call_llm(llm, messages)
    return {"messages": [response], "step_count": state.step_count + 1}


async def execute_tools(state: AgentState) -> dict[str, Any]:
    tool_map = {t.name: t for t in agent_tools}
    last_message = state.messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {}

    results: list[ToolMessage] = []

    for tc in last_message.tool_calls:
        if state.read_only and tc["name"] not in READ_ONLY_TOOLS:
            results.append(
                ToolMessage(
                    content="This action is blocked in read-only evaluation mode.",
                    tool_call_id=tc["id"],
                    status="error",
                    additional_kwargs={"execution_status": "blocked", "error_category": "policy"},
                )
            )
            continue
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            results.append(
                ToolMessage(
                    content=f"Unknown tool: {tc['name']}",
                    tool_call_id=tc["id"],
                    status="error",
                    additional_kwargs={"error_category": "tool_selection"},
                )
            )
            continue

        try:
            output = await tool_fn.ainvoke(tc["args"])
            results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
        except Exception as exc:
            category = "tool_execution"
            if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
                category = "operational"
            elif isinstance(exc, httpx.HTTPStatusError):
                category = (
                    "operational"
                    if exc.response.status_code >= 500 or exc.response.status_code == 429
                    else "tool_input"
                )
            elif isinstance(exc, ValidationError):
                category = "tool_input"
            log.error("tool_call_failed", tool=tc["name"], error_type=type(exc).__name__)
            results.append(
                ToolMessage(
                    content=f"Error calling {tc['name']}: {type(exc).__name__}",
                    tool_call_id=tc["id"],
                    status="error",
                    additional_kwargs={"error_category": category},
                )
            )

    return {"messages": results}


def route_after_agent(state: AgentState) -> str:
    """Route: tool calls → tools, book_room → HITL, else → end."""
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        if not state.read_only and any(tc["name"] == "book_room" for tc in last_message.tool_calls):
            return "human_approval"
        if state.step_count >= MAX_STEPS:
            return "end"
        return "tools"
    return "end"
