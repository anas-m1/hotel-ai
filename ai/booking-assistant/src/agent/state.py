from typing import Annotated, Any

from langgraph.graph.message import add_messages
from pydantic import BaseModel


class ToolCall(BaseModel):
    name: str
    args: dict[str, Any]
    id: str = ""


class ToolResult(BaseModel):
    tool_call_id: str
    output: str


class AgentState(BaseModel):
    messages: Annotated[list, add_messages] = []
    session_id: str = ""
    user_id: str = ""
    tool_errors: list[str] = []
    retry_count: int = 0
    plan: list[str] = []
    current_step: int = 0
