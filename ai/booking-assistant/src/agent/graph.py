from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .hitl import human_approval_edge, human_approval_node
from .nodes import (
    advance_check,
    executor,
    execute_tools,
    should_advance_fn,
    should_continue,
    should_retry,
)
from .planner import create_plan
from .reflection import reflect_on_error
from .state import AgentState


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", create_plan)
    workflow.add_node("executor", executor)
    workflow.add_node("tools", execute_tools)
    workflow.add_node("reflect", reflect_on_error)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("advance_check", advance_check)

    workflow.set_entry_point("planner")

    workflow.add_edge("planner", "executor")

    workflow.add_conditional_edges(
        "executor",
        should_continue,
        {"tools": "tools", "human_approval": "human_approval", "advance": "advance_check"},
    )

    workflow.add_conditional_edges(
        "human_approval",
        human_approval_edge,
        {"tools": "tools", "advance": "advance_check"},
    )

    workflow.add_conditional_edges(
        "tools",
        should_retry,
        {"reflect": "reflect", "advance": "advance_check"},
    )

    workflow.add_edge("reflect", "executor")

    workflow.add_conditional_edges(
        "advance_check",
        should_advance_fn,
        {"executor": "executor", "end": END},
    )

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
