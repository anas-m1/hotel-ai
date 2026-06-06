# ADR-013: LiteLLM Gateway — All LLM Calls Centralised

**Date:** Phase 2  
**Status:** Accepted

## Context
Multiple AI services (booking-assistant, future agents) need to call LLMs. Each could call Anthropic/OpenAI directly. Cost visibility, model swapping, and provider fallback need to be manageable without touching every service.

## Decision
All LLM calls go through a single internal FastAPI service (`ai/llm-gateway`) that wraps the `litellm` Python library. No AI service calls a provider SDK directly.

## Why
- **Single cost ledger**: every LLM call writes a JSONL cost record. `GET /v1/usage` gives the total spend without aggregating across services.
- **Model swap without code change**: changing `DEFAULT_MODEL` in `llm-gateway.env` reroutes all agents. No `grep` + `sed` across five services.
- **Provider fallback**: LiteLLM handles automatic fallback to a secondary provider if the primary is down. This logic lives once, in the gateway.
- **Prompt versioning**: the gateway serves named prompts from YAML files. Agents reference `prompt_name` rather than embedding prompt strings in code.

## Consequences
- The gateway is a single point of failure for all LLM calls. Mitigation: it is stateless and trivially horizontally scalable; health checks ensure it restarts fast.
- Added one network hop per LLM call. Acceptable given LLM latency dominates (100–10,000 ms) vs. internal HTTP overhead (~1 ms).
- The gateway speaks OpenAI wire format, so `langchain-openai` with `base_url` pointing to the gateway is the standard integration pattern.
