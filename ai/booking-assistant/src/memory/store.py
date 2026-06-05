from collections import defaultdict

from langchain_core.messages import BaseMessage


class InMemoryConversationStore:
    """Simple in-memory conversation history store.

    Will be replaced with Redis-backed storage in a later iteration.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[BaseMessage]] = defaultdict(list)

    def add_messages(self, session_id: str, messages: list[BaseMessage]) -> None:
        self._sessions[session_id].extend(messages)

    def get_messages(self, session_id: str) -> list[BaseMessage]:
        return self._sessions.get(session_id, [])

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
