# ADR-021: Langfuse for Centralized LLM Observability

**Date:** Phase 7  
**Status:** Accepted

## Context

As the system grows to multiple AI services (llm-gateway, booking-assistant,
multi-agent), we need visibility into: which models are being called, how much
each call costs, how long each agent step takes, and what the LLM input/output
looked like when something goes wrong.

## Decision

Use **Langfuse** (self-hosted) as the single observability backend for all LLM calls:

- `ai/llm-gateway`: activate litellm's built-in Langfuse callback
  (`litellm.success_callback = ["langfuse"]`). Every LLM call is automatically
  traced — no manual instrumentation in each route.
- `ai/booking-assistant`, `ai/multi-agent`: pass `langfuse.callback.CallbackHandler`
  in the LangGraph `invoke` config. LangGraph emits span events for every node
  execution, tool call, and LLM invocation automatically.

Langfuse is optional at runtime: if `LANGFUSE_PUBLIC_KEY` is empty, tracing is
silently skipped. This keeps dev/test fast without a Langfuse instance.

## Why

- **Single dashboard**: all traces — gateway calls and agent runs — visible in
  one place with session/user linking.
- **Zero manual spans**: litellm's callback and LangGraph's callback system handle
  span creation. No `with tracer.start_span(...)` boilerplate in business code.
- **Self-hosted**: traces contain prompt text and user data. Sending this to a
  third-party SaaS requires consent; self-hosting avoids the concern entirely.
- **Cost attribution**: Langfuse aggregates token counts and cost per model, per
  session, per user — more granular than the gateway's flat JSONL log.

## Consequences

- Langfuse requires its own PostgreSQL database (`langfuse`). Created in
  `infra/docker/init-db.sh` alongside `booking_ops`.
- `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` must be set in each service's
  `.env` file to enable tracing. Generate these from the Langfuse UI after first
  login at `http://localhost:3000`.
- Traces are async fire-and-forget; a Langfuse outage does not affect LLM latency.
