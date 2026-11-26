# ADR-012: LangGraph over LangChain Chains

**Date:** Phase 4  
**Status:** Accepted

## Context
The booking assistant agent needs cycles (tool call → reflect → tool call again), persistent state across HTTP requests (conversation memory), human-in-the-loop interrupts, and branching control flow. Need a framework that supports this.

## Decision
Use LangGraph (`langgraph`) for agent orchestration. LangChain chains (`langchain`) are not used directly — only `langchain-core` for tool definitions and message types.

## Why
- LangChain chains are DAGs (no cycles). An agent that retries after a tool error, or waits for human confirmation, needs cycles. LangGraph is a cyclic graph.
- LangGraph's `interrupt()` + `MemorySaver` checkpointer gives first-class HITL: execution suspends, state persists, resumes on the next HTTP request. Chains have no equivalent.
- LangGraph's `StateGraph` makes state explicit and typed — the full conversation history, pending tool calls, and retry count are all visible in the state object.
- `create_react_agent` from `langgraph.prebuilt` handles the standard think → act → observe loop with one function call, avoiding boilerplate.

## Consequences
- LangGraph is under active development — API changes are expected between minor versions. Pin to a tested version in `pyproject.toml`.
- The `langchain-openai` package is used to connect to the LLM gateway (which speaks OpenAI wire format), not to OpenAI directly.
