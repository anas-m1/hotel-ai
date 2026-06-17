"""
Supervisor + worker graph.

Topology:
  START → supervisor → search_agent ──┐
                     → booking_agent ─┤→ supervisor → END
                     → END (FINISH)

The supervisor runs after every worker to decide: call another worker,
or synthesize the final response (FINISH).
"""

from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from agents.state import MultiAgentState
from agents.supervisor import supervisor_node
from agents.workers import booking_agent_node, search_agent_node


def _route(state: MultiAgentState) -> Literal["search_agent", "booking_agent", "__end__"]:
    if state.next_worker == "FINISH":
        return END
    return state.next_worker  # type: ignore[return-value]


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    builder = StateGraph(MultiAgentState)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("search_agent", search_agent_node)
    builder.add_node("booking_agent", booking_agent_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", _route)

    # After each worker finishes, return to supervisor
    builder.add_edge("search_agent", "supervisor")
    builder.add_edge("booking_agent", "supervisor")

    return builder.compile(checkpointer=checkpointer)
