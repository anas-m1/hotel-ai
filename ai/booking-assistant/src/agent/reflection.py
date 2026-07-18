from typing import Any

import structlog
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..config import settings
from .prompts import REFLECTION_PROMPT
from .state import AgentState

log = structlog.get_logger()


async def reflect_on_error(state: AgentState) -> dict[str, Any]:
    """Reflect on tool errors and generate a corrected plan."""
    if not state.tool_errors:
        return {}

    llm = ChatOpenAI(
        model=settings.agent_model,
        temperature=0.2,
        base_url=f"{settings.llm_gateway_url}/v1",
        api_key="sk-noop",
    )

    error_context = "\n".join(state.tool_errors)
    messages = [
        SystemMessage(content=REFLECTION_PROMPT.format(errors=error_context)),
        *state.messages,
    ]

    response: AIMessage = await llm.ainvoke(messages)
    return {"messages": [response], "tool_errors": [], "retry_count": state.retry_count + 1}
