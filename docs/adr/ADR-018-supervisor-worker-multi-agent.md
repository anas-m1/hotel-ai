# ADR-018: Supervisor + Worker Multi-Agent Pattern

**Date:** Phase 5  
**Status:** Accepted

## Context

Phase 4 built a single ReAct agent with 9 tools. As the tool set grows (search, booking,
pricing, fraud, analytics), a monolithic agent becomes harder to reason about and more
expensive — every LLM call sees all tools in the context window regardless of relevance.

## Decision

Replace the single agent with a **supervisor + worker** topology:
- One supervisor LLM (claude-sonnet) receives the user request, decides which specialist
  to call, and synthesizes the final answer.
- Two specialist worker agents (claude-haiku), each with a focused tool set:
  `search_agent` (RAG + inventory tools) and `booking_agent` (reservation + guest tools).
- The supervisor uses **structured output** (`RoutingDecision` Pydantic model) to route —
  the routing decision is always a validated enum, never a free-form string.
- Workers return to the supervisor after completing their task (hub-and-spoke topology).

## Why

- **Tool set isolation**: each worker only sees its own tools. Fewer tokens, less confusion.
- **Cost tiering**: the supervisor (expensive, strategic) uses claude-sonnet; workers
  (cheap, tactical) use claude-haiku. Multi-step requests use haiku for the heavy lifting.
- **Structured routing**: using `with_structured_output(RoutingDecision)` eliminates
  routing hallucinations. The supervisor cannot invent a worker name that doesn't exist.
- **Extensibility**: adding a new specialist (e.g., `pricing_agent`) requires adding one
  node and one edge — the supervisor prompt learns about it from the updated system message.

## Consequences

- Two LLM calls minimum per request (supervisor → worker → supervisor). Acceptable because
  haiku latency is ~1–2 s and the user expects a multi-second response from a booking agent.
- The supervisor is a single point of coordination. If its structured output fails, the
  request fails. Mitigated by LangGraph's retry-on-exception and the gateway's fallback.
- Workers are stateless per invocation — they don't share memory between calls within the
  same session. Cross-turn memory is deferred to Phase 7 (Redis-backed MemoryStore).
