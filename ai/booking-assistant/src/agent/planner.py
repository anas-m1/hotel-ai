from typing import Any

import structlog
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from config import settings
from .prompts import PLANNER_PROMPT
from .state import AgentState

log = structlog.get_logger()


class Plan(BaseModel):
    steps: list[str]


async def create_plan(state: AgentState) -> dict[str, Any]:
    """Generate a step-by-step plan from the user's request."""
    llm = ChatOpenAI(
        model=settings.agent_model,
        temperature=0.2,
        base_url=f"{settings.llm_gateway_url}/v1",
        api_key="sk-noop",
    )

    structured_llm = llm.with_structured_output(Plan)
    plan: Plan = await structured_llm.ainvoke([
        SystemMessage(content=PLANNER_PROMPT),
        *state.messages,
    ])

    log.info("plan_created", steps=plan.steps)
    return {"plan": plan.steps, "current_step": 0}
