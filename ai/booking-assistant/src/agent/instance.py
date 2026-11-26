"""
Holds the compiled graph singleton so startup can inject the Redis checkpointer
before any request handler imports it.
"""

from __future__ import annotations

from typing import Any

_graph: Any = None


def get_graph() -> Any:
    return _graph


def set_graph(g: Any) -> None:
    global _graph
    _graph = g
