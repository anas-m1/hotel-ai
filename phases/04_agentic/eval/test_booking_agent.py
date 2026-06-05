"""Scenario-based eval tests for the booking assistant agent.

These tests validate the agent graph structure, routing logic, and tool
definitions. Full end-to-end tests require running Go services + LLM gateway.
"""

import pytest
from agent.graph import build_graph
from agent.nodes import advance_check, should_advance_fn, should_continue, should_retry
from agent.state import AgentState


def test_graph_compiles():
    graph = build_graph()
    assert graph is not None
    nodes = list(graph.nodes.keys())
    assert "planner" in nodes
    assert "executor" in nodes
    assert "tools" in nodes
    assert "reflect" in nodes
    assert "human_approval" in nodes
    assert "advance_check" in nodes


def test_should_continue_tools():
    from langchain_core.messages import AIMessage

    msg = AIMessage(content="", tool_calls=[{"name": "search_hotels", "args": {}, "id": "1"}])
    state = AgentState(messages=[msg])
    assert should_continue(state) == "tools"


def test_should_continue_human_approval():
    from langchain_core.messages import AIMessage

    msg = AIMessage(
        content="",
        tool_calls=[{"name": "book_room", "args": {"hotel_code": "NYC001"}, "id": "1"}],
    )
    state = AgentState(messages=[msg])
    assert should_continue(state) == "human_approval"


def test_should_continue_advance():
    from langchain_core.messages import AIMessage

    msg = AIMessage(content="Here are the available hotels...")
    state = AgentState(messages=[msg])
    assert should_continue(state) == "advance"


def test_should_retry_with_errors():
    state = AgentState(tool_errors=["Error calling search_hotels: Connection refused"], retry_count=0)
    assert should_retry(state) == "reflect"


def test_should_retry_no_errors():
    state = AgentState(tool_errors=[], retry_count=0)
    assert should_retry(state) == "advance"


def test_should_retry_max_retries():
    state = AgentState(tool_errors=["Error calling search_hotels: Connection refused"], retry_count=2)
    assert should_retry(state) == "advance"


@pytest.mark.asyncio
async def test_advance_check_increments_step():
    state = AgentState(plan=["step1", "step2", "step3"], current_step=0)
    result = await advance_check(state)
    assert result["current_step"] == 1


@pytest.mark.asyncio
async def test_advance_check_does_not_overflow():
    state = AgentState(plan=["step1"], current_step=0)
    result = await advance_check(state)
    assert result == {}  # already at end, no increment


def test_should_advance_fn_more_steps():
    state = AgentState(plan=["step1", "step2", "step3"], current_step=1)
    assert should_advance_fn(state) == "executor"


def test_should_advance_fn_end():
    state = AgentState(plan=["step1", "step2", "step3"], current_step=3)
    assert should_advance_fn(state) == "end"


def test_tools_module_has_all_tools():
    from agent.tools import tools

    tool_names = {t.name for t in tools}
    expected = {
        "search_hotels",
        "get_hotel",
        "list_rooms",
        "check_availability",
        "semantic_search_hotels",
        "get_guest",
        "create_guest",
        "book_room",
        "get_booking",
    }
    assert tool_names == expected
