"""
Worker nodes: search_agent and booking_agent.

Each worker is a LangGraph ReAct agent compiled into a subgraph,
then called as a single node from the supervisor graph. This keeps
each specialist isolated — their tool sets don't overlap.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.state import MultiAgentState, WorkerResult
from config import settings
from tools.booking_tools import BOOKING_TOOLS
from tools.search_tools import SEARCH_TOOLS

_SEARCH_SYSTEM = """\
You are a hotel search specialist. Help the user find suitable hotels and rooms.
Use semantic_search_hotels to find properties matching their needs, then list_rooms
to show room options, and check_availability to verify dates. Be concise and specific.
"""

_BOOKING_SYSTEM = """\
You are a hotel booking specialist. Help the user complete reservations.
Look up or create the guest profile first, then create the booking.
If a booking conflict occurs (409), apologize and suggest alternatives.
"""


def _worker_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=f"{settings.llm_gateway_url}/v1",
        api_key="not-needed",
        model=settings.worker_model,
        temperature=settings.agent_temperature,
    )


def _run_worker(system_prompt: str, tools: list, task: str) -> str:
    agent = create_react_agent(_worker_llm(), tools, state_modifier=system_prompt)
    result = agent.invoke({"messages": [HumanMessage(content=task)]})
    last = result["messages"][-1]
    return str(last.content)


def search_agent_node(state: MultiAgentState) -> dict:
    task = next(
        (t["task"] for t in state.worker_tasks if t["worker"] == "search_agent"),
        state.user_request,
    )
    output = _run_worker(_SEARCH_SYSTEM, SEARCH_TOOLS, task)
    result = WorkerResult(worker="search_agent", output=output)
    return {"worker_results": state.worker_results + [result]}


def booking_agent_node(state: MultiAgentState) -> dict:
    task = next(
        (t["task"] for t in state.worker_tasks if t["worker"] == "booking_agent"),
        state.user_request,
    )
    output = _run_worker(_BOOKING_SYSTEM, BOOKING_TOOLS, task)
    result = WorkerResult(worker="booking_agent", output=output)
    return {"worker_results": state.worker_results + [result]}
