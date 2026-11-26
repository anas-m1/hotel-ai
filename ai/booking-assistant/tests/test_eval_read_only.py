"""Read-only evals must not rely on model compliance for side-effect safety."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from langchain_core.messages import AIMessage

import agent.nodes as nodes
from agent.state import AgentState
from router.chat import _extract_tool_trace


class ReadOnlyTests(unittest.TestCase):
    def test_mutations_and_unknown_tools_never_execute(self):
        for name in ["create_guest", "book_room", "future_mutation"]:
            with self.subTest(name=name):
                tool = SimpleNamespace(name=name, ainvoke=AsyncMock())
                call = AIMessage(content="", tool_calls=[{"name": name, "args": {}, "id": "one"}])
                with patch.object(nodes, "agent_tools", [tool]):
                    result = asyncio.run(
                        nodes.execute_tools(AgentState(messages=[call], read_only=True))
                    )
                tool.ainvoke.assert_not_awaited()
                trace = _extract_tool_trace({"messages": [call, *result["messages"]]})
                self.assertEqual(trace[0]["status"], "blocked")
                self.assertEqual(trace[0]["call_id"], "one")

    def test_read_tool_still_executes(self):
        tool = SimpleNamespace(name="get_hotel", ainvoke=AsyncMock(return_value={"name": "Test"}))
        call = AIMessage(content="", tool_calls=[{"name": "get_hotel", "args": {}, "id": "one"}])
        with patch.object(nodes, "agent_tools", [tool]):
            result = asyncio.run(nodes.execute_tools(AgentState(messages=[call], read_only=True)))
        tool.ainvoke.assert_awaited_once()
        self.assertEqual(result["messages"][0].status, "success")

    def test_read_only_booking_is_blocked_instead_of_pausing(self):
        call = AIMessage(content="", tool_calls=[{"name": "book_room", "args": {}, "id": "one"}])
        self.assertEqual(
            nodes.route_after_agent(AgentState(messages=[call], read_only=True)), "tools"
        )
        self.assertEqual(nodes.route_after_agent(AgentState(messages=[call])), "human_approval")

    def test_service_error_is_visible_and_classified(self):
        tool = SimpleNamespace(
            name="get_hotel", ainvoke=AsyncMock(side_effect=httpx.ConnectError("offline"))
        )
        call = AIMessage(content="", tool_calls=[{"name": "get_hotel", "args": {}, "id": "one"}])
        with patch.object(nodes, "agent_tools", [tool]):
            result = asyncio.run(nodes.execute_tools(AgentState(messages=[call], read_only=True)))
        trace = _extract_tool_trace({"messages": [call, *result["messages"]]})
        self.assertEqual(trace[0]["status"], "failed")
        self.assertEqual(trace[0]["error_category"], "operational")


if __name__ == "__main__":
    unittest.main()
