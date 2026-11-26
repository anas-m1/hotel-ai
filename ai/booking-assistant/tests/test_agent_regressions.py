"""Deterministic regressions: no provider, Redis, or real booking calls."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

import agent.graph as graph_module
import agent.nodes as nodes
from agent.state import AgentState
from router import chat as chat_module


class AgentRegressions(unittest.TestCase):
    def test_eval_identity_exposes_only_non_secret_configuration(self):
        from agent.provenance import eval_info

        info = eval_info()
        self.assertEqual(
            set(info),
            {"model", "temperature", "max_steps", "source_sha256", "read_only_evals_supported"},
        )
        self.assertEqual(len(info["source_sha256"]), 64)

    def test_trace_config_groups_conversation_without_requiring_tracing(self):
        with patch.object(chat_module, "_get_langfuse_callback", None):
            config = chat_module._config("demo-session", "demo-user")
            resumed = chat_module._config("demo-session")
        self.assertEqual(config["configurable"]["thread_id"], "demo-session")
        self.assertEqual(config["metadata"]["langfuse_session_id"], "demo-session")
        self.assertEqual(config["metadata"]["langfuse_user_id"], "demo-user")
        self.assertEqual(config["callbacks"], [])
        self.assertEqual(config["run_name"], "hotel-booking-agent")
        self.assertEqual(resumed["metadata"]["langfuse_session_id"], "demo-session")
        self.assertNotIn("langfuse_user_id", resumed["metadata"])

    def test_new_turn_resets_budget_but_preserves_history(self):
        async def scenario():
            bound = []
            histories = []
            replies = iter(
                [
                    AIMessage(
                        content="",
                        tool_calls=[{"name": "search_hotels", "args": {}, "id": f"s{i}"}],
                    )
                    for i in range(nodes.MAX_STEPS - 1)
                ]
                + [
                    AIMessage(content="First answer"),
                    AIMessage(
                        content="", tool_calls=[{"name": "search_hotels", "args": {}, "id": "next"}]
                    ),
                    AIMessage(content="Second answer"),
                ]
            )

            class Model:
                enabled = False

                def bind_tools(self, *args, **kwargs):
                    self.enabled = True
                    return self

                async def ainvoke(self, messages):
                    bound.append(self.enabled)
                    histories.append(messages)
                    return next(replies)

            search = SimpleNamespace(name="search_hotels", ainvoke=AsyncMock(return_value=[]))
            graph = graph_module.build_graph()
            with (
                patch.object(nodes, "_build_llm", side_effect=Model),
                patch.object(nodes, "agent_tools", [search]),
                patch.object(chat_module, "get_graph", return_value=graph),
                patch.object(
                    chat_module,
                    "_config",
                    side_effect=lambda sid, user_id="": {"configurable": {"thread_id": sid}},
                ),
            ):
                for text in ["First search", "Second search"]:
                    await chat_module.chat(
                        chat_module.ChatRequest(message=text, session_id="same-user")
                    )
                snapshot = await graph.aget_state({"configurable": {"thread_id": "same-user"}})
            self.assertFalse(bound[nodes.MAX_STEPS - 1])
            self.assertTrue(bound[nodes.MAX_STEPS])
            self.assertEqual(search.ainvoke.await_count, nodes.MAX_STEPS)
            self.assertEqual(snapshot.values["step_count"], 2)
            self.assertEqual(
                [m.content for m in histories[-1] if isinstance(m, HumanMessage)],
                ["First search", "Second search"],
            )

        asyncio.run(scenario())

    def _approval_scenario(self, approved, extra_call=False):
        async def scenario():
            book = SimpleNamespace(
                name="book_room", ainvoke=AsyncMock(return_value={"id": "test-booking"})
            )
            sibling = SimpleNamespace(
                name="create_guest", ainvoke=AsyncMock(return_value={"id": "test-guest"})
            )
            calls = [{"name": "book_room", "args": {}, "id": "book-1"}]
            if extra_call:
                calls.append({"name": "create_guest", "args": {}, "id": "guest-1"})

            async def scripted_agent(state):
                if isinstance(state.messages[-1], ToolMessage):
                    return {
                        "messages": [AIMessage(content="Booking completed")],
                        "step_count": state.step_count + 1,
                    }
                return {
                    "messages": [AIMessage(content="Please approve", tool_calls=calls)],
                    "step_count": state.step_count + 1,
                }

            with (
                patch.object(graph_module, "agent_node", scripted_agent),
                patch.object(nodes, "agent_tools", [book, sibling]),
            ):
                graph = graph_module.build_graph()
                config = {"configurable": {"thread_id": "approval-test"}}
                first = await graph.ainvoke(
                    {"messages": [HumanMessage(content="Book a room")]}, config
                )
                self.assertTrue(first.get("__interrupt__"))
                self.assertEqual(first["step_count"], 1)
                book.ainvoke.assert_not_awaited()
                sibling.ainvoke.assert_not_awaited()
                result = await graph.ainvoke(Command(resume=approved), config)
            if approved:
                book.ainvoke.assert_awaited_once()
                self.assertEqual(result["step_count"], 2)
            else:
                book.ainvoke.assert_not_awaited()
                sibling.ainvoke.assert_not_awaited()
                # Model APIs require every tool result to match a retained tool call.
                call_ids = {
                    c["id"]
                    for m in result["messages"]
                    if isinstance(m, AIMessage)
                    for c in m.tool_calls
                }
                results = [m for m in result["messages"] if isinstance(m, ToolMessage)]
                self.assertEqual({m.tool_call_id for m in results}, call_ids)
                self.assertEqual(len(results), len(calls))
                self.assertEqual(
                    result["messages"][-1].content, "Booking cancelled. No booking was created."
                )
                self.assertEqual(result["step_count"], 1)

        asyncio.run(scenario())

    def test_booking_pauses_then_executes_once_on_approval(self):
        self._approval_scenario(True)

    def test_cancel_skips_booking_and_keeps_valid_history(self):
        self._approval_scenario(False)

    def test_cancel_skips_sibling_side_effects(self):
        self._approval_scenario(False, extra_call=True)

    def test_budget_boundary(self):
        message = AIMessage(
            content="", tool_calls=[{"name": "search_hotels", "args": {}, "id": "s"}]
        )
        self.assertEqual(
            nodes.route_after_agent(AgentState(messages=[message], step_count=nodes.MAX_STEPS - 1)),
            "tools",
        )
        self.assertEqual(
            nodes.route_after_agent(AgentState(messages=[message], step_count=nodes.MAX_STEPS)),
            "end",
        )

    def test_approval_still_required_at_budget_boundary(self):
        message = AIMessage(content="", tool_calls=[{"name": "book_room", "args": {}, "id": "b"}])
        self.assertEqual(
            nodes.route_after_agent(AgentState(messages=[message], step_count=nodes.MAX_STEPS)),
            "human_approval",
        )


if __name__ == "__main__":
    unittest.main()
