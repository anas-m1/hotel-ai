"""Scenario-based eval tests for the booking assistant agent.

These tests validate the agent graph structure, routing logic, and tool
definitions. Full end-to-end tests require running Go services + LLM gateway.
"""

from agent.graph import build_graph
from agent.nodes import MAX_STEPS, route_after_agent
from agent.state import AgentState


def test_graph_compiles():
    graph = build_graph()
    assert graph is not None
    nodes = list(graph.nodes.keys())
    assert "agent" in nodes
    assert "tools" in nodes
    assert "human_approval" in nodes
    assert len(nodes) == 4  # __start__ + agent + tools + human_approval


def test_route_after_agent_tool_calls():
    from langchain_core.messages import AIMessage

    msg = AIMessage(content="", tool_calls=[{"name": "search_hotels", "args": {}, "id": "1"}])
    state = AgentState(messages=[msg], step_count=0)
    assert route_after_agent(state) == "tools"


def test_route_after_agent_book_room():
    from langchain_core.messages import AIMessage

    msg = AIMessage(
        content="",
        tool_calls=[{"name": "book_room", "args": {"hotel_code": "NYC001"}, "id": "1"}],
    )
    state = AgentState(messages=[msg], step_count=0)
    assert route_after_agent(state) == "human_approval"


def test_route_after_agent_final_answer():
    from langchain_core.messages import AIMessage

    msg = AIMessage(content="Here are the available hotels...")
    state = AgentState(messages=[msg], step_count=1)
    assert route_after_agent(state) == "end"


def test_route_after_agent_max_steps():
    from langchain_core.messages import AIMessage

    msg = AIMessage(content="", tool_calls=[{"name": "search_hotels", "args": {}, "id": "1"}])
    state = AgentState(messages=[msg], step_count=MAX_STEPS)
    assert route_after_agent(state) == "end"


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
