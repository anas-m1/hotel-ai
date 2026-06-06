"""
Supervisor node: decides which specialist worker(s) to invoke.

Uses structured output so the LLM returns a typed routing decision
instead of free-form text. The supervisor runs first, then again after
all workers finish to synthesize the final answer.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agents.state import MultiAgentState
from config import settings

_SYSTEM_PROMPT = """\
You are a hotel booking supervisor. Your job is to analyze the user's request
and decide which specialist agents are needed to fulfill it.

Available workers:
- search_agent: finds hotels, checks room availability, answers questions about properties
- booking_agent: creates bookings, retrieves booking details, cancels bookings, manages guests

Rules:
- If the request involves both searching AND booking, route to search_agent first.
- If the user already knows the hotel/room and wants to book, route directly to booking_agent.
- After workers finish and you see their results in the conversation, set next_worker=FINISH
  and write a clear, friendly final_response for the user.
- Never route to a worker that has already been called for this request (check worker_results).
"""

_SYNTHESIS_PROMPT = """\
You are a hotel booking assistant. Based on the specialist agents' findings below,
write a clear, helpful, and concise response for the guest. Be friendly and specific.
"""


class RoutingDecision(BaseModel):
    next_worker: Literal["search_agent", "booking_agent", "FINISH"] = Field(
        description="Which worker to call next, or FINISH if the request is complete."
    )
    reasoning: str = Field(description="One sentence explaining the routing choice.")
    task_for_worker: str = Field(
        default="",
        description="Specific sub-task description for the chosen worker. Empty when FINISH.",
    )
    final_response: str = Field(
        default="",
        description="Filled only when next_worker=FINISH. The synthesized answer for the user.",
    )


def _build_supervisor_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=f"{settings.llm_gateway_url}/v1",
        api_key="not-needed",
        model=settings.supervisor_model,
        temperature=settings.agent_temperature,
    ).with_structured_output(RoutingDecision)


def supervisor_node(state: MultiAgentState) -> dict:
    """Routes to the next worker, or synthesizes the final response."""
    llm = _build_supervisor_llm()

    already_called = {r.worker for r in state.worker_results}
    context_parts = [f"User request: {state.user_request}"]
    for result in state.worker_results:
        context_parts.append(f"\n{result.worker} result:\n{result.output}")

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content="\n".join(context_parts)),
    ]
    if already_called:
        messages.append(
            HumanMessage(
                content=f"Workers already called: {', '.join(already_called)}. "
                "Decide what to do next."
            )
        )

    decision: RoutingDecision = llm.invoke(messages)  # type: ignore[assignment]

    update: dict = {"next_worker": decision.next_worker}
    if decision.next_worker != "FINISH":
        update["worker_tasks"] = [
            {"worker": decision.next_worker, "task": decision.task_for_worker}
        ]
    else:
        update["final_response"] = decision.final_response

    return update
