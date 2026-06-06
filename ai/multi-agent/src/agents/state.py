from __future__ import annotations

from typing import Annotated, Any
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class WorkerResult(BaseModel):
    worker: str
    output: str
    data: dict[str, Any] = Field(default_factory=dict)


class MultiAgentState(BaseModel):
    """Shared state flowing through the supervisor + worker graph."""

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    user_request: str = ""

    # Supervisor populates this; workers consume from it
    worker_tasks: list[dict[str, str]] = Field(default_factory=list)

    # Workers append their results here
    worker_results: list[WorkerResult] = Field(default_factory=list)

    # Supervisor synthesizes this after all workers finish
    final_response: str = ""

    # Which worker to invoke next (for sequential fallback routing)
    next_worker: str = "FINISH"
