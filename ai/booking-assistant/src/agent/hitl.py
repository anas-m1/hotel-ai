from typing import Any

import structlog
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import interrupt

from .state import AgentState

log = structlog.get_logger()


async def human_approval_node(state: AgentState) -> dict[str, Any]:
    """Pause for user approval when a booking is about to be created."""
    last_message = state.messages[-1]

    if not isinstance(last_message, AIMessage):
        return {}

    booking_calls = [tc for tc in last_message.tool_calls if tc["name"] == "book_room"]
    if not booking_calls:
        return {}

    tc = booking_calls[0]

    approval = interrupt(
        {
            "type": "booking_approval",
            "tool_call": {"name": tc["name"], "args": tc["args"]},
            "message": "The assistant wants to create a booking. Do you approve?",
        }
    )

    approved = approval if isinstance(approval, bool) else approval.get("approved", False)

    if not approved:
        remaining = [c for c in last_message.tool_calls if c["id"] != tc["id"]]
        filtered_message = AIMessage(
            content=last_message.content,
            tool_calls=remaining,
            id=last_message.id,
        )
        cancel_msg = ToolMessage(
            content="Booking was cancelled by user.",
            tool_call_id=tc["id"],
        )
        return {"messages": [filtered_message, cancel_msg]}

    return {}


def human_approval_edge(state: AgentState) -> str:
    """After human_approval, route to tools if there are remaining tool calls, else advance plan."""
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "advance"
