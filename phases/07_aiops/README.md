# Phase 7 — AI Ops

## What this phase builds

Observability and durability infrastructure for the AI layer:

| Concern | Solution |
|---|---|
| LLM call tracing | Langfuse self-hosted (ADR-021) |
| Agent state persistence | Redis + `AsyncRedisSaver` (ADR-022) |
| HITL durability | Redis checkpointer survives restarts |
| Cost attribution | Langfuse per-session/per-model cost view |

## Architecture changes

```
Before Phase 7:
  booking-assistant ──► MemorySaver (in-process dict)
  multi-agent       ──► MemorySaver (in-process dict)
  llm-gateway       ──► JSONL file only

After Phase 7:
  booking-assistant ──► AsyncRedisSaver ──► Redis :6379
  multi-agent       ──► AsyncRedisSaver ──► Redis :6379
  llm-gateway       ──► litellm callback ──► Langfuse :3000
  booking-assistant ──► LangGraph callback ──► Langfuse :3000
  multi-agent       ──► LangGraph callback ──► Langfuse :3000
```

## New infrastructure services

| Service | Port | Purpose |
|---|---|---|
| `redis` | 6379 | LangGraph checkpoint store |
| `langfuse` | 3000 | LLM observability UI |

## Getting started

```bash
# 1. Start the full stack
docker compose -f infra/docker/docker-compose.yml up -d

# 2. Create a Langfuse account (first run only)
open http://localhost:3000
# Sign up → create a project → copy the public/secret keys

# 3. Add keys to env files
echo "LANGFUSE_PUBLIC_KEY=pk-lf-..." >> infra/docker/llm-gateway.env
echo "LANGFUSE_SECRET_KEY=sk-lf-..." >> infra/docker/llm-gateway.env
echo "LANGFUSE_PUBLIC_KEY=pk-lf-..." >> infra/docker/booking-assistant.env
echo "LANGFUSE_SECRET_KEY=sk-lf-..." >> infra/docker/booking-assistant.env
echo "LANGFUSE_PUBLIC_KEY=pk-lf-..." >> infra/docker/multi-agent.env
echo "LANGFUSE_SECRET_KEY=sk-lf-..." >> infra/docker/multi-agent.env

# 4. Restart AI services to pick up keys
docker compose -f infra/docker/docker-compose.yml restart \
  llm-gateway booking-assistant multi-agent

# 5. Make a booking request and watch traces appear in Langfuse
curl -s -X POST http://localhost:8092/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find hotels in Dubai", "session_id": "test-001"}' | jq .
```

## What you see in Langfuse

- **Traces**: one trace per agent invocation, with child spans for each node
- **Generations**: each LLM call with input messages, output, model, tokens, cost
- **Sessions**: all traces from the same `session_id` grouped together
- **Cost dashboard**: total spend by model, by session, by day

## What's next (Phase 8)

Knowledge graph — Neo4j + GraphRAG for entity-aware hotel recommendations and
Self-RAG with retrieval quality scoring.
