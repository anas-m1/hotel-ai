from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .hitl import human_approval_edge, human_approval_node
from .nodes import agent_node, execute_tools, route_after_agent
from .state import AgentState


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", execute_tools)
    workflow.add_node("human_approval", human_approval_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "human_approval": "human_approval", "end": END},
    )

    workflow.add_conditional_edges(
        "human_approval",
        human_approval_edge,
        {"tools": "tools", "end": END},
    )

    workflow.add_edge("tools", "agent")

    return workflow.compile(checkpointer=checkpointer or MemorySaver())
